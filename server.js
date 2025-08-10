const express = require('express');
const cors = require('cors');
const multer = require('multer');
const { nanoid } = require('nanoid');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// --- config ---
const PORT = process.env.PORT || 3000;
const TEMP_DIR = path.join(__dirname, 'temp');
const ALLOWED_ORIGINS = [
  'http://localhost:19006', // Expo web
  'http://localhost:8081',  // RN dev
  'http://localhost:5173',  // Vite (if you test)
];

// Create temp directory if it doesn't exist
if (!fs.existsSync(TEMP_DIR)) {
  fs.mkdirSync(TEMP_DIR, { recursive: true });
}

// accept only pdf/ppt/pptx, max 20MB
const ACCEPTED_MIME = new Set([
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation'
]);
const MAX_FILE_SIZE = 20 * 1024 * 1024;

// in‑memory job store
const jobs = new Map(); // jobId -> { status, result?, timer?, error? }

// Function to run Python pipeline
async function runPipeline(filePath, options = {}) {
  return new Promise((resolve, reject) => {
    const args = [
      'pipeline.py',
      filePath,
      '--max-mcq', options.maxMcq || '8',
      '--max-short', options.maxShort || '4'
    ];

    if (options.model) {
      args.push('--model', options.model);
    }
    if (options.temperature) {
      args.push('--temperature', options.temperature.toString());
    }

    // Use the virtual environment's Python if it exists, otherwise system python
    const venvPython = path.join(__dirname, 'venv', 'bin', 'python');
    const pythonCommand = fs.existsSync(venvPython) ? venvPython : 'python3';

    console.log(`Running: ${pythonCommand} ${args.join(' ')}`);

    const pythonProcess = spawn(pythonCommand, args, {
      cwd: __dirname,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONPATH: __dirname }
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('close', (code) => {
      console.log(`Pipeline process exited with code ${code}`);
      if (stderr) console.log('Pipeline stderr:', stderr);
      
      if (code === 0) {
        try {
          // Look for JSON output between the RESULT markers or as the last JSON block
          let jsonString = '';
          
          // First try to find JSON between RESULT markers
          const resultStart = stdout.indexOf('================================================================================\nRESULT:\n================================================================================');
          if (resultStart !== -1) {
            const jsonStart = stdout.indexOf('{', resultStart);
            if (jsonStart !== -1) {
              // Find the end of JSON (look for the closing brace at the same level)
              let braceCount = 0;
              let jsonEnd = jsonStart;
              for (let i = jsonStart; i < stdout.length; i++) {
                if (stdout[i] === '{') braceCount++;
                else if (stdout[i] === '}') {
                  braceCount--;
                  if (braceCount === 0) {
                    jsonEnd = i + 1;
                    break;
                  }
                }
              }
              jsonString = stdout.substring(jsonStart, jsonEnd);
            }
          }
          
          // If that didn't work, try to find the last complete JSON object
          if (!jsonString) {
            const lines = stdout.trim().split('\n');
            let jsonLines = [];
            let inJson = false;
            let braceCount = 0;
            
            for (const line of lines) {
              if (line.trim().startsWith('{')) {
                inJson = true;
                jsonLines = [line];
                braceCount = (line.match(/\{/g) || []).length - (line.match(/\}/g) || []).length;
              } else if (inJson) {
                jsonLines.push(line);
                braceCount += (line.match(/\{/g) || []).length - (line.match(/\}/g) || []).length;
                if (braceCount === 0) {
                  jsonString = jsonLines.join('\n');
                  break;
                }
              }
            }
          }

          if (jsonString) {
            const result = JSON.parse(jsonString);
            resolve(result);
          } else {
            console.log('Full stdout:', stdout);
            reject(new Error('No valid JSON output from pipeline'));
          }
        } catch (error) {
          console.log('JSON parsing error:', error.message);
          console.log('Attempted to parse:', jsonString || 'No JSON found');
          reject(new Error(`Failed to parse pipeline output: ${error.message}`));
        }
      } else {
        reject(new Error(`Pipeline failed with code ${code}: ${stderr}`));
      }
    });

    pythonProcess.on('error', (error) => {
      reject(new Error(`Failed to start pipeline: ${error.message}`));
    });
  });
}

// multer setup (save to temp directory)
const upload = multer({
  storage: multer.diskStorage({
    destination: TEMP_DIR,
    filename: (req, file, cb) => {
      // Keep original extension
      const ext = path.extname(file.originalname);
      const name = `${nanoid()}${ext}`;
      cb(null, name);
    }
  }),
  limits: { fileSize: MAX_FILE_SIZE },
  fileFilter: (_req, file, cb) => {
    if (!ACCEPTED_MIME.has(file.mimetype)) {
      return cb(new Error('Unsupported file type'));
    }
    cb(null, true);
  }
});

const app = express();
app.use(
  cors({
    origin: (origin, cb) => {
      if (!origin) return cb(null, true); // allow curl/postman
      if (ALLOWED_ORIGINS.includes(origin)) return cb(null, true);
      return cb(new Error('Not allowed by CORS'));
    }
  })
);
app.use(express.json());

// health
app.get('/health', (_req, res) => res.json({ ok: true }));

// Get processing status and job count
app.get('/status', (_req, res) => {
  const stats = {
    totalJobs: jobs.size,
    processing: 0,
    completed: 0,
    failed: 0
  };
  
  for (const [_, job] of jobs.entries()) {
    if (job.status === 'processing') stats.processing++;
    else if (job.status === 'done') stats.completed++;
    else if (job.status === 'error') stats.failed++;
  }
  
  res.json(stats);
});

// upload -> create job, run pipeline
app.post('/uploads', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'file is required' });

    const jobId = nanoid();
    const filePath = req.file.path;
    const originalName = req.file.originalname || 'upload';
    
    // Parse options from request body or query
    const options = {
      maxMcq: parseInt(req.body.maxMcq || req.query.maxMcq || '8'),
      maxShort: parseInt(req.body.maxShort || req.query.maxShort || '4'),
      model: req.body.model || req.query.model || 'gpt-3.5-turbo',
      temperature: parseFloat(req.body.temperature || req.query.temperature || '0.2')
    };

    // Create job in "processing" state
    jobs.set(jobId, { status: 'processing', filePath, originalName });

    // Return immediately with job ID
    res.status(202).json({ jobId, status: 'processing' });

    // Run pipeline asynchronously
    try {
      console.log(`Starting pipeline for job ${jobId}: ${originalName}`);
      const result = await runPipeline(filePath, options);
      
      // Update job with success result
      jobs.set(jobId, {
        status: 'done',
        result: {
          jobId,
          status: 'done',
          ...result,
          meta: {
            ...result.meta,
            sourceFile: originalName
          }
        }
      });
      
      console.log(`Pipeline completed for job ${jobId}`);
    } catch (error) {
      console.error(`Pipeline failed for job ${jobId}:`, error.message);
      
      // Update job with error
      jobs.set(jobId, {
        status: 'error',
        error: error.message
      });
    } finally {
      // Clean up temp file
      try {
        fs.unlinkSync(filePath);
      } catch (e) {
        console.warn(`Failed to delete temp file ${filePath}:`, e.message);
      }
    }

  } catch (e) {
    return res.status(500).json({ error: e.message || 'server error' });
  }
});

// poll job
app.get('/jobs/:jobId', (req, res) => {
  const { jobId } = req.params;
  const record = jobs.get(jobId);

  if (!record) {
    return res.status(404).json({ error: 'Job not found' });
  }
  
  if (record.status === 'processing') {
    return res.json({ jobId, status: 'processing' });
  }
  
  if (record.status === 'done') {
    return res.json(record.result);
  }
  
  if (record.status === 'error') {
    return res.status(500).json({ 
      jobId, 
      status: 'error', 
      error: record.error || 'Unknown error occurred' 
    });
  }
  
  // fallback
  return res.status(500).json({ jobId, status: 'error', error: 'unknown state' });
});

// optional: cleanup finished jobs every 10 minutes
setInterval(() => {
  for (const [jobId, rec] of jobs.entries()) {
    if (rec.status === 'done' || rec.status === 'error') {
      // Clean up any remaining temp files
      if (rec.filePath && fs.existsSync(rec.filePath)) {
        try {
          fs.unlinkSync(rec.filePath);
        } catch (e) {
          console.warn(`Failed to cleanup temp file ${rec.filePath}:`, e.message);
        }
      }
      jobs.delete(jobId);
    }
  }
}, 10 * 60 * 1000);

app.use((err, _req, res, _next) => {
  if (err && err.message === 'Not allowed by CORS') {
    return res.status(403).json({ error: 'CORS blocked' });
  }
  if (err && err.message === 'Unsupported file type') {
    return res.status(415).json({ error: 'Unsupported file type' });
  }
  return res.status(500).json({ error: err?.message || 'server error' });
});

app.listen(PORT, () => {
  console.log(`Dummy API on http://localhost:${PORT}`);
});

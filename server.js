// Load environment variables from .env file
require('dotenv').config();

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
  'http://localhost:3000',  // Same origin
  '*'                       // Allow all for debugging
];

console.log('🚀 Starting Quiz Backend Server...');
console.log(`📂 Temp directory: ${TEMP_DIR}`);
console.log(`🌐 Allowed origins: ${ALLOWED_ORIGINS.join(', ')}`);

// Verify OpenAI API key is loaded
const apiKey = process.env.OPENAI_API_KEY;
if (apiKey) {
  console.log(`🔑 OpenAI API key loaded: ${apiKey.substring(0, 10)}...${apiKey.substring(apiKey.length - 4)}`);
} else {
  console.log('❌ OpenAI API key not found! Please check your .env file');
}

// Create temp directory if it doesn't exist
if (!fs.existsSync(TEMP_DIR)) {
  console.log('📁 Creating temp directory...');
  fs.mkdirSync(TEMP_DIR, { recursive: true });
  console.log('✅ Temp directory created');
} else {
  console.log('✅ Temp directory exists');
}

// accept only pdf/ppt/pptx, max 20MB
const ACCEPTED_MIME = new Set([
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation'
]);
const MAX_FILE_SIZE = 20 * 1024 * 1024;

console.log(`📋 Accepted MIME types: ${Array.from(ACCEPTED_MIME).join(', ')}`);
console.log(`📏 Max file size: ${Math.round(MAX_FILE_SIZE / 1024 / 1024)}MB`);

// in‑memory job store
const jobs = new Map(); // jobId -> { status, result?, timer?, error? }

console.log('💾 Job store initialized');

// Function to run Python pipeline
async function runPipeline(filePath, options = {}) {
  const startTime = Date.now();
  console.log(`🐍 Starting Python pipeline for file: ${path.basename(filePath)}`);
  console.log(`⚙️ Pipeline options:`, options);
  
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

    console.log(`🔧 Python command: ${pythonCommand}`);
    console.log(`📋 Pipeline args: ${args.join(' ')}`);

    const pythonProcess = spawn(pythonCommand, args, {
      cwd: __dirname,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONPATH: __dirname }
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      stdout += chunk;
      
      // Only log OpenAI-related output
      if (chunk.includes('🤖 Making OpenAI API call') || 
          chunk.includes('📥 OpenAI response received') ||
          chunk.includes('📊 Token usage') ||
          chunk.includes('🎉 Pipeline completed') ||
          chunk.includes('Generated') && chunk.includes('questions')) {
        console.log(chunk.trim());
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      const chunk = data.toString();
      stderr += chunk;
      
      // Only log API-related errors
      if (chunk.includes('API') || chunk.includes('openai') || chunk.includes('Error')) {
        console.log(`⚠️ ${chunk.trim()}`);
      }
    });

    pythonProcess.on('close', (code) => {
      const duration = Date.now() - startTime;
      console.log(`⏱️ Pipeline completed in ${duration}ms with exit code ${code}`);
      
      if (stderr && (stderr.includes('Error') || stderr.includes('API'))) {
        console.log(`⚠️ Pipeline errors: ${stderr.trim()}`);
      }
      
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
            console.log(`✅ Generated ${result.questions?.mcq?.length || 0} MCQ and ${result.questions?.short?.length || 0} short answer questions`);
            resolve(result);
          } else {
            console.log('❌ No valid JSON found in pipeline output');
            reject(new Error('No valid JSON output from pipeline'));
          }
        } catch (error) {
          console.log('❌ JSON parsing failed:', error.message);
          reject(new Error(`Failed to parse pipeline output: ${error.message}`));
        }
      } else {
        console.log(`❌ Pipeline failed with exit code ${code}`);
        reject(new Error(`Pipeline failed with code ${code}: ${stderr}`));
      }
    });

    pythonProcess.on('error', (error) => {
      console.log(`❌ Failed to start Python process: ${error.message}`);
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
      console.log(`📁 Storing uploaded file: ${file.originalname} -> ${name}`);
      cb(null, name);
    }
  }),
  limits: { fileSize: MAX_FILE_SIZE },
  fileFilter: (_req, file, cb) => {
    console.log(`🔍 Checking file: ${file.originalname}, MIME: ${file.mimetype}`);
    if (!ACCEPTED_MIME.has(file.mimetype)) {
      console.log(`❌ Rejected file type: ${file.mimetype}`);
      return cb(new Error('Unsupported file type'));
    }
    console.log(`✅ Accepted file: ${file.originalname}`);
    cb(null, true);
  }
});

console.log('📤 Multer upload middleware configured');

const app = express();

// Request logging middleware (before CORS)
app.use((req, res, next) => {
  // Only log upload and job requests
  if (req.method === 'POST' && req.url === '/uploads') {
    console.log(`� File upload request received`);
  }
  next();
});

app.use(
  cors({
    origin: true, // Allow all origins for debugging
    credentials: true
  })
);
app.use(express.json());

console.log('🌐 Express app configured with CORS and JSON middleware');

// health
app.get('/health', (_req, res) => {
  res.json({ ok: true });
});

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

// Debug endpoint to list all jobs
app.get('/debug/jobs', (_req, res) => {
  const jobList = {};
  for (const [jobId, job] of jobs.entries()) {
    jobList[jobId] = {
      status: job.status,
      createdAt: job.createdAt ? new Date(job.createdAt).toISOString() : null,
      completedAt: job.completedAt ? new Date(job.completedAt).toISOString() : null,
      failedAt: job.failedAt ? new Date(job.failedAt).toISOString() : null,
      processingTime: job.processingTime || null,
      originalName: job.originalName || null,
      error: job.error || null
    };
  }
  
  res.json({
    totalJobs: jobs.size,
    jobs: jobList
  });
});

// upload -> create job, run pipeline
app.post('/uploads', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'file is required' });
    }

    const jobId = nanoid();
    const filePath = req.file.path;
    const originalName = req.file.originalname || 'upload';
    
    console.log(`📁 Processing: ${originalName} -> Job ID: ${jobId}`);
    
    // Parse options from request body or query
    const options = {
      maxMcq: parseInt(req.body.maxMcq || req.query.maxMcq || '8'),
      maxShort: parseInt(req.body.maxShort || req.query.maxShort || '4'),
      model: req.body.model || req.query.model || 'gpt-3.5-turbo',
      temperature: parseFloat(req.body.temperature || req.query.temperature || '0.2')
    };

    // Create job in "processing" state
    jobs.set(jobId, { 
      status: 'processing', 
      filePath, 
      originalName,
      createdAt: Date.now(),
      options 
    });

    // Return immediately with job ID
    res.status(202).json({ jobId, status: 'processing' });

    // Run pipeline asynchronously
    
    try {
      const pipelineStart = Date.now();
      
      const result = await runPipeline(filePath, options);
      
      const pipelineDuration = Date.now() - pipelineStart;
      
      // Update job with success result
      const finalResult = {
        jobId,  // Use server job ID, not pipeline job ID
        status: 'done',
        ...result,
        meta: {
          ...result.meta,
          sourceFile: originalName,
          processingTime: pipelineDuration
        }
      };
      
      // Override the jobId to match our server job ID
      finalResult.jobId = jobId;
      
      jobs.set(jobId, {
        status: 'done',
        result: finalResult,
        completedAt: Date.now(),
        processingTime: pipelineDuration
      });
      
    } catch (error) {
      console.log(`❌ Pipeline failed for job ${jobId}: ${error.message}`);
      
      // Update job with error
      jobs.set(jobId, {
        status: 'error',
        error: error.message,
        failedAt: Date.now(),
        processingTime: Date.now() - (jobs.get(jobId)?.createdAt || Date.now())
      });
      
    } finally {
      // Clean up temp file
      try {
        fs.unlinkSync(filePath);
      } catch (e) {
        // Ignore cleanup errors
      }
    }

  } catch (e) {
    console.log('❌ Upload request failed:', e.message);
    return res.status(500).json({ error: e.message || 'server error' });
  }
});

// poll job
app.get('/jobs/:jobId', (req, res) => {
  const { jobId } = req.params;
  console.log(`🔍 Job status request for: ${jobId}`);
  
  // Log current jobs for debugging
  console.log(`💾 Current jobs in memory: ${jobs.size} total`);
  if (jobs.size > 0) {
    const jobList = Array.from(jobs.keys()).map(id => {
      const job = jobs.get(id);
      return `${id}: ${job.status} (${job.createdAt ? new Date(job.createdAt).toISOString() : 'no timestamp'})`;
    });
    console.log(`📋 Job list: ${jobList.join(', ')}`);
  } else {
    console.log(`📋 No jobs in memory`);
  }
  
  const record = jobs.get(jobId);

  if (!record) {
    console.log(`❌ Job not found: ${jobId}`);
    console.log(`🔍 Available job IDs: [${Array.from(jobs.keys()).join(', ')}]`);
    return res.status(404).json({ error: 'Job not found' });
  }
  
  console.log(`📊 Job ${jobId} status: ${record.status}`);
  
  if (record.status === 'processing') {
    const processingTime = Date.now() - (record.createdAt || Date.now());
    console.log(`⏳ Job ${jobId} still processing (${Math.round(processingTime / 1000)}s elapsed)`);
    return res.json({ jobId, status: 'processing' });
  }
  
  if (record.status === 'done') {
    console.log(`✅ Job ${jobId} completed, returning result`);
    console.log('📤 Sending result to client:', JSON.stringify(record.result, null, 2));
    return res.json(record.result);
  }
  
  if (record.status === 'error') {
    console.log(`❌ Job ${jobId} failed: ${record.error}`);
    return res.status(500).json({ 
      jobId, 
      status: 'error', 
      error: record.error || 'Unknown error occurred' 
    });
  }
  
  // fallback
  console.log(`⚠️ Job ${jobId} in unknown state: ${record.status}`);
  return res.status(500).json({ jobId, status: 'error', error: 'unknown state' });
});

// optional: cleanup finished jobs every 30 minutes (reduced frequency for debugging)
setInterval(() => {
  const beforeCount = jobs.size;
  console.log(`🧹 Starting periodic job cleanup... (${beforeCount} jobs before cleanup)`);
  
  if (beforeCount === 0) {
    console.log('🧹 No jobs to clean up');
    return;
  }
  
  let deletedJobs = 0;
  let cleanedFiles = 0;
  
  for (const [jobId, rec] of jobs.entries()) {
    const ageMinutes = (Date.now() - (rec.completedAt || rec.failedAt || rec.createdAt || 0)) / (1000 * 60);
    
    // Only clean up jobs older than 20 minutes
    if ((rec.status === 'done' || rec.status === 'error') && ageMinutes > 20) {
      console.log(`🗑️ Cleaning up ${rec.status} job ${jobId} (${Math.round(ageMinutes)} minutes old)`);
      
      // Clean up any remaining temp files
      if (rec.filePath && fs.existsSync(rec.filePath)) {
        try {
          fs.unlinkSync(rec.filePath);
          cleanedFiles++;
          console.log(`🗑️ Cleaned up temp file for job ${jobId}: ${path.basename(rec.filePath)}`);
        } catch (e) {
          console.warn(`⚠️ Failed to cleanup temp file ${rec.filePath}:`, e.message);
        }
      }
      jobs.delete(jobId);
      deletedJobs++;
    } else if (rec.status === 'done' || rec.status === 'error') {
      console.log(`⏳ Keeping ${rec.status} job ${jobId} (${Math.round(ageMinutes)} minutes old, under 20 minute threshold)`);
    }
  }
  
  const afterCount = jobs.size;
  console.log(`🧹 Cleanup complete: deleted ${deletedJobs} jobs, cleaned ${cleanedFiles} files, ${afterCount} jobs remaining`);
}, 30 * 60 * 1000);

console.log('⏰ Periodic cleanup scheduled (every 30 minutes, keeps jobs for 20 minutes)');

app.use((err, _req, res, _next) => {
  console.error('🚨 Express error handler caught:', err.message);
  
  if (err && err.message === 'Not allowed by CORS') {
    console.log('❌ CORS error response sent');
    return res.status(403).json({ error: 'CORS blocked' });
  }
  if (err && err.message === 'Unsupported file type') {
    console.log('❌ Unsupported file type error response sent');
    return res.status(415).json({ error: 'Unsupported file type' });
  }
  
  console.log('❌ Generic server error response sent');
  return res.status(500).json({ error: err?.message || 'server error' });
});

app.listen(PORT, () => {
  console.log(`🚀 Quiz Backend Server running on http://localhost:${PORT}`);
  console.log(`📋 Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`🐍 Python pipeline ready`);
  console.log(`💾 Job store ready`);
  console.log(`📁 Temp directory: ${TEMP_DIR}`);
  console.log('✅ Server startup complete!');
});

const express = require('express');
const cors = require('cors');
const multer = require('multer');
const { nanoid } = require('nanoid');

// --- config ---
const PORT = process.env.PORT || 3000;
const ALLOWED_ORIGINS = [
  'http://localhost:19006', // Expo web
  'http://localhost:8081',  // RN dev
  'http://localhost:5173',  // Vite (if you test)
];

// accept only pdf/ppt/pptx, max 20MB
const ACCEPTED_MIME = new Set([
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation'
]);
const MAX_FILE_SIZE = 20 * 1024 * 1024;

// in‑memory job store
const jobs = new Map(); // jobId -> { status, result?, timer? }

// static result used when job completes
const STATIC_RESULT = {
  questions: {
    mcq: [
      {
        id: 'q1',
        question: 'What is photosynthesis?',
        options: [
          'Energy release in mitochondria',
          'Conversion of light energy into chemical energy (glucose)',
          'Protein synthesis in ribosomes',
          'DNA replication in the nucleus'
        ],
        answerIndex: 1,
        explanation:
          'Plants convert light energy to chemical energy stored as glucose using CO₂ and H₂O.'
      },
      {
        id: 'q2',
        question: 'Which molecule is the primary energy currency of the cell?',
        options: ['ATP', 'DNA', 'Glucose', 'NADH'],
        answerIndex: 0,
        explanation: 'ATP directly powers cellular processes.'
      }
    ],
    short: [
      {
        id: 's1',
        prompt: 'Define mitosis in one sentence.',
        expectedKeywords: ['cell division', 'two identical daughter cells']
      },
      {
        id: 's2',
        prompt: 'Name the organelle responsible for aerobic respiration.',
        expectedKeywords: ['mitochondria']
      }
    ]
  },
  meta: { sourceFile: 'Lecture01.pdf', pages: 24 }
};

// multer setup (memory storage; we ignore the buffer)
const upload = multer({
  storage: multer.memoryStorage(),
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

// upload -> create job, schedule completion
app.post('/uploads', upload.single('file'), (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'file is required' });

    const jobId = nanoid();
    const sourceFile = req.file.originalname || 'upload';
    // create job in "processing"
    const record = { status: 'processing' };
    jobs.set(jobId, record);

    // simulate processing delay (2–3.5s)
    const delay = 2000 + Math.floor(Math.random() * 1500);
    record.timer = setTimeout(() => {
      jobs.set(jobId, {
        status: 'done',
        result: {
          jobId,
          status: 'done',
          ...STATIC_RESULT,
          meta: { ...STATIC_RESULT.meta, sourceFile }
        }
      });
    }, delay);

    return res.status(202).json({ jobId, status: 'processing' });
  } catch (e) {
    return res.status(500).json({ error: e.message || 'server error' });
  }
});

// poll job
app.get('/jobs/:jobId', (req, res) => {
  const { jobId } = req.params;
  const record = jobs.get(jobId);

  if (!record) {
    // emulate unknown job as still cooking for nicer UX, or return 404
    return res.status(200).json({ jobId, status: 'processing' });
  }
  if (record.status === 'processing') {
    return res.json({ jobId, status: 'processing' });
  }
  if (record.status === 'done') {
    return res.json(record.result);
  }
  // fallback error state
  return res.status(200).json({ jobId, status: 'error', error: 'unknown state' });
});

// optional: cleanup finished jobs every 10 minutes
setInterval(() => {
  const now = Date.now();
  for (const [jobId, rec] of jobs.entries()) {
    if (rec.status === 'done' || rec.status === 'error') {
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

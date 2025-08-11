# Quiz Backend Server

A REST API server that integrates the Python quiz generation pipeline with a web interface.

## Features

- **File Upload**: Upload PDF/PPTX documents via REST API
- **Asynchronous Processing**: Non-blocking question generation using job queues
- **Configurable Parameters**: Customize question counts, model settings, and temperature
- **Real-time Status**: Poll job status and retrieve results when ready
- **Auto Cleanup**: Automatic cleanup of temporary files and completed jobs

## API Endpoints

### 🏥 Health Check
```http
GET /health
```
Returns server health status.

### 📊 Server Statistics
```http
GET /status
```
Returns processing statistics and job counts.

### 📤 Upload Document
```http
POST /uploads
Content-Type: multipart/form-data

file: <PDF or PPTX file>
maxMcq: 8 (optional)
maxShort: 4 (optional)
model: gpt-3.5-turbo (optional)
temperature: 0.2 (optional)
```

Returns: `{ jobId: "abc123", status: "processing" }`

### 🔍 Poll Job Status
```http
GET /jobs/:jobId
```

Returns:
- **Processing**: `{ jobId: "abc123", status: "processing" }`
- **Completed**: Full result JSON with questions and metadata
- **Failed**: `{ jobId: "abc123", status: "error", error: "error message" }`

## Usage Examples

### Command Line (curl)
```bash
# Upload document
curl -X POST \
  -F "file=@/path/to/lecture.pdf" \
  -F "maxMcq=6" \
  -F "maxShort=3" \
  http://localhost:3000/uploads

# Poll for results (replace JOB_ID with actual job ID)
curl http://localhost:3000/jobs/JOB_ID
```

### JavaScript/Frontend
```javascript
// Upload file
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('maxMcq', '8');
formData.append('maxShort', '4');

const uploadResponse = await fetch('http://localhost:3000/uploads', {
  method: 'POST',
  body: formData
});

const { jobId } = await uploadResponse.json();

// Poll for results
const pollResult = async () => {
  const response = await fetch(`http://localhost:3000/jobs/${jobId}`);
  const result = await response.json();
  
  if (result.status === 'processing') {
    setTimeout(pollResult, 2000); // Poll every 2 seconds
  } else if (result.status === 'done') {
    console.log('Questions generated:', result.questions);
  } else {
    console.error('Error:', result.error);
  }
};

pollResult();
```

### Python Client
```python
import requests
import time

# Upload
with open('/path/to/lecture.pdf', 'rb') as f:
    files = {'file': ('lecture.pdf', f, 'application/pdf')}
    data = {'maxMcq': '6', 'maxShort': '3'}
    
    response = requests.post('http://localhost:3000/uploads', 
                           files=files, data=data)
    job_id = response.json()['jobId']

# Poll for results
while True:
    response = requests.get(f'http://localhost:3000/jobs/{job_id}')
    result = response.json()
    
    if result['status'] == 'done':
        print(f"Generated {len(result['questions']['mcq'])} MCQ questions")
        break
    elif result['status'] == 'error':
        print(f"Error: {result['error']}")
        break
    
    time.sleep(2)
```

## Configuration

### Environment Variables
- `PORT`: Server port (default: 3000)
- `OPENAI_API_KEY`: Required for question generation

### File Limits
- **Supported formats**: PDF, PPT, PPTX
- **Max file size**: 20MB
- **Processing timeout**: No limit (async processing)

### CORS Policy
Allows requests from:
- `http://localhost:19006` (Expo web)
- `http://localhost:8081` (React Native dev)
- `http://localhost:5173` (Vite dev)

## Starting the Server

```bash
# Install dependencies
npm install

# Start in development mode
npm run dev

# Start in production mode
npm start
```

## Testing

Use the included test script to verify integration:

```bash
python test_server_integration.py /path/to/document.pdf
```

## Response Format

### Successful Generation
```json
{
  "jobId": "abc123",
  "status": "done",
  "questions": {
    "mcq": [
      {
        "id": "q_12345678",
        "question": "What is...",
        "options": ["A", "B", "C", "D"],
        "answerIndex": 1,
        "explanation": "Because..."
      }
    ],
    "short": [
      {
        "id": "s_87654321",
        "prompt": "Explain...",
        "expectedKeywords": ["keyword1", "keyword2"]
      }
    ]
  },
  "meta": {
    "sourceFile": "lecture.pdf",
    "pages": 23,
    "tokenCounts": {
      "raw": 2062,
      "notes": 1822,
      "promptIn": 1980,
      "modelOut": 308
    },
    "strategy": "single",
    "chunks": 1
  }
}
```

### Error Response
```json
{
  "jobId": "abc123",
  "status": "error",
  "error": "Pipeline failed: API key not set"
}
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Node.js       │    │   Python        │
│   (React/Web)   │────│   Server        │────│   Pipeline      │
│                 │    │   (Express)     │    │   (OpenAI)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │ 1. Upload PDF         │ 2. Save temp file     │
        │ 2. Poll status        │ 3. Spawn Python      │ 3. Process doc
        │ 3. Get results        │ 4. Parse JSON output  │ 4. Generate Q&A
        │                       │ 5. Return results     │ 5. Return JSON
```

The server acts as a bridge between web clients and the Python pipeline, providing:
- File upload handling
- Asynchronous job management  
- Process orchestration
- Result formatting
- Error handling
- Resource cleanup

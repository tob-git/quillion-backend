# Quiz Generation Pipeline

A complete document processing pipeline that extracts text from PDF/PPTX files, cleans and compresses the content, and generates quiz questions using OpenAI GPT-3.5.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your OpenAI API key in `.env`:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

### Command Line
```bash
python pipeline.py document.pdf --max-mcq 8 --max-short 4
```

### Programmatic Usage
```python
import asyncio
from pipeline import process_document

async def main():
    result = await process_document("document.pdf", max_mcq=8, max_short=4)
    print(f"Generated {len(result['questions']['mcq'])} MCQ questions")
    
asyncio.run(main())
```

## Components

- **extract_text.py**: Extracts text from PDF/PPTX with OCR fallback
- **clean_text.py**: Cleans and normalizes extracted text
- **compress_notes.py**: Compresses text to key study notes using TF-IDF
- **pipeline.py**: Main orchestration with OpenAI integration

## Features

- **Smart Strategy Selection**: Automatically chooses single call or chunked map-reduce based on content size
- **Academic Content Cleaning**: Removes course codes, Dr. names, and other noise
- **Deduplication**: Ensures no duplicate questions are generated
- **Error Handling**: Comprehensive retry logic and fallback mechanisms
- **Token Management**: Tracks and optimizes OpenAI API usage

## Output Format

```json
{
  "jobId": "unique_id",
  "status": "done",
  "questions": {
    "mcq": [
      {
        "id": "q_12345678",
        "question": "What is...",
        "options": ["A", "B", "C", "D"],
        "answerIndex": 0,
        "explanation": "..."
      }
    ],
    "short": [
      {
        "id": "s_87654321", 
        "prompt": "Explain...",
        "expectedKeywords": ["key1", "key2"]
      }
    ]
  },
  "meta": {
    "strategy": "single",
    "tokenCounts": {...},
    "chunks": 1
  }
}
```

## Requirements

- Python 3.10+
- OpenAI API key
- Tesseract OCR (for image text extraction)

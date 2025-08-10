# Document Processing and Question Generation Pipeline

This module (`orchestrate_pipeline.py`) provides a complete pipeline for processing documents and generating quiz questions using OpenAI GPT-3.5.

## Features

### 🔄 **Complete Pipeline Integration**
- **Text Extraction**: PDF/PPTX documents using existing `extract_text.py`
- **Text Cleaning**: Removes headers, footers, boilerplate using `clean_text.py`
- **Content Compression**: Creates study notes with TF-IDF keywords using `compress_notes.py`
- **Question Generation**: Uses OpenAI GPT-3.5 to generate MCQ and short-answer questions

### 🧠 **Smart Processing Strategies**
- **Single Call**: For smaller documents (≤6000 tokens)
- **Chunked Map-Reduce**: For larger documents with intelligent chunking
- **Token Estimation**: Cheap approximation (words × 1.3)
- **Automatic Strategy Selection**: Based on content size

### 📝 **Question Types**
- **Multiple Choice Questions (MCQ)**: 4 options, 1 correct answer, explanations
- **Short Answer Questions**: Open-ended with expected keywords
- **Deduplication**: Removes similar questions using normalized stems
- **Validation**: Ensures proper format and required fields

### 🔧 **Robust Error Handling**
- **Retry Logic**: Exponential backoff for API timeouts/rate limits
- **JSON Validation**: Handles malformed responses with correction prompts
- **Fallback Strategies**: Manual merging if reduce phase fails

## Installation

```bash
# Install dependencies
pip install openai httpx

# Or use requirements.txt
pip install -r requirements.txt
```

## Usage

### Environment Setup

```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

### Programmatic Usage

```python
import asyncio
from orchestrate_pipeline import process_document

async def main():
    result = await process_document(
        "/path/to/document.pdf",
        max_mcq=8,
        max_short=4,
        model="gpt-3.5-turbo",
        temperature=0.2
    )
    
    if result["status"] == "done":
        print(f"Generated {len(result['questions']['mcq'])} MCQ questions")
        print(f"Generated {len(result['questions']['short'])} short questions")
    else:
        print(f"Error: {result['error']}")

asyncio.run(main())
```

### Command Line Usage

```bash
# Basic usage
python orchestrate_pipeline.py /path/to/document.pdf

# With options
python orchestrate_pipeline.py document.pdf \
    --max-mcq 10 \
    --max-short 5 \
    --model gpt-3.5-turbo \
    --temperature 0.3

# Force strategy
python orchestrate_pipeline.py document.pdf --strategy chunked
```

## API Reference

### Main Function

```python
async def process_document(
    file_path: str,
    *,
    model: str = "gpt-3.5-turbo",
    max_mcq: int = 8,
    max_short: int = 4,
    temperature: float = 0.2,
    single_call_token_limit: int = 6000,
    chunk_target_tokens: int = 1500,
    request_timeout_s: int = 30,
    max_retries: int = 2,
) -> dict
```

**Parameters:**
- `file_path`: Path to PDF or PPTX document
- `model`: OpenAI model (default: "gpt-3.5-turbo")
- `max_mcq`: Maximum MCQ questions to generate (default: 8)
- `max_short`: Maximum short answer questions (default: 4)
- `temperature`: Model creativity (0.0-1.0, default: 0.2)
- `single_call_token_limit`: Threshold for strategy selection (default: 6000)
- `chunk_target_tokens`: Target tokens per chunk (default: 1500)
- `request_timeout_s`: API timeout in seconds (default: 30)
- `max_retries`: Maximum retry attempts (default: 2)

### Return Format

```json
{
  "jobId": "abc12345",
  "status": "done",
  "questions": {
    "mcq": [
      {
        "id": "q_def67890",
        "question": "What is the primary obligation of states regarding human rights?",
        "options": [
          "To respect only",
          "To respect, protect, and fulfill",
          "To protect only",
          "To fulfill only"
        ],
        "answerIndex": 1,
        "explanation": "States have three broad obligations: respect, protect, and fulfill human rights."
      }
    ],
    "short": [
      {
        "id": "s_ghi34567",
        "prompt": "Explain the principle of progressive realization in human rights law.",
        "expectedKeywords": ["progressive", "realization", "resources", "obligations"]
      }
    ]
  },
  "meta": {
    "sourceFile": "lecture.pdf",
    "pages": 23,
    "tokenCounts": {
      "raw": 15420,
      "notes": 4280,
      "promptIn": 4500,
      "modelOut": 850
    },
    "strategy": "single",
    "chunks": 1
  }
}
```

## Processing Strategies

### Single Call Strategy
Used when `notes_tokens ≤ single_call_token_limit`

- Concatenates all study notes
- Makes one API call to generate all questions
- Faster and more coherent for smaller documents

### Chunked Map-Reduce Strategy
Used when `notes_tokens > single_call_token_limit`

1. **Map Phase**: 
   - Split notes into chunks (~1500 tokens each)
   - Generate 2 MCQ + 1 short per chunk
   - Track seen question stems to avoid overlap

2. **Reduce Phase**:
   - Merge all partial question lists
   - Remove duplicates and diversify stems
   - Cap at requested maximums

## Quality Controls

### Question Validation
- **MCQ**: Must have exactly 4 options, valid answer index (0-3), non-empty strings
- **Short**: Must have non-empty prompt and keyword list
- **IDs**: Auto-generated if missing or malformed (`q_<uuid8>`, `s_<uuid8>`)

### Deduplication
- Normalizes question stems (lowercase, remove punctuation, first 12 words)
- Removes questions with identical normalized stems
- Preserves question diversity

### Content Filtering
- Only uses cleaned, compressed study notes (no raw text)
- Focuses on factual content from document
- Avoids generating questions from headers/footers/boilerplate

## Token Management

### Estimation
- Simple approximation: `word_count × 1.3`
- Used for strategy selection and chunking
- Actual usage tracked when available from API

### Limits
- **Single call**: Configurable limit (default 6000 tokens)
- **Chunk size**: Target tokens per chunk (default 1500)
- **Safety**: Notes truncated at 8000 words max

## Error Handling

### API Errors
- **Rate Limits**: Exponential backoff retry
- **Timeouts**: Configurable timeout with retry
- **Invalid JSON**: Correction prompt and retry

### Document Errors
- **File not found**: Clear error message
- **Unsupported format**: Handled by extract_text.py
- **Empty content**: Returns empty question lists

### Graceful Degradation
- Partial success: Returns questions generated so far
- Failed chunks: Skipped with warning
- Reduce failure: Manual merge fallback

## Testing

```bash
# Test utility functions
python test_orchestrate.py

# Test with real document (requires API key)
export OPENAI_API_KEY="your-key"
python orchestrate_pipeline.py test_certificate.pdf
```

## Dependencies

- `openai>=1.0.0`: Official OpenAI Python SDK
- `httpx>=0.24.0`: Async HTTP client
- `asyncio`: Built-in async support
- Existing pipeline modules: `extract_text.py`, `clean_text.py`, `compress_notes.py`

## Performance

### Typical Processing Times
- **Small document** (1-5 pages): 10-30 seconds
- **Medium document** (5-20 pages): 30-90 seconds  
- **Large document** (20+ pages): 2-5 minutes (chunked)

### Token Usage
- **Single strategy**: 1 API call (~4000-8000 tokens total)
- **Chunked strategy**: 3-10 API calls depending on size
- **Cost estimate**: $0.01-0.10 per document (GPT-3.5-turbo pricing)

## Best Practices

1. **Set reasonable limits**: Don't generate too many questions from small documents
2. **Use appropriate temperature**: 0.1-0.3 for factual questions, higher for creative
3. **Monitor token usage**: Large documents can consume significant tokens
4. **Cache results**: Store generated questions to avoid regeneration
5. **Validate output**: Always check question quality before use

## Troubleshooting

### Common Issues

**"OPENAI_API_KEY not set"**
```bash
export OPENAI_API_KEY="your-actual-api-key"
```

**"Rate limit exceeded"**
- Wait and retry, or implement longer delays
- Consider using a higher tier API plan

**"Empty questions returned"**
- Check if document content is meaningful after cleaning
- Ensure document has sufficient text content
- Review token limits and chunking settings

**"Invalid JSON response"**
- Usually handled automatically with retry
- May indicate model issues or complex content

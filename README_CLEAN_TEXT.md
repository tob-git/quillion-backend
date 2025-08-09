# Text Cleaning Module Documentation

## Overview

The `clean_text.py` module provides deterministic text cleaning for extracted document sections. It removes common noise patterns like headers, footers, boilerplate text, and other artifacts that typically appear in extracted PDF/PPTX content.

## Main Function

```python
def clean_extracted_sections(sections: list[dict]) -> list[dict]:
    """
    Cleans a list of extracted sections in place (deterministic, no LLM).
    Returns a new list of cleaned section dicts in the same shape:
        [ { "id": str, "title": str, "text": str }, ... ]
    """
```

## Cleaning Operations

### 1. Strip Headers/Footers/Page Numbers
- Removes lines matching patterns:
  - `^\s*page\s*\d+\s*$` (case-insensitive)
  - `^\s*\d+\s*$` (standalone numbers)
  - `^\s*(header|footer).*` (obvious boilerplate patterns)
- Identifies lines appearing in 80%+ of sections as global boilerplate

### 2. Collapse Whitespace
- Multiple spaces → single space
- Multiple newlines → single `\n`
- Strips leading/trailing whitespace from each line

### 3. Remove Duplicate Lines
- Eliminates consecutive duplicate lines within sections
- Removes lines appearing in 80%+ of all sections (global boilerplate)

### 4. Remove References/Appendix Sections
- Drops entire sections with titles starting with "references", "bibliography", or "appendix"
- Truncates sections where these keywords appear mid-text followed by >50% citations/URLs

### 5. Kill Boilerplate Patterns
Removes lines containing (case-insensitive):
- "all rights reserved"
- "©" 
- "copyright"
- "terms of use"
- "table of contents"

### 6. Trim Long Paragraphs
- Splits text into paragraphs (double newline separation)
- For paragraphs >1000 characters: keeps only first and last sentence
- Rejoins sentences with a space

### 7. Final Cleanup
- Collapses whitespace again
- Drops sections with empty text after cleaning
- Logs section IDs that were dropped or truncated

## Usage Examples

### Basic Usage
```python
from clean_text import clean_extracted_sections

sections = [
    {"id": "s1", "title": "Page 1", "text": "Header\nContent here\nPage 1\n1"},
    {"id": "s2", "title": "References", "text": "Ref 1\nRef 2"}
]

cleaned = clean_extracted_sections(sections)
# Result: [{"id": "s1", "title": "Page 1", "text": "Content here"}]
```

### CLI Usage
```bash
# Clean sections from JSON file
python clean_text.py sections.json

# Clean from stdin (pipe from extract_text.py)
python extract_text.py document.pdf | python clean_text.py -

# Test with sample data
echo '[{"id":"s1","title":"Test","text":"Sample text"}]' | python clean_text.py -
```

### Combined Processing
```bash
# Extract and clean in one step
python process_document.py document.pdf

# Extract without cleaning
python process_document.py document.pdf --no-clean
```

## Input/Output Format

### Input
```json
[
  {
    "id": "s1",
    "title": "Page 1", 
    "text": "Header text\nPhotosynthesis is...\nPage 1\n1\nFooter"
  },
  {
    "id": "s2",
    "title": "References",
    "text": "Reference 1\nReference 2\nhttps://example.com"
  }
]
```

### Output
```json
[
  {
    "id": "s1",
    "title": "Page 1",
    "text": "Photosynthesis is..."
  }
]
```

## Features

✅ **Deterministic**: No LLM or AI - pure rule-based cleaning  
✅ **Preserves Structure**: Maintains section ID and title  
✅ **Handles Multiple Formats**: Works with extract_text.py output or raw sections  
✅ **Configurable**: Can disable cleaning with `--no-clean` flag  
✅ **Traceable**: Logs which sections were dropped/modified  
✅ **Fast**: Efficient regex-based processing  

## Integration with Node.js

```javascript
const { spawn } = require('child_process');

function processDocument(filePath, clean = true) {
  return new Promise((resolve, reject) => {
    const args = [clean ? 'process_document.py' : 'extract_text.py', filePath];
    if (!clean) args.push('--no-clean');
    
    const python = spawn('python', args, { cwd: __dirname });
    
    let output = '';
    python.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    python.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(output);
          resolve(result);
        } catch (e) {
          reject(new Error('Failed to parse JSON output'));
        }
      } else {
        reject(new Error(`Process exited with code ${code}`));
      }
    });
  });
}
```

## Dependencies

- Python 3.10+
- `re` module (built-in)
- `collections.Counter` (built-in)
- `typing` (built-in)

No external dependencies required for the cleaning module itself.

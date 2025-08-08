# Setup Guide for Text Extraction Module

## Quick Start

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Test the module:**
   ```bash
   python test_extract.py
   ```

4. **Use with actual files:**
   ```bash
   python extract_text.py /path/to/your/file.pdf
   python extract_text.py /path/to/your/file.pptx
   ```

## Resolving TensorFlow Conflicts

If you encounter dependency conflicts with TensorFlow (like typing-extensions), you have several options:

### Option 1: Use the Virtual Environment (Recommended)
The virtual environment isolates the dependencies and avoids conflicts with your global Python installation.

### Option 2: Pin typing-extensions Version
If you need to use this alongside TensorFlow, uncomment this line in requirements.txt:
```
typing-extensions<4.6.0
```

### Option 3: Update TensorFlow
Consider updating to a newer version of TensorFlow that supports newer typing-extensions:
```bash
pip install --upgrade tensorflow-macos  # for Apple Silicon Macs
# or
pip install --upgrade tensorflow
```

## Dependencies Explained

- **PyMuPDF (fitz)**: PDF text extraction and rendering for OCR
- **python-pptx**: PowerPoint slide text extraction
- **pytesseract**: OCR engine for image-based text extraction
- **Pillow**: Image processing for OCR

## Tesseract Installation

If you get tesseract-related errors, install Tesseract OCR:

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

## Integration with Node.js Backend

To integrate with your Node.js backend, you can call the Python script using child_process:

```javascript
const { spawn } = require('child_process');

function extractText(filePath) {
  return new Promise((resolve, reject) => {
    const python = spawn('python', ['extract_text.py', filePath], {
      cwd: __dirname
    });
    
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
        reject(new Error(`Python script exited with code ${code}`));
      }
    });
  });
}
```

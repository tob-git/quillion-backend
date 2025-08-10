# OpenAI API Key Setup Instructions

## Step 1: Get Your OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in to your OpenAI account (or create one)
3. Click "Create new secret key"
4. Give it a name like "Quiz Backend"
5. Copy the key (it starts with `sk-proj-` or `sk-`)

## Step 2: Add Your API Key

1. Open the `.env` file in this directory:
   ```bash
   nano .env
   ```

2. Replace `your-openai-api-key-here` with your actual API key:
   ```
   OPENAI_API_KEY=sk-proj-your-actual-key-here
   ```

3. Save the file (Ctrl+X, then Y, then Enter in nano)

## Step 3: Test the Integration

```bash
# Activate virtual environment
source venv/bin/activate

# Test with a small document
python test_integration.py test_certificate.pdf

# Or test with your lecture PDF
python test_integration.py '/Users/mohamdtobgi/spring25/Lecture 02_Summer 2025.pdf'
```

## Expected Output

The test will:
1. ✅ Verify your API key is configured
2. 🧪 Test single call strategy (small token count)
3. 🧪 Test chunked strategy (forced chunking)
4. 📊 Show generated questions and metadata
5. 🔍 Compare both strategies

## Troubleshooting

### "API key not configured"
- Make sure you edited `.env` and replaced the placeholder
- The key should start with `sk-`

### "Rate limit exceeded" 
- Wait a few minutes and try again
- OpenAI has rate limits for new accounts

### "Insufficient credits"
- Check your OpenAI account billing
- New accounts usually get $5 free credits

### "File not found"
- Make sure the PDF path is correct
- Use quotes around paths with spaces


## Security Notes

- The `.env` file is already in `.gitignore` 
- Your API key will NOT be committed to git
- Keep your API key private and secure

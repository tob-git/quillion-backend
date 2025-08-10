#!/usr/bin/env python3
"""
Demo script showing the complete orchestration pipeline flow.
This demonstrates the structure without requiring OpenAI API key.
"""

import asyncio
import json
from pathlib import Path

# Import our pipeline modules
from extract_text import extract_document_text
from clean_text import clean_extracted_sections
from compress_notes import compress_sections
from orchestrate_pipeline import (
    estimate_tokens,
    concat_notes,
    chunk_notes,
    validate_and_normalize_questions,
    deduplicate_questions
)

async def demo_pipeline_flow(file_path: str):
    """
    Demonstrate the complete pipeline flow up to OpenAI call.
    
    Args:
        file_path: Path to document to process
    """
    print("="*80)
    print("DOCUMENT PROCESSING PIPELINE DEMONSTRATION")
    print("="*80)
    print(f"Processing: {Path(file_path).name}")
    print()
    
    try:
        # Step 1: Extract document text
        print("📄 STEP 1: Extracting text from document...")
        raw_data = extract_document_text(file_path)
        
        doc_info = raw_data.get("doc", {})
        sections = raw_data.get("sections", [])
        
        print(f"   ✅ Extracted {len(sections)} sections")
        print(f"   📊 Document: {doc_info.get('title', 'Unknown')}")
        print(f"   📄 Pages: {doc_info.get('pages', 0)}")
        print()
        
        # Step 2: Clean sections
        print("🧹 STEP 2: Cleaning extracted sections...")
        cleaned_sections = clean_extracted_sections(sections)
        
        print(f"   ✅ Cleaned {len(cleaned_sections)} sections (removed {len(sections) - len(cleaned_sections)})")
        print()
        
        # Step 3: Compress to study notes
        print("📝 STEP 3: Compressing to study notes...")
        notes_data = compress_sections(cleaned_sections)
        
        notes = notes_data.get("notes", [])
        global_keywords = notes_data.get("global_keywords", [])
        
        print(f"   ✅ Generated {len(notes)} study note sections")
        print(f"   🔑 Global keywords: {len(global_keywords)} identified")
        print()
        
        # Step 4: Token analysis and strategy selection
        print("🎯 STEP 4: Token analysis and strategy selection...")
        
        # Calculate token counts
        raw_tokens = sum(estimate_tokens(s.get("text", "")) for s in cleaned_sections)
        notes_text = concat_notes(notes_data)
        notes_tokens = estimate_tokens(notes_text)
        
        print(f"   📊 Raw text tokens: {raw_tokens:,}")
        print(f"   📊 Notes tokens: {notes_tokens:,}")
        
        # Strategy selection
        single_call_limit = 6000
        if notes_tokens <= single_call_limit:
            strategy = "single"
            chunks_count = 1
            print(f"   🎯 Strategy: SINGLE CALL (notes fit in {single_call_limit:,} token limit)")
        else:
            strategy = "chunked"
            note_chunks = chunk_notes(notes_data, chunk_target_tokens=1500)
            chunks_count = len(note_chunks)
            print(f"   🎯 Strategy: CHUNKED MAP-REDUCE ({chunks_count} chunks)")
            
            # Show chunk breakdown
            for i, chunk in enumerate(note_chunks):
                chunk_text = concat_notes(chunk)
                chunk_tokens = estimate_tokens(chunk_text)
                print(f"      Chunk {i+1}: {len(chunk['notes'])} notes, ~{chunk_tokens} tokens")
        
        print()
        
        # Step 5: Show what would be sent to OpenAI
        print("🤖 STEP 5: OpenAI prompt preparation...")
        
        if strategy == "single":
            print("   📤 Would send single prompt with all notes:")
            print(f"      - Notes text: {len(notes_text)} characters")
            print(f"      - Estimated tokens: {notes_tokens}")
            print(f"      - Request: Generate up to 8 MCQ + 4 short questions")
        else:
            print("   📤 Would send chunked prompts:")
            note_chunks = chunk_notes(notes_data, chunk_target_tokens=1500)
            for i, chunk in enumerate(note_chunks):
                chunk_text = concat_notes(chunk)
                chunk_tokens = estimate_tokens(chunk_text)
                print(f"      Map {i+1}: {chunk_tokens} tokens → 2 MCQ + 1 short")
            print(f"      Reduce: Merge {chunks_count} partial results → 8 MCQ + 4 short")
        
        print()
        
        # Step 6: Sample content preview
        print("👀 STEP 6: Content preview...")
        
        print("   📋 Sample study notes (first 500 chars):")
        preview = notes_text[:500] + "..." if len(notes_text) > 500 else notes_text
        print("   " + "─" * 60)
        for line in preview.split('\n')[:10]:  # First 10 lines
            print(f"   {line}")
        if len(notes_text) > 500:
            print("   ...")
        print("   " + "─" * 60)
        print()
        
        # Step 7: Show global keywords
        if global_keywords:
            print("   🔑 Top global keywords:")
            keyword_list = global_keywords if isinstance(global_keywords, list) else []
            for i, kw in enumerate(keyword_list[:10]):  # Show top 10
                if isinstance(kw, tuple):
                    word, score = kw
                    print(f"      {i+1:2d}. {word} ({score:.3f})")
                else:
                    print(f"      {i+1:2d}. {kw}")
        print()
        
        # Step 8: Mock question generation result
        print("✨ STEP 8: Mock question generation result...")
        
        mock_result = {
            "jobId": "demo1234",
            "status": "done",
            "questions": {
                "mcq": [
                    {
                        "id": "q_mock001",
                        "question": f"Based on the document '{doc_info.get('title', 'content')}', what is a key concept discussed?",
                        "options": [
                            "Option A (example)",
                            "Option B (example)", 
                            "Option C (example)",
                            "Option D (example)"
                        ],
                        "answerIndex": 1,
                        "explanation": "This is a mock explanation based on the document content."
                    }
                ],
                "short": [
                    {
                        "id": "s_mock001",
                        "prompt": f"Explain a main topic from the document '{doc_info.get('title', 'content')}'.",
                        "expectedKeywords": [word for word, _ in (global_keywords[:3] if global_keywords else [])] or ["example", "keywords"]
                    }
                ]
            },
            "meta": {
                "sourceFile": doc_info.get("title", Path(file_path).name),
                "pages": doc_info.get("pages", 0),
                "tokenCounts": {
                    "raw": raw_tokens,
                    "notes": notes_tokens,
                    "promptIn": notes_tokens + 200,  # Estimated prompt overhead
                    "modelOut": 400  # Estimated response tokens
                },
                "strategy": strategy,
                "chunks": chunks_count
            }
        }
        
        print("   🎯 Mock result structure:")
        print(json.dumps(mock_result, indent=4, ensure_ascii=False))
        print()
        
        print("="*80)
        print("✅ DEMONSTRATION COMPLETE!")
        print("="*80)
        print()
        print("To run with actual OpenAI question generation:")
        print("1. Set environment variable: export OPENAI_API_KEY='your-key'")
        print("2. Run: python orchestrate_pipeline.py", file_path)
        print()
        
        return mock_result
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        return None

async def main():
    """Main demo function."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python demo_orchestration.py <document_path>")
        print("Example: python demo_orchestration.py test_certificate.pdf")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    await demo_pipeline_flow(file_path)

if __name__ == "__main__":
    asyncio.run(main())

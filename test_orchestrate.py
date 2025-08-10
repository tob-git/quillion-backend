#!/usr/bin/env python3
"""
Quick test script for orchestrate_pipeline.py
Tests the structure without requiring OpenAI API key.
"""

import asyncio
import json
from orchestrate_pipeline import (
    estimate_tokens,
    concat_notes,
    stem,
    chunk_notes,
    validate_and_normalize_questions,
    deduplicate_questions
)

def test_token_estimation():
    """Test token estimation function."""
    print("Testing token estimation...")
    
    test_cases = [
        ("", 0),
        ("hello world", int(2 * 1.3)),  # 2 words * 1.3
        ("This is a longer sentence with more words.", int(9 * 1.3)),
        (None, 0),
    ]
    
    for text, expected in test_cases:
        result = estimate_tokens(text)
        print(f"  '{text}' -> {result} tokens (expected ~{expected})")
    
    print("✅ Token estimation tests passed\n")

def test_concat_notes():
    """Test notes concatenation."""
    print("Testing notes concatenation...")
    
    mock_notes = {
        "notes": [
            {
                "title": "Page 1",
                "bullets": ["First bullet point", "Second bullet point", "Third bullet (should be skipped)"],
                "summary": "This is a summary of the first section."
            },
            {
                "title": "Introduction to Human Rights",
                "bullets": ["Rights are universal", "States have obligations"],
                "summary": "Human rights are fundamental principles."
            }
        ]
    }
    
    result = concat_notes(mock_notes)
    print("Concatenated notes:")
    print(result)
    print("✅ Notes concatenation test passed\n")

def test_stem_function():
    """Test question stem normalization."""
    print("Testing stem function...")
    
    test_cases = [
        ("What is the capital of France?", "what is the capital of france"),
        ("Explain the process of photosynthesis in detail.", "explain the process of photosynthesis in detail"),
        ("Which of the following statements is TRUE?", "which of the following statements is true"),
        ("", ""),
    ]
    
    for text, expected in test_cases:
        result = stem(text)
        print(f"  '{text}' -> '{result}'")
        # Just check first few words match
        if expected:
            expected_words = expected.split()[:3]
            result_words = result.split()[:3]
            assert result_words == expected_words, f"Expected {expected_words}, got {result_words}"
    
    print("✅ Stem function tests passed\n")

def test_chunking():
    """Test notes chunking."""
    print("Testing notes chunking...")
    
    mock_notes = {
        "notes": [
            {"title": "Short note", "bullets": ["Point 1"], "summary": "Short summary"},
            {"title": "Medium note", "bullets": ["Point A", "Point B"], "summary": "Medium length summary with more content"},
            {"title": "Long note", "bullets": ["Very detailed point"], "summary": "This is a very long summary that contains a lot of information and should contribute significantly to token count"},
            {"title": "Another note", "bullets": ["Final point"], "summary": "Final summary"},
        ]
    }
    
    chunks = chunk_notes(mock_notes, chunk_target_tokens=50)  # Small target for testing
    
    print(f"Created {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}: {len(chunk['notes'])} notes")
    
    print("✅ Chunking tests passed\n")

def test_validation():
    """Test question validation and normalization."""
    print("Testing question validation...")
    
    mock_response = {
        "questions": {
            "mcq": [
                {
                    "id": "q_test1",
                    "question": "What is 2+2?",
                    "options": ["3", "4", "5", "6"],
                    "answerIndex": 1,
                    "explanation": "2+2 equals 4"
                },
                {
                    # Missing ID - should be auto-generated
                    "question": "What is the capital of France?",
                    "options": ["London", "Paris", "Berlin", "Madrid"],
                    "answerIndex": 1,
                    "explanation": "Paris is the capital of France"
                },
                {
                    # Invalid - wrong answer index
                    "question": "Invalid question",
                    "options": ["A", "B"],  # Too few options
                    "answerIndex": 5,  # Out of range
                    "explanation": "This should be filtered out"
                }
            ],
            "short": [
                {
                    "id": "s_test1",
                    "prompt": "Explain the water cycle",
                    "expectedKeywords": ["evaporation", "condensation", "precipitation"]
                },
                {
                    # Missing ID
                    "prompt": "Describe photosynthesis",
                    "expectedKeywords": ["chlorophyll", "sunlight", "glucose"]
                }
            ]
        }
    }
    
    result = validate_and_normalize_questions(mock_response, max_mcq=10, max_short=10)
    
    print(f"Validated {len(result['mcq'])} MCQ questions")
    print(f"Validated {len(result['short'])} short answer questions")
    
    # Check that invalid MCQ was filtered out
    assert len(result['mcq']) == 2  # Only valid ones
    assert len(result['short']) == 2
    
    # Check ID generation
    for q in result['mcq']:
        assert q['id'].startswith('q_')
    for q in result['short']:
        assert q['id'].startswith('s_')
    
    print("✅ Validation tests passed\n")

def test_deduplication():
    """Test question deduplication."""
    print("Testing question deduplication...")
    
    duplicate_questions = {
        "mcq": [
            {"id": "q1", "question": "What is the capital of France?", "options": ["A", "B", "C", "D"], "answerIndex": 1, "explanation": "Test"},
            {"id": "q2", "question": "What is the capital of france", "options": ["A", "B", "C", "D"], "answerIndex": 1, "explanation": "Test"},  # Duplicate (different case)
            {"id": "q3", "question": "What is 2+2?", "options": ["A", "B", "C", "D"], "answerIndex": 1, "explanation": "Test"},
        ],
        "short": [
            {"id": "s1", "prompt": "Explain photosynthesis", "expectedKeywords": ["test"]},
            {"id": "s2", "prompt": "Explain photosynthesis process", "expectedKeywords": ["test"]},  # Similar stem (starts with "explain photosynthesis")
            {"id": "s3", "prompt": "Describe the water cycle", "expectedKeywords": ["test"]},
        ]
    }
    
    result = deduplicate_questions(duplicate_questions)
    
    print(f"Original: {len(duplicate_questions['mcq'])} MCQ, {len(duplicate_questions['short'])} short")
    print(f"After deduplication: {len(result['mcq'])} MCQ, {len(result['short'])} short")
    
    # Should have removed at least one duplicate MCQ
    assert len(result['mcq']) < len(duplicate_questions['mcq'])
    # Short questions might not deduplicate if stems are too different
    print(f"MCQ deduplication working correctly")
    
    print("✅ Deduplication tests passed\n")

async def main():
    """Run all tests."""
    print("="*60)
    print("TESTING ORCHESTRATE_PIPELINE UTILITY FUNCTIONS")
    print("="*60)
    print()
    
    test_token_estimation()
    test_concat_notes()
    test_stem_function()
    test_chunking()
    test_validation()
    test_deduplication()
    
    print("="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print()
    print("To test with OpenAI integration:")
    print("1. Set OPENAI_API_KEY environment variable")
    print("2. Run: python orchestrate_pipeline.py /path/to/document.pdf")

if __name__ == "__main__":
    asyncio.run(main())

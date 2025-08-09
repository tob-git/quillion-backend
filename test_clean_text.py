#!/usr/bin/env python3
"""
Test script for clean_text.py module.
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clean_text import clean_extracted_sections


def test_cleaning_functionality():
    """Test the text cleaning with various scenarios."""
    print("Testing clean_text module...")
    
    # Test data with various cleaning scenarios
    test_sections = [
        {
            "id": "s1",
            "title": "Page 1",
            "text": "Header text\nPhotosynthesis is the process by which plants convert light energy into chemical energy.\nThis is an important biological process.\nPage 1\n1\nFooter text"
        },
        {
            "id": "s2",
            "title": "Page 2", 
            "text": "Header text\nATP is the energy currency of the cell.\nIt powers most cellular processes.\nPage 2\n2\nFooter text"
        },
        {
            "id": "s3",
            "title": "References",
            "text": "Reference 1: Smith, J. (2020)\nReference 2: Jones, A. (2019)\nhttps://example.com/paper1"
        },
        {
            "id": "s4",
            "title": "Chapter 3",
            "text": "Mitochondria are the powerhouses of the cell.\n\n\nThey produce ATP through cellular respiration.\n\nCopyright © 2023 All rights reserved.\nTable of Contents"
        },
        {
            "id": "s5", 
            "title": "Long Content",
            "text": "This is a very long paragraph that exceeds 1000 characters and should be trimmed to keep only the first and last sentences. " * 20 + "This is the last sentence of the long paragraph.\n\nThis is a normal paragraph that should remain unchanged."
        }
    ]
    
    print(f"\nBefore cleaning: {len(test_sections)} sections")
    print("Section titles:", [s["title"] for s in test_sections])
    
    # Clean the sections
    cleaned_sections = clean_extracted_sections(test_sections)
    
    print(f"\nAfter cleaning: {len(cleaned_sections)} sections")
    print("Remaining section titles:", [s["title"] for s in cleaned_sections])
    
    # Show cleaned content
    print("\n=== CLEANED SECTIONS ===")
    for section in cleaned_sections:
        print(f"\n[{section['id']}] {section['title']}:")
        # Show full text for the long content section to demonstrate trimming
        if section['title'] == 'Long Content':
            print(f"Text: {section['text']}")
        else:
            print(f"Text: {section['text'][:200]}{'...' if len(section['text']) > 200 else ''}")
    
    print("\n✅ Text cleaning test completed!")


def test_with_certificate_example():
    """Test with a certificate-like text similar to what was extracted."""
    print("\n" + "="*50)
    print("Testing with certificate-like content...")
    
    certificate_sections = [
        {
            "id": "cert1",
            "title": "Page 1",
            "text": """Header Information
Aug 4, 2025
Mohammed Khaled Ali
Introduction to Financial Accounting
an online non-credit course authorized by University of Pennsylvania and offered through
Coursera
has successfully completed
Professor Brian J. Bushee 
Gilbert and Shelley Harrison Professor 
Wharton School, University of Pennsylvania
Verify at: 
coursera.org/verify/KXSHSGNDHHHB 
Coursera has confirmed the identity of this individual and
their participation in the course.
The online course named in this certificate may draw on material from courses taught on-campus, but it is not equivalent to an on-campus course. Participation in this online course does not constitute enrollment at the
University of Pennsylvania. This certificate does not confer a University grade, course credit or degree, and it does not verify the identity of the learner.
© 2023 Coursera Inc. All rights reserved.
Page 1
1"""
        }
    ]
    
    cleaned = clean_extracted_sections(certificate_sections)
    
    print(f"\nCleaned certificate content:")
    if cleaned:
        print(f"[{cleaned[0]['id']}] {cleaned[0]['title']}:")
        print(cleaned[0]['text'])
    
    print("\n✅ Certificate cleaning test completed!")


if __name__ == "__main__":
    test_cleaning_functionality()
    test_with_certificate_example()

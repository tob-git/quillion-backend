#!/usr/bin/env python3
"""
Test script for compress_notes.py module.
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from compress_notes import compress_sections


def test_compression_functionality():
    """Test the note compression with various scenarios."""
    print("Testing compress_notes module...")
    
    # Test data with bullet points, emphasis, and various content types
    test_sections = [
        {
            "id": "s1",
            "title": "Photosynthesis — Overview",
            "text": "• Occurs in chloroplasts\n- Light-dependent reactions produce ATP and NADPH.\n• The Calvin cycle fixes CO2 into glucose.\n**Chlorophyll** absorbs light energy. Photosynthesis is the process by which plants convert light energy into chemical energy stored as glucose."
        },
        {
            "id": "s2", 
            "title": "Page 2",
            "text": "Cellular respiration occurs in the mitochondria. It uses oxygen to produce ATP through a series of chemical reactions. The electron transport chain is the final stage of cellular respiration."
        },
        {
            "id": "s3",
            "title": "DNA Structure",
            "text": "1. DNA is a double helix structure\n2. Contains four bases: A, T, G, C\n3. Base pairing follows Chargaff's rules\nDNA replication is *semiconservative*. Each strand serves as a template for the new strand."
        },
        {
            "id": "s4",
            "title": "Very Short",
            "text": "RNA is important."
        }
    ]
    
    print(f"\nInput: {len(test_sections)} sections")
    
    # Compress the sections
    result = compress_sections(test_sections)
    
    print(f"\nOutput: {result['meta']['sections']} notes")
    print(f"Total words: {result['meta']['total_words']}")
    print(f"Global keywords: {result['global_keywords']}")
    
    # Show each compressed note
    print("\n=== COMPRESSED NOTES ===")
    for note in result['notes']:
        print(f"\n[{note['id']}] {note['title']} ({note['wordCount']} words)")
        print(f"Keywords: {', '.join(note['keywords'])}")
        if note['bullets']:
            print(f"Bullets: {note['bullets']}")
        print(f"Summary: {note['summary']}")
    
    print("\n✅ Compression test completed!")
    return result


def test_with_real_certificate_content():
    """Test with certificate-like content."""
    print("\n" + "="*60)
    print("Testing with certificate-like content...")
    
    # Simulate cleaned certificate content
    certificate_sections = [
        {
            "id": "cert1",
            "title": "Certificate of Completion",
            "text": "Mohammed Khaled Ali has successfully completed Introduction to Financial Accounting, an online non-credit course authorized by University of Pennsylvania and offered through Coursera. Professor Brian J. Bushee served as instructor. The course covered fundamental accounting principles, financial statements, and basic financial analysis techniques."
        }
    ]
    
    result = compress_sections(certificate_sections, min_words=30, max_words=80)
    
    print(f"\nCompressed certificate:")
    if result['notes']:
        note = result['notes'][0]
        print(f"[{note['id']}] {note['title']} ({note['wordCount']} words)")
        print(f"Keywords: {', '.join(note['keywords'])}")
        print(f"Summary: {note['summary']}")
    
    print("\n✅ Certificate compression test completed!")


def test_edge_cases():
    """Test edge cases like empty sections, very short content, etc."""
    print("\n" + "="*60)
    print("Testing edge cases...")
    
    edge_cases = [
        {"id": "empty", "title": "Empty", "text": ""},
        {"id": "short", "title": "Too Short", "text": "Very short."},
        {"id": "bullets_only", "title": "Bullets Only", "text": "• First point\n• Second point\n• Third point"},
        {"id": "no_bullets", "title": "No Bullets", "text": "This is a longer paragraph without any bullet points. It discusses various topics and contains multiple sentences that should be processed for keyword extraction and summarization."}
    ]
    
    result = compress_sections(edge_cases, min_words=25, max_words=60)
    
    print(f"\nEdge cases result: {result['meta']['sections']} notes from {len(edge_cases)} inputs")
    for note in result['notes']:
        print(f"\n[{note['id']}] {note['title']} ({note['wordCount']} words)")
        print(f"Summary: {note['summary']}")
    
    print("\n✅ Edge cases test completed!")


if __name__ == "__main__":
    test_compression_functionality()
    test_with_real_certificate_content()
    test_edge_cases()

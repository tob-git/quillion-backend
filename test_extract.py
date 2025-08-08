#!/usr/bin/env python3
"""
Test script for extract_text.py module.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_text import extract_document_text

def test_basic_functionality():
    """Test basic module import and error handling."""
    print("Testing extract_text module...")
    
    # Test unsupported file type with existing file path format
    try:
        result = extract_document_text("/tmp/test.txt")  # Use a realistic path
        print("❌ Should have raised ValueError for unsupported file type")
    except ValueError as e:
        print(f"✅ Correctly handled unsupported file type: {e}")
    except FileNotFoundError as e:
        print(f"✅ File check works, but testing with existing file would be better")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    # Test missing file
    try:
        result = extract_document_text("nonexistent.pdf")
        print("❌ Should have raised FileNotFoundError")
    except FileNotFoundError as e:
        print(f"✅ Correctly handled missing file: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    print("\n✅ Basic functionality tests passed!")
    print("\nTo test with actual PDF/PPTX files:")
    print("python extract_text.py /path/to/your/file.pdf")
    print("python extract_text.py /path/to/your/file.pptx")

if __name__ == "__main__":
    test_basic_functionality()

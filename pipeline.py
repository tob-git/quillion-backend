#!/usr/bin/env python3
"""
Complete document processing pipeline.
Extracts text from PDF/PPTX -> Cleans text -> Compresses to study notes -> Saves to text file.
"""

import sys
import json
import tempfile
import os
from pathlib import Path

# Import our modules
from extract_text import extract_document_text
from clean_text import clean_extracted_sections
from compress_notes import compress_sections

def run_pipeline(input_file_path, output_file_path):
    """
    Run the complete pipeline on a document and save results to a text file.
    
    Args:
        input_file_path (str): Path to the input document (PDF or PPTX)
        output_file_path (str): Path to save the final study notes text file
    """
    try:
        print(f"Starting pipeline for: {input_file_path}")
        
        # Step 1: Extract text
        print("Step 1: Extracting text...")
        extracted_data = extract_document_text(input_file_path)
        print(f"Extracted {len(extracted_data['sections'])} sections")
        
        # Step 2: Clean text
        print("Step 2: Cleaning text...")
        cleaned_sections = clean_extracted_sections(extracted_data['sections'])
        cleaned_data = {"sections": cleaned_sections}
        print(f"Cleaned {len(cleaned_data['sections'])} sections")
        
        # Step 3: Compress to study notes
        print("Step 3: Compressing to study notes...")
        compressed_data = compress_sections(cleaned_data['sections'])
        # Convert notes to sections for consistency
        compressed_data['sections'] = compressed_data.pop('notes', [])
        print(f"Generated study notes with {len(compressed_data['sections'])} sections")
        
        # Step 4: Format and save to text file
        print("Step 4: Formatting and saving to text file...")
        formatted_text = format_study_notes(compressed_data)
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        
        print(f"Pipeline complete! Study notes saved to: {output_file_path}")
        return True
        
    except Exception as e:
        print(f"Pipeline failed: {str(e)}")
        return False

def format_study_notes(compressed_data):
    """
    Format the compressed study notes into readable text.
    
    Args:
        compressed_data (dict): The compressed data from compress_notes
        
    Returns:
        str: Formatted text for the study notes
    """
    lines = []
    
    # Add header
    lines.append("=" * 80)
    lines.append("STUDY NOTES")
    lines.append("=" * 80)
    lines.append("")
    
    # Add global summary if available
    if compressed_data.get('global_summary'):
        lines.append("DOCUMENT SUMMARY:")
        lines.append("-" * 40)
        lines.append(compressed_data['global_summary'])
        lines.append("")
    
    # Add global keywords if available
    if compressed_data.get('global_keywords'):
        lines.append("KEY TERMS:")
        lines.append("-" * 40)
        # Handle different keyword formats
        global_kw = compressed_data['global_keywords']
        if isinstance(global_kw, list) and len(global_kw) > 0:
            if isinstance(global_kw[0], tuple):
                keywords_text = ", ".join([f"{word} ({score:.2f})" for word, score in global_kw])
            else:
                keywords_text = ", ".join([str(kw) for kw in global_kw])
        else:
            keywords_text = str(global_kw)
        lines.append(keywords_text)
        lines.append("")
    
    # Process each section
    for i, section in enumerate(compressed_data['sections'], 1):
        lines.append(f"SECTION {i}: {section.get('title', f'Section {i}')}")
        lines.append("=" * 60)
        lines.append("")
        
        # Add section summary
        if section.get('summary'):
            lines.append("Summary:")
            lines.append(section['summary'])
            lines.append("")
        
        # Add keywords
        if section.get('keywords'):
            lines.append("Keywords:")
            # Handle different keyword formats
            section_kw = section['keywords']
            if isinstance(section_kw, list) and len(section_kw) > 0:
                if isinstance(section_kw[0], tuple):
                    keywords_text = ", ".join([f"{word} ({score:.2f})" for word, score in section_kw])
                else:
                    keywords_text = ", ".join([str(kw) for kw in section_kw])
            else:
                keywords_text = str(section_kw)
            lines.append(keywords_text)
            lines.append("")
        
        # Add bullet points
        if section.get('bullets'):
            lines.append("Key Points:")
            for bullet in section['bullets']:
                lines.append(f"• {bullet}")
            lines.append("")
        
        lines.append("-" * 60)
        lines.append("")
    
    return "\n".join(lines)

def main():
    if len(sys.argv) != 3:
        print("Usage: python pipeline.py <input_document> <output_text_file>")
        print("Example: python pipeline.py document.pdf study_notes.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Run the pipeline
    success = run_pipeline(input_file, output_file)
    
    if success:
        print(f"\n✅ Success! Study notes saved to: {output_file}")
        sys.exit(0)
    else:
        print(f"\n❌ Pipeline failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Text cleaning module for extracted document sections.

Provides deterministic cleaning of text sections without using LLMs.
Removes headers, footers, boilerplate, and other noise from extracted text.
"""

import re
from typing import List, Dict, Set
from collections import Counter


# Precompiled regex patterns
PAGE_NUMBER_PATTERN = re.compile(r'^\s*page\s*\d+\s*$', re.IGNORECASE)
STANDALONE_NUMBER_PATTERN = re.compile(r'^\s*\d+\s*$')
HEADER_FOOTER_PATTERN = re.compile(r'^\s*(header|footer).*', re.IGNORECASE)
REFERENCE_START_PATTERN = re.compile(r'^(references|bibliography|appendix)', re.IGNORECASE)
CITATION_URL_PATTERN = re.compile(r'(https?://|www\.|doi:|isbn:|issn:|\[\d+\]|^\d+\.)', re.IGNORECASE)
COURSE_CODE_PATTERN = re.compile(r'\b[A-Za-z]{3}\d{3}\b', re.IGNORECASE)
DR_NAME_PATTERN = re.compile(r'\bdr\.?\s+[a-zA-Z]+(?:\s+[a-zA-Z]+)*', re.IGNORECASE)
BOILERPLATE_PATTERNS = [
    re.compile(r'all rights reserved', re.IGNORECASE),
    re.compile(r'©', re.IGNORECASE),
    re.compile(r'copyright', re.IGNORECASE),
    re.compile(r'terms of use', re.IGNORECASE),
    re.compile(r'table of contents', re.IGNORECASE),
]
MULTIPLE_SPACES_PATTERN = re.compile(r'\s+')
MULTIPLE_NEWLINES_PATTERN = re.compile(r'\n\s*\n')


def clean_extracted_sections(sections: List[Dict]) -> List[Dict]:
    """
    Cleans a list of extracted sections in place (deterministic, no LLM).
    Returns a new list of cleaned section dicts in the same shape:
        [ { "id": str, "title": str, "text": str }, ... ]
    """
    if not sections:
        return []
    
    print(f"Starting cleanup of {len(sections)} sections...")
    
    # Step 1: Identify global boilerplate (lines that appear in 80%+ of sections)
    global_boilerplate = _identify_global_boilerplate(sections)
    
    cleaned_sections = []
    
    for section in sections:
        # Make a copy to avoid mutating original
        cleaned_section = {
            "id": section["id"],
            "title": section.get("title", "Untitled Section").strip() or "Untitled Section",
            "text": section.get("text", "")
        }
        
        # Step 2: Check if this is a references/appendix section to drop entirely
        if _should_drop_section(cleaned_section):
            print(f"Dropped section {cleaned_section['id']}: {cleaned_section['title']} (references/appendix)")
            continue
        
        # Step 3: Clean the text
        text = cleaned_section["text"]
        
        # Remove headers/footers/page numbers
        text = _remove_headers_footers_page_numbers(text)
        
        # Remove global boilerplate
        text = _remove_global_boilerplate(text, global_boilerplate)
        
        # Remove boilerplate patterns
        text = _remove_boilerplate_patterns(text)
        
        # Remove course codes (3 letters + 3 digits)
        text = _remove_course_codes(text)
        
        # Remove Dr. names
        text = _remove_dr_names(text)
        
        # Collapse whitespace
        text = _collapse_whitespace(text)
        
        # Remove duplicate lines within section
        text = _remove_duplicate_lines(text)
        
        # Remove references/appendix if they appear mid-section
        text = _truncate_at_references(text, cleaned_section["id"])
        
        # Trim extreme-long paragraphs
        text = _trim_long_paragraphs(text)
        
        # Final cleanup
        text = _collapse_whitespace(text)
        
        # Only keep section if it has meaningful content
        if text.strip():
            cleaned_section["text"] = text.strip()
            cleaned_sections.append(cleaned_section)
        else:
            print(f"Dropped section {cleaned_section['id']}: {cleaned_section['title']} (empty after cleaning)")
    
    print(f"Cleanup complete: {len(cleaned_sections)} sections remaining")
    return cleaned_sections


def _identify_global_boilerplate(sections: List[Dict]) -> Set[str]:
    """Identify lines that appear in 80%+ of sections."""
    if len(sections) < 2:
        return set()
    
    line_counts = Counter()
    total_sections = len(sections)
    
    for section in sections:
        text = section.get("text", "")
        lines = set(line.strip() for line in text.split('\n') if line.strip())
        for line in lines:
            line_counts[line] += 1
    
    threshold = total_sections * 0.8
    boilerplate = {line for line, count in line_counts.items() if count >= threshold}
    
    if boilerplate:
        print(f"Identified {len(boilerplate)} global boilerplate lines")
    
    return boilerplate


def _should_drop_section(section: Dict) -> bool:
    """Check if section should be dropped entirely (references/appendix)."""
    title = section.get("title", "").lower()
    text = section.get("text", "").lower()
    
    return (REFERENCE_START_PATTERN.match(title) or 
            REFERENCE_START_PATTERN.match(text))


def _remove_headers_footers_page_numbers(text: str) -> str:
    """Remove headers, footers, and page numbers."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Skip page numbers, standalone numbers, and obvious headers/footers
        if (PAGE_NUMBER_PATTERN.match(line) or 
            STANDALONE_NUMBER_PATTERN.match(line) or 
            HEADER_FOOTER_PATTERN.match(line)):
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _remove_global_boilerplate(text: str, boilerplate: Set[str]) -> str:
    """Remove globally identified boilerplate lines."""
    if not boilerplate:
        return text
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        if line.strip() not in boilerplate:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _remove_boilerplate_patterns(text: str) -> str:
    """Remove lines containing boilerplate patterns."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        should_keep = True
        for pattern in BOILERPLATE_PATTERNS:
            if pattern.search(line):
                should_keep = False
                break
        
        if should_keep:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _remove_course_codes(text: str) -> str:
    """Remove course codes (3 letters + 3 digits format like ASU111, CSE101)."""
    # Remove course codes from the text
    return COURSE_CODE_PATTERN.sub('', text)


def _remove_dr_names(text: str) -> str:
    """Remove Dr. names (like 'Dr. Mohamed', 'Dr Mohamed Kohail', etc.)."""
    # Remove Dr. names from the text
    return DR_NAME_PATTERN.sub('', text)


def _collapse_whitespace(text: str) -> str:
    """Normalize whitespace: multiple spaces → single space, multiple newlines → single newline, but preserve paragraph breaks."""
    # First normalize spaces within lines
    lines = text.split('\n')
    normalized_lines = []
    
    for line in lines:
        # Strip leading/trailing whitespace and normalize internal spaces
        normalized_line = MULTIPLE_SPACES_PATTERN.sub(' ', line.strip())
        normalized_lines.append(normalized_line)
    
    # Rejoin and normalize multiple newlines, but preserve double newlines for paragraph breaks
    text = '\n'.join(normalized_lines)
    
    # Replace 3+ newlines with double newlines (preserve paragraph breaks)
    # This regex matches 3 or more consecutive newlines and replaces with exactly 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


def _remove_duplicate_lines(text: str) -> str:
    """Remove consecutive duplicate lines within the text."""
    lines = text.split('\n')
    cleaned_lines = []
    prev_line = None
    
    for line in lines:
        if line != prev_line:
            cleaned_lines.append(line)
        prev_line = line
    
    return '\n'.join(cleaned_lines)


def _truncate_at_references(text: str, section_id: str) -> str:
    """Truncate section if references/bibliography appears mid-text with citations following."""
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        if REFERENCE_START_PATTERN.match(line.strip()):
            # Check if >50% of remaining lines are citations/URLs
            remaining_lines = lines[i+1:]
            if len(remaining_lines) > 0:
                citation_count = sum(1 for rl in remaining_lines 
                                   if CITATION_URL_PATTERN.search(rl))
                citation_ratio = citation_count / len(remaining_lines)
                
                if citation_ratio > 0.5:
                    print(f"Truncated section {section_id} at references (line {i+1})")
                    return '\n'.join(lines[:i])
    
    return text


def _trim_long_paragraphs(text: str) -> str:
    """Trim paragraphs longer than 1000 characters to first and last sentence."""
    paragraphs = text.split('\n\n')
    trimmed_paragraphs = []
    
    for paragraph in paragraphs:
        if len(paragraph) > 1000:
            sentences = _split_into_sentences(paragraph)
            if len(sentences) > 2:
                # Keep first and last sentence
                trimmed = f"{sentences[0]} {sentences[-1]}"
                trimmed_paragraphs.append(trimmed)
            else:
                # If 2 or fewer sentences, keep as is
                trimmed_paragraphs.append(paragraph)
        else:
            trimmed_paragraphs.append(paragraph)
    
    return '\n\n'.join(trimmed_paragraphs)


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences (simple approach)."""
    # Split on sentence endings: . ! ? followed by whitespace or end of string
    sentence_pattern = re.compile(r'[.!?]+(?:\s+|$)')
    sentences = sentence_pattern.split(text.strip())
    
    # Remove empty sentences and strip whitespace
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences


def main():
    """CLI interface for testing."""
    import json
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python clean_text.py <json_file>")
        print("       or")
        print("       echo '[{\"id\":\"s1\",\"title\":\"Test\",\"text\":\"Sample text\"}]' | python clean_text.py -")
        print("       or")
        print("       python extract_text.py file.pdf | python clean_text.py -")
        sys.exit(1)
    
    if sys.argv[1] == '-':
        # Read from stdin
        import sys
        data = sys.stdin.read()
    else:
        # Read from file
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            data = f.read()
    
    try:
        input_data = json.loads(data)
        
        # Handle both formats: direct sections array or extract_text.py output format
        if isinstance(input_data, list):
            sections = input_data
        elif isinstance(input_data, dict) and "sections" in input_data:
            sections = input_data["sections"]
        else:
            raise ValueError("Input must be a list of sections or a dict with 'sections' key")
        
        cleaned_sections = clean_extracted_sections(sections)
        
        # Return in the same format as input
        if isinstance(input_data, list):
            print(json.dumps(cleaned_sections, indent=2, ensure_ascii=False))
        else:
            # Preserve the original structure but with cleaned sections
            output = input_data.copy()
            output["sections"] = cleaned_sections
            print(json.dumps(output, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

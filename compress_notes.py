#!/usr/bin/env python3
"""
Text compression module for converting cleaned sections into structured study notes.

Implements TF-IDF keyword extraction, bullet point detection, and automatic summarization
without using any external ML libraries or LLMs.
"""

import json
import math
import re
import sys
from collections import Counter, defaultdict
from typing import List, Dict, Set, Tuple, Any

# Debug flag for optional logging
DEBUG = False

# Compact English stopword set (essential words to filter out)
STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'by', 'for', 'from',
    'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to',
    'was', 'will', 'with', 'would', 'you', 'your', 'this', 'they', 'their',
    'them', 'these', 'those', 'than', 'then', 'there', 'when', 'where', 'who',
    'which', 'what', 'how', 'why', 'can', 'could', 'should', 'would', 'may',
    'might', 'must', 'shall', 'will', 'do', 'does', 'did', 'have', 'had',
    'having', 'am', 'is', 'are', 'was', 'were', 'being', 'been', 'get', 'got',
    'getting', 'give', 'given', 'giving', 'go', 'going', 'gone', 'make', 'made',
    'making', 'take', 'taken', 'taking', 'come', 'came', 'coming', 'know',
    'known', 'knowing', 'see', 'seen', 'seeing', 'look', 'looking', 'looked',
    'use', 'used', 'using', 'find', 'found', 'finding', 'work', 'worked',
    'working', 'call', 'called', 'calling', 'try', 'tried', 'trying', 'ask',
    'asked', 'asking', 'need', 'needed', 'needing', 'feel', 'felt', 'feeling',
    'become', 'became', 'becoming', 'leave', 'left', 'leaving', 'put', 'putting',
    'mean', 'meant', 'meaning', 'keep', 'kept', 'keeping', 'let', 'letting',
    'begin', 'began', 'beginning', 'seem', 'seemed', 'seeming', 'turn', 'turned',
    'turning', 'start', 'started', 'starting', 'show', 'showed', 'showing',
    'hear', 'heard', 'hearing', 'play', 'played', 'playing', 'run', 'ran',
    'running', 'move', 'moved', 'moving', 'live', 'lived', 'living', 'believe',
    'believed', 'believing', 'hold', 'held', 'holding', 'bring', 'brought',
    'bringing', 'happen', 'happened', 'happening', 'write', 'wrote', 'written',
    'writing', 'provide', 'provided', 'providing', 'sit', 'sat', 'sitting',
    'stand', 'stood', 'standing', 'lose', 'lost', 'losing', 'pay', 'paid',
    'paying', 'meet', 'met', 'meeting', 'include', 'included', 'including',
    'continue', 'continued', 'continuing', 'set', 'setting', 'learn', 'learned',
    'learning', 'change', 'changed', 'changing', 'lead', 'led', 'leading',
    'understand', 'understood', 'understanding', 'watch', 'watched', 'watching',
    'follow', 'followed', 'following', 'stop', 'stopped', 'stopping', 'create',
    'created', 'creating', 'speak', 'spoke', 'spoken', 'speaking', 'read',
    'reading', 'allow', 'allowed', 'allowing', 'add', 'added', 'adding',
    'spend', 'spent', 'spending', 'grow', 'grew', 'grown', 'growing', 'open',
    'opened', 'opening', 'walk', 'walked', 'walking', 'win', 'won', 'winning',
    'offer', 'offered', 'offering', 'remember', 'remembered', 'remembering',
    'love', 'loved', 'loving', 'consider', 'considered', 'considering'
}

# Precompiled regex patterns
BULLET_PATTERN = re.compile(r'^\s*[-•*·–—→>]\s+|^\s*\d+[\.\)]\s+')
EMPHASIS_PATTERN = re.compile(r'\*\*([^*]+)\*\*|\*([^*]+)\*|_([^_]+)_')
SENTENCE_PATTERN = re.compile(r'[.!?]+(?=\s|$)')
WORD_PATTERN = re.compile(r'\b\w+\b')
PARENTHETICAL_PATTERN = re.compile(r'\([^)]*\)')
TRAILING_CLAUSE_PATTERN = re.compile(r'[;—].*$')


def compress_sections(sections: List[Dict], *, min_words: int = 50, max_words: int = 120, top_k_keywords: int = 8) -> Dict:
    """
    Compress cleaned sections into short study notes (no LLM).
    """
    if DEBUG:
        print(f"Starting compression of {len(sections)} sections...")
    
    if not sections:
        return {
            "notes": [],
            "global_keywords": [],
            "meta": {"sections": 0, "total_words": 0}
        }
    
    # Process each section
    processed_sections = []
    all_documents = []  # For TF-IDF computation
    
    for section in sections:
        processed = _process_section(section)
        if processed:
            processed_sections.append(processed)
            all_documents.append(processed['tokens'])
    
    if not processed_sections:
        return {
            "notes": [],
            "global_keywords": [],
            "meta": {"sections": 0, "total_words": 0}
        }
    
    # Compute TF-IDF and extract keywords
    tf_idf_scores = _compute_tf_idf(all_documents)
    global_keywords = _extract_global_keywords(tf_idf_scores, processed_sections)
    
    # Generate final notes
    notes = []
    total_words = 0
    
    for i, processed in enumerate(processed_sections):
        section_keywords = _extract_section_keywords(
            processed, tf_idf_scores[i], top_k_keywords
        )
        
        summary = _generate_summary(
            processed, section_keywords, min_words, max_words
        )
        
        if summary.strip():  # Only include if summary is not empty
            word_count = word_count_func(summary)
            
            note = {
                "id": processed['id'],
                "title": processed['title'],
                "bullets": processed['bullets'],
                "keywords": section_keywords,
                "summary": summary,
                "wordCount": word_count
            }
            notes.append(note)
            total_words += word_count
    
    if DEBUG:
        print(f"Generated {len(notes)} notes with {total_words} total words")
    
    return {
        "notes": notes,
        "global_keywords": global_keywords,
        "meta": {
            "sections": len(notes),
            "total_words": total_words
        }
    }


def _process_section(section: Dict) -> Dict:
    """Process a single section to extract bullets, emphasis, and tokens."""
    text = section.get('text', '').strip()
    if not text or word_count_func(text) < 10:
        # Handle extremely short sections
        return {
            'id': section['id'],
            'title': section.get('title', ''),
            'text': text,
            'bullets': [],
            'emphasis_phrases': [],
            'tokens': tokenize_words(text),
            'lines': []
        }
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Extract bullet lines
    bullets = _extract_bullets(lines)
    
    # Extract emphasis phrases
    emphasis_phrases = _extract_emphasis(text)
    
    # Tokenize for TF-IDF
    tokens = tokenize_words(text)
    
    return {
        'id': section['id'],
        'title': section.get('title', ''),
        'text': text,
        'bullets': bullets,
        'emphasis_phrases': emphasis_phrases,
        'tokens': tokens,
        'lines': lines
    }


def _extract_bullets(lines: List[str]) -> List[str]:
    """Extract and clean bullet points from lines."""
    bullets = []
    
    for line in lines:
        if BULLET_PATTERN.match(line) and len(bullets) < 6:
            # Remove bullet markers and clean up
            cleaned = BULLET_PATTERN.sub('', line).strip()
            if cleaned and len(cleaned.split()) > 2:  # Only keep substantial bullets
                bullets.append(cleaned)
    
    return bullets


def _extract_emphasis(text: str) -> List[str]:
    """Extract emphasized phrases from text markup."""
    phrases = []
    
    for match in EMPHASIS_PATTERN.finditer(text):
        # Get the emphasized text (any of the capture groups)
        phrase = match.group(1) or match.group(2) or match.group(3)
        if phrase and phrase.strip():
            phrases.append(phrase.strip())
    
    return dedupe_preserve_order(phrases)


def _compute_tf_idf(all_documents: List[List[str]]) -> List[Dict[str, float]]:
    """Compute TF-IDF scores for all documents."""
    if not all_documents:
        return []
    
    # Build vocabulary and document frequencies
    vocab = set()
    for doc in all_documents:
        vocab.update(doc)
        # Add bigrams
        for i in range(len(doc) - 1):
            bigram = f"{doc[i]} {doc[i+1]}"
            vocab.add(bigram)
    
    vocab = list(vocab)
    
    # Compute document frequencies
    df = Counter()
    for doc in all_documents:
        doc_set = set(doc)
        # Add bigrams to doc_set
        for i in range(len(doc) - 1):
            bigram = f"{doc[i]} {doc[i+1]}"
            doc_set.add(bigram)
        
        for term in vocab:
            if term in doc_set:
                df[term] += 1
    
    N = len(all_documents)
    
    # Compute TF-IDF for each document
    tf_idf_scores = []
    for doc in all_documents:
        doc_tf = Counter(doc)
        # Add bigram counts
        for i in range(len(doc) - 1):
            bigram = f"{doc[i]} {doc[i+1]}"
            doc_tf[bigram] += 1
        
        doc_length = len(doc)
        scores = {}
        
        for term in vocab:
            tf = doc_tf[term] / doc_length if doc_length > 0 else 0
            idf = math.log(1 + N / (1 + df[term]))
            scores[term] = tf * idf
        
        tf_idf_scores.append(scores)
    
    return tf_idf_scores


def _extract_global_keywords(tf_idf_scores: List[Dict[str, float]], processed_sections: List[Dict]) -> List[str]:
    """Extract global keywords by averaging TF-IDF scores across all sections."""
    if not tf_idf_scores:
        return []
    
    # Average TF-IDF scores across all documents
    avg_scores = defaultdict(float)
    for scores in tf_idf_scores:
        for term, score in scores.items():
            avg_scores[term] += score
    
    for term in avg_scores:
        avg_scores[term] /= len(tf_idf_scores)
    
    # Sort by score (desc) then lexicographically
    sorted_terms = sorted(avg_scores.items(), key=lambda x: (-x[1], x[0]))
    
    # Filter out stopwords and get top terms (favor bigrams)
    global_keywords = []
    seen_unigrams = set()
    
    for term, score in sorted_terms:
        if len(global_keywords) >= 12:
            break
        
        if term not in STOPWORDS:
            words = term.split()
            if len(words) == 2:  # Bigram - always prefer
                global_keywords.append(term)
            elif len(words) == 1 and term not in seen_unigrams:  # Unigram
                # Check if it's not already covered by a bigram
                covered = any(term in existing for existing in global_keywords if ' ' in existing)
                if not covered:
                    global_keywords.append(term)
                    seen_unigrams.add(term)
    
    return global_keywords


def _extract_section_keywords(processed: Dict, tf_idf_scores: Dict[str, float], top_k: int) -> List[str]:
    """Extract keywords for a single section."""
    # Apply bonuses for emphasis and bullet content
    boosted_scores = tf_idf_scores.copy()
    
    # Boost emphasis phrases
    for phrase in processed['emphasis_phrases']:
        phrase_tokens = tokenize_words(phrase)
        for token in phrase_tokens:
            if token in boosted_scores:
                boosted_scores[token] *= 1.1
        # Also boost as bigram if applicable
        if len(phrase_tokens) == 2:
            bigram = f"{phrase_tokens[0]} {phrase_tokens[1]}"
            if bigram in boosted_scores:
                boosted_scores[bigram] *= 1.1
    
    # Boost bullet content
    for bullet in processed['bullets']:
        bullet_tokens = tokenize_words(bullet)
        for token in bullet_tokens:
            if token in boosted_scores:
                boosted_scores[token] *= 1.1
        # Also boost bigrams in bullets
        for i in range(len(bullet_tokens) - 1):
            bigram = f"{bullet_tokens[i]} {bullet_tokens[i+1]}"
            if bigram in boosted_scores:
                boosted_scores[bigram] *= 1.1
    
    # Sort by score (desc) then lexicographically
    sorted_terms = sorted(boosted_scores.items(), key=lambda x: (-x[1], x[0]))
    
    # Select top keywords (favor bigrams over unigrams when overlapping)
    keywords = []
    seen_unigrams = set()
    
    for term, score in sorted_terms:
        if len(keywords) >= top_k:
            break
        
        if term not in STOPWORDS and score > 0:
            words = term.split()
            if len(words) == 2:  # Bigram - always prefer
                keywords.append(term)
            elif len(words) == 1 and term not in seen_unigrams:  # Unigram
                # Check if it's not already covered by a bigram
                covered = any(term in existing for existing in keywords if ' ' in existing)
                if not covered:
                    keywords.append(term)
                    seen_unigrams.add(term)
    
    return keywords


def _generate_summary(processed: Dict, keywords: List[str], min_words: int, max_words: int) -> str:
    """Generate a summary for a section."""
    if word_count_func(processed['text']) < 10:
        # Extremely short section - return as is but bounded
        summary = processed['text']
        if word_count_func(summary) > max_words:
            words = summary.split()[:max_words]
            summary = ' '.join(words)
        return summary
    
    parts = []
    used_content = set()  # Track content to avoid duplication
    
    # Add title if informative
    title = processed['title']
    if is_informative_title(title):
        title_text = title.rstrip('.') + '.'
        parts.append(title_text)
        used_content.add(title.lower().strip())
    
    # Add first 1-2 bullet lines (cleaned)
    for i, bullet in enumerate(processed['bullets'][:2]):
        if bullet and bullet.lower().strip() not in used_content:
            clean_bullet = bullet.rstrip('.')
            if not clean_bullet.endswith('.'):
                clean_bullet += '.'
            parts.append(clean_bullet)
            used_content.add(bullet.lower().strip())
    
    current_text = ' '.join(parts)
    current_words = word_count_func(current_text)
    
    # If we need more words, add keyword-bearing sentences from non-bullet content
    if current_words < min_words:
        # Get non-bullet sentences from the original text
        all_lines = processed['text'].split('\n')
        non_bullet_lines = []
        
        for line in all_lines:
            line = line.strip()
            if line and not BULLET_PATTERN.match(line):
                non_bullet_lines.append(line)
        
        non_bullet_text = ' '.join(non_bullet_lines)
        sentences = split_sentences(non_bullet_text)
        top_keywords = set(keywords[:5])  # Use top 5 keywords for filtering
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_lower = sentence.lower().strip()
            
            # Skip if sentence is very similar to existing content
            if any(sentence_lower in existing.lower() or existing.lower() in sentence_lower 
                   for existing in used_content):
                continue
            
            # Check if sentence contains keywords or if we're still very short
            sentence_tokens = set(tokenize_words(sentence))
            if top_keywords.intersection(sentence_tokens) or current_words < min_words // 2:
                # Trim very long sentences
                if word_count_func(sentence) > 35:
                    sentence = _trim_long_sentence(sentence)
                
                if not sentence.endswith('.'):
                    sentence += '.'
                
                parts.append(sentence)
                used_content.add(sentence_lower)
                current_text = ' '.join(parts)
                current_words = word_count_func(current_text)
                
                if current_words >= min_words:
                    break
    
    # If still too short and we have more bullets, add them
    if current_words < min_words:
        for bullet in processed['bullets'][2:]:
            if bullet and bullet.lower().strip() not in used_content:
                clean_bullet = bullet.rstrip('.')
                if not clean_bullet.endswith('.'):
                    clean_bullet += '.'
                parts.append(clean_bullet)
                used_content.add(bullet.lower().strip())
                current_text = ' '.join(parts)
                current_words = word_count_func(current_text)
                if current_words >= min_words:
                    break
    
    # Enforce max_words limit
    if current_words > max_words:
        # Trim at sentence boundaries
        sentences = split_sentences(current_text)
        trimmed_parts = []
        running_words = 0
        
        for sentence in sentences:
            sentence_words = word_count_func(sentence)
            if running_words + sentence_words <= max_words:
                trimmed_parts.append(sentence)
                running_words += sentence_words
            else:
                break
        
        current_text = ' '.join(trimmed_parts)
    
    # Final cleanup
    current_text = re.sub(r'\s+', ' ', current_text).strip()
    
    return current_text


def _trim_long_sentence(sentence: str) -> str:
    """Trim a long sentence by removing parentheticals and trailing clauses."""
    # Remove parentheticals
    sentence = PARENTHETICAL_PATTERN.sub('', sentence)
    
    # Remove trailing clauses after semicolons or em-dashes
    sentence = TRAILING_CLAUSE_PATTERN.sub('', sentence)
    
    return sentence.strip()


# Utility functions
def tokenize_words(text: str) -> List[str]:
    """Tokenize text into lowercase words, stripping punctuation."""
    words = WORD_PATTERN.findall(text.lower())
    return [word for word in words if word not in STOPWORDS and len(word) > 1]


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using regex."""
    sentences = SENTENCE_PATTERN.split(text)
    return [s.strip() for s in sentences if s.strip()]


def is_informative_title(title: str) -> bool:
    """Check if title is informative (not just 'Page N')."""
    return not re.match(r'^\s*page\s+\d+\s*$', title.lower())


def word_count_func(text: str) -> int:
    """Count words in text."""
    return len(text.split()) if text else 0


def dedupe_preserve_order(seq: List) -> List:
    """Remove duplicates while preserving order."""
    seen = set()
    result = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def main():
    """CLI interface for testing."""
    if len(sys.argv) != 2:
        print("Usage: python compress_notes.py <json_file>")
        print("")
        print("JSON file should contain:")
        print('{"sections": [{"id": "...", "title": "...", "text": "..."}, ...]}')
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "sections" not in data:
            raise ValueError("JSON must contain 'sections' key")
        
        result = compress_sections(data["sections"])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

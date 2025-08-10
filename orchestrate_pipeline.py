#!/usr/bin/env python3
"""
Document processing orchestrator with OpenAI question generation.

Integrates extract_text.py, clean_text.py, compress_notes.py, and OpenAI GPT-3.5
to generate quiz questions from documents.
"""

import asyncio
import json
import os
import re
import uuid
import argparse
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path

import openai
import httpx

# Import our existing pipeline modules
from extract_text import extract_document_text
from clean_text import clean_extracted_sections
from compress_notes import compress_sections


def estimate_tokens(text: str) -> int:
    """
    Cheap token estimator: approximately words * 1.3.
    
    Args:
        text: Input text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text or not isinstance(text, str):
        return 0
    
    # Simple word count * 1.3 approximation
    word_count = len(text.split())
    return int(word_count * 1.3)


def concat_notes(notes_obj: Dict) -> str:
    """
    Create a compact text block from notes object.
    
    Args:
        notes_obj: Output from compress_sections
        
    Returns:
        Formatted text string of all notes
    """
    if not notes_obj or 'notes' not in notes_obj:
        return ""
    
    note_blocks = []
    
    for note in notes_obj['notes']:
        lines = []
        
        # Add title (if not generic page title)
        title = note.get('title', '').strip()
        if title and not re.match(r'^page\s+\d+$', title, re.IGNORECASE):
            lines.append(f"## {title}")
        
        # Add up to 2 bullet points
        bullets = note.get('bullets', [])
        if bullets:
            for i, bullet in enumerate(bullets[:2]):  # Max 2 bullets
                lines.append(f"• {bullet}")
        
        # Add summary
        summary = note.get('summary', '').strip()
        if summary:
            lines.append(summary)
        
        if lines:
            note_blocks.append('\n'.join(lines))
    
    # Join notes with double newlines, limit to ~8k words for safety
    full_text = '\n\n'.join(note_blocks)
    words = full_text.split()
    if len(words) > 8000:
        full_text = ' '.join(words[:8000]) + "..."
    
    return full_text


def stem(text: str) -> str:
    """
    Create normalized stem for duplicate detection.
    
    Args:
        text: Question text to normalize
        
    Returns:
        Normalized stem (first 12 words, lowercase, no punctuation)
    """
    if not text:
        return ""
    
    # Lowercase and remove punctuation
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    # Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    # Take first 12 words
    words = normalized.split()[:12]
    
    return ' '.join(words)


class OpenAIClient:
    """Async OpenAI client with retry logic."""
    
    def __init__(self, api_key: str, timeout: int = 30, max_retries: int = 2):
        self.client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.max_retries = max_retries
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.2,
        max_tokens: int = 2000
    ) -> Tuple[str, int, int]:
        """
        Make chat completion with retry logic.
        
        Returns:
            (response_text, prompt_tokens, completion_tokens)
        """
        for attempt in range(self.max_retries + 1):
            try:
                # Prepare request params
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                
                # Add seed for determinism if supported
                try:
                    params["seed"] = 1
                except:
                    pass  # Ignore if seed not supported
                
                response = await self.client.chat.completions.create(**params)
                
                content = response.choices[0].message.content or ""
                
                # Extract token counts
                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else estimate_tokens('\n'.join(m['content'] for m in messages))
                completion_tokens = usage.completion_tokens if usage else estimate_tokens(content)
                
                return content, prompt_tokens, completion_tokens
                
            except (openai.RateLimitError, openai.APITimeoutError, httpx.TimeoutException) as e:
                if attempt == self.max_retries:
                    raise
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(1)
        
        raise Exception("Max retries exceeded")


def chunk_notes(notes_obj: Dict, chunk_target_tokens: int) -> List[Dict]:
    """
    Split notes into chunks for map-reduce processing.
    
    Args:
        notes_obj: Output from compress_sections
        chunk_target_tokens: Target tokens per chunk
        
    Returns:
        List of note chunks
    """
    if not notes_obj or 'notes' not in notes_obj:
        return []
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for note in notes_obj['notes']:
        # Estimate tokens for this note
        note_text = f"{note.get('title', '')} {' '.join(note.get('bullets', []))} {note.get('summary', '')}"
        note_tokens = estimate_tokens(note_text)
        
        # If adding this note exceeds target and we have notes in current chunk
        if current_tokens + note_tokens > chunk_target_tokens and current_chunk:
            chunks.append({"notes": current_chunk})
            current_chunk = [note]
            current_tokens = note_tokens
        else:
            current_chunk.append(note)
            current_tokens += note_tokens
    
    # Add remaining notes
    if current_chunk:
        chunks.append({"notes": current_chunk})
    
    return chunks


def validate_and_normalize_questions(raw_response: Dict, max_mcq: int, max_short: int) -> Dict:
    """
    Validate and normalize question format.
    
    Args:
        raw_response: Raw response from OpenAI
        max_mcq: Maximum MCQ questions
        max_short: Maximum short answer questions
        
    Returns:
        Normalized questions dict
    """
    result = {"mcq": [], "short": []}
    
    if not isinstance(raw_response, dict) or 'questions' not in raw_response:
        return result
    
    questions = raw_response['questions']
    
    # Process MCQ questions
    mcq_list = questions.get('mcq', [])
    if isinstance(mcq_list, list):
        for q in mcq_list[:max_mcq]:
            if not isinstance(q, dict):
                continue
            
            # Validate required fields
            question_text = q.get('question', '').strip()
            options = q.get('options', [])
            answer_idx = q.get('answerIndex')
            explanation = q.get('explanation', '').strip()
            
            if (question_text and 
                isinstance(options, list) and 
                len(options) == 4 and 
                all(isinstance(opt, str) and opt.strip() for opt in options) and
                isinstance(answer_idx, int) and 
                0 <= answer_idx <= 3):
                
                # Ensure unique ID
                q_id = q.get('id', f"q_{uuid.uuid4().hex[:8]}")
                if not q_id.startswith('q_'):
                    q_id = f"q_{uuid.uuid4().hex[:8]}"
                
                result['mcq'].append({
                    "id": q_id,
                    "question": question_text,
                    "options": [opt.strip() for opt in options],
                    "answerIndex": answer_idx,
                    "explanation": explanation
                })
    
    # Process short answer questions
    short_list = questions.get('short', [])
    if isinstance(short_list, list):
        for q in short_list[:max_short]:
            if not isinstance(q, dict):
                continue
            
            prompt_text = q.get('prompt', '').strip()
            keywords = q.get('expectedKeywords', [])
            
            if (prompt_text and 
                isinstance(keywords, list) and 
                all(isinstance(kw, str) for kw in keywords)):
                
                # Ensure unique ID
                s_id = q.get('id', f"s_{uuid.uuid4().hex[:8]}")
                if not s_id.startswith('s_'):
                    s_id = f"s_{uuid.uuid4().hex[:8]}"
                
                result['short'].append({
                    "id": s_id,
                    "prompt": prompt_text,
                    "expectedKeywords": [kw.strip() for kw in keywords if kw.strip()]
                })
    
    return result


def deduplicate_questions(questions: Dict) -> Dict:
    """
    Remove duplicate questions based on normalized stems.
    
    Args:
        questions: Questions dict with mcq and short lists
        
    Returns:
        Deduplicated questions dict
    """
    seen_stems = set()
    result = {"mcq": [], "short": []}
    
    # Deduplicate MCQ
    for q in questions.get('mcq', []):
        question_stem = stem(q.get('question', ''))
        if question_stem and question_stem not in seen_stems:
            seen_stems.add(question_stem)
            result['mcq'].append(q)
    
    # Deduplicate short answer
    for q in questions.get('short', []):
        prompt_stem = stem(q.get('prompt', ''))
        if prompt_stem and prompt_stem not in seen_stems:
            seen_stems.add(prompt_stem)
            result['short'].append(q)
    
    return result


async def process_document(
    file_path: str,
    *,
    model: str = "gpt-3.5-turbo",
    max_mcq: int = 8,
    max_short: int = 4,
    temperature: float = 0.2,
    single_call_token_limit: int = 6000,
    chunk_target_tokens: int = 1500,
    request_timeout_s: int = 30,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    Process document through pipeline and generate questions.
    
    Args:
        file_path: Path to document file
        model: OpenAI model to use
        max_mcq: Maximum MCQ questions
        max_short: Maximum short answer questions
        temperature: Model temperature
        single_call_token_limit: Token limit for single call strategy
        chunk_target_tokens: Target tokens per chunk
        request_timeout_s: Request timeout in seconds
        max_retries: Maximum retry attempts
        
    Returns:
        JobResult-like dict with questions and metadata
    """
    job_id = uuid.uuid4().hex[:8]
    
    # Initialize result structure
    result = {
        "jobId": job_id,
        "status": "error",
        "questions": {"mcq": [], "short": []},
        "meta": {
            "sourceFile": Path(file_path).name,
            "pages": 0,
            "tokenCounts": {"raw": 0, "notes": 0, "promptIn": 0, "modelOut": 0},
            "strategy": "single",
            "chunks": 0
        },
        "error": None
    }
    
    try:
        # Check OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Step 1: Extract document text
        print(f"Extracting text from {file_path}...")
        raw_data = extract_document_text(file_path)
        
        result["meta"]["sourceFile"] = raw_data.get("doc", {}).get("title", Path(file_path).name)
        result["meta"]["pages"] = raw_data.get("doc", {}).get("pages", 0)
        
        # Step 2: Clean sections
        print("Cleaning extracted sections...")
        cleaned_sections = clean_extracted_sections(raw_data["sections"])
        
        # Step 3: Compress to notes
        print("Compressing to study notes...")
        notes_data = compress_sections(cleaned_sections)
        
        # Calculate token counts
        raw_tokens = sum(estimate_tokens(s.get("text", "")) for s in cleaned_sections)
        notes_text = concat_notes(notes_data)
        notes_tokens = estimate_tokens(notes_text)
        
        result["meta"]["tokenCounts"]["raw"] = raw_tokens
        result["meta"]["tokenCounts"]["notes"] = notes_tokens
        
        # Choose strategy
        if notes_tokens <= single_call_token_limit:
            strategy = "single"
            chunks = 1
        else:
            strategy = "chunked"
            note_chunks = chunk_notes(notes_data, chunk_target_tokens)
            chunks = len(note_chunks)
        
        result["meta"]["strategy"] = strategy
        result["meta"]["chunks"] = chunks
        
        print(f"Using {strategy} strategy with {chunks} chunk(s)")
        
        # Initialize OpenAI client
        client = OpenAIClient(api_key, request_timeout_s, max_retries)
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        
        if strategy == "single":
            # Single call strategy
            system_msg = "You are an exam-item writer. Generate high-quality, factual questions strictly from the provided notes."
            
            user_prompt = f"""Using ONLY these section notes, generate up to {max_mcq} multiple-choice (4 options, 1 correct) and up to {max_short} short-answer questions.
Return JSON only in this exact shape:
{{
  "questions": {{
    "mcq": [
      {{ "id": "q_<uuid8>", "question": "...", "options": ["A","B","C","D"], "answerIndex": 0, "explanation": "..." }}
    ],
    "short": [
      {{ "id": "s_<uuid8>", "prompt": "...", "expectedKeywords": ["k1","k2"] }}
    ]
  }}
}}

Notes:
{notes_text}"""

            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ]
            
            response_text, prompt_tokens, completion_tokens = await client.chat_completion(
                messages, model, temperature, 2000
            )
            
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            
            # Parse response
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                # Retry with correction prompt
                correction_prompt = "You returned invalid JSON. Return strictly valid JSON matching the schema."
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": correction_prompt})
                
                response_text, prompt_tokens, completion_tokens = await client.chat_completion(
                    messages, model, temperature, 2000
                )
                
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                
                response_data = json.loads(response_text)
            
            # Validate and normalize
            questions = validate_and_normalize_questions(response_data, max_mcq, max_short)
            
        else:
            # Chunked strategy (map-reduce)
            note_chunks = chunk_notes(notes_data, chunk_target_tokens)
            seen_stems = []
            all_partials = []
            
            # Map phase
            for i, chunk in enumerate(note_chunks):
                print(f"Processing chunk {i+1}/{len(note_chunks)}...")
                
                chunk_text = concat_notes(chunk)
                seen_stems_str = ', '.join(seen_stems) if seen_stems else "None"
                
                system_msg = "You are an exam-item writer. Generate high-quality, factual questions strictly from the provided notes."
                
                user_prompt = f"""Using ONLY these section notes, generate up to 2 multiple-choice (4 options, 1 correct) and up to 1 short-answer questions.
Avoid overlap with existing stems: {seen_stems_str}

Return JSON only in this exact shape:
{{
  "questions": {{
    "mcq": [
      {{ "id": "q_<uuid8>", "question": "...", "options": ["A","B","C","D"], "answerIndex": 0, "explanation": "..." }}
    ],
    "short": [
      {{ "id": "s_<uuid8>", "prompt": "...", "expectedKeywords": ["k1","k2"] }}
    ]
  }}
}}

Notes:
{chunk_text}"""

                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ]
                
                response_text, prompt_tokens, completion_tokens = await client.chat_completion(
                    messages, model, temperature, 1500
                )
                
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                
                try:
                    chunk_response = json.loads(response_text)
                    chunk_questions = validate_and_normalize_questions(chunk_response, 2, 1)
                    all_partials.append(chunk_questions)
                    
                    # Update seen stems
                    for q in chunk_questions.get('mcq', []):
                        seen_stems.append(stem(q.get('question', '')))
                    for q in chunk_questions.get('short', []):
                        seen_stems.append(stem(q.get('prompt', '')))
                    
                except json.JSONDecodeError:
                    print(f"Failed to parse chunk {i+1} response, skipping...")
                    continue
            
            # Reduce phase
            if all_partials:
                partials_json = json.dumps(all_partials)
                
                reduce_prompt = f"""Merge these partial question lists. Remove duplicates, diversify stems, ensure coverage.
Cap totals at {max_mcq} MCQ and {max_short} short. Keep best explanations.
Return the same JSON shape.

Partial lists:
{partials_json}"""

                messages = [
                    {"role": "system", "content": "You are an exam-item writer. Merge and optimize question collections."},
                    {"role": "user", "content": reduce_prompt}
                ]
                
                response_text, prompt_tokens, completion_tokens = await client.chat_completion(
                    messages, model, temperature, 2000
                )
                
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                
                try:
                    final_response = json.loads(response_text)
                    questions = validate_and_normalize_questions(final_response, max_mcq, max_short)
                except json.JSONDecodeError:
                    # Fallback: merge partials manually
                    questions = {"mcq": [], "short": []}
                    for partial in all_partials:
                        questions["mcq"].extend(partial.get("mcq", []))
                        questions["short"].extend(partial.get("short", []))
                    questions = validate_and_normalize_questions({"questions": questions}, max_mcq, max_short)
            else:
                questions = {"mcq": [], "short": []}
        
        # Final deduplication
        questions = deduplicate_questions(questions)
        
        # Update result
        result["status"] = "done"
        result["questions"] = questions
        result["meta"]["tokenCounts"]["promptIn"] = total_prompt_tokens
        result["meta"]["tokenCounts"]["modelOut"] = total_completion_tokens
        
        print(f"Generated {len(questions['mcq'])} MCQ and {len(questions['short'])} short answer questions")
        
    except Exception as e:
        result["error"] = str(e)
        print(f"Error: {e}")
    
    return result


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Process document and generate questions")
    parser.add_argument("file_path", help="Path to document file")
    parser.add_argument("--strategy", choices=["single", "chunked"], help="Force strategy")
    parser.add_argument("--max-mcq", type=int, default=8, help="Maximum MCQ questions")
    parser.add_argument("--max-short", type=int, default=4, help="Maximum short answer questions")
    parser.add_argument("--model", default="gpt-3.5-turbo", help="OpenAI model")
    parser.add_argument("--temperature", type=float, default=0.2, help="Model temperature")
    
    args = parser.parse_args()
    
    # Force strategy if specified
    kwargs = {
        "max_mcq": args.max_mcq,
        "max_short": args.max_short,
        "model": args.model,
        "temperature": args.temperature,
    }
    
    if args.strategy:
        if args.strategy == "single":
            kwargs["single_call_token_limit"] = 50000  # Force single
        else:
            kwargs["single_call_token_limit"] = 100    # Force chunked
    
    result = await process_document(args.file_path, **kwargs)
    
    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

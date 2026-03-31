"""
Interview Transcript Analyzer

Architecture:
- Parses transcript into speaker turns (natural chunk boundaries)
- Generic speaker names (Speaker 1/2, Unknown) relabeled Interviewer/Interviewee via question-frequency heuristic
- Short transcripts (≤ 3500 words): single structured API call
- Long transcripts: map-reduce — analyze each chunk, then synthesize into final output
- Chunking is word-count based (~3500 words per chunk), never split mid-turn
- Talk ratio computed locally (no API cost)
- All LLM responses use JSON mode for reliable structured output
"""

import re
import json
from collections import Counter
from groq import Groq

WORDS_PER_CHUNK = 3500

_GENERIC_SPEAKER_RE = re.compile(
    r'^(speaker\s*\d+|unknown(\s+speaker)?|interviewee?|participant\s*\d*)$',
    re.IGNORECASE,
)


def parse_transcript(text: str) -> list:
    """
    Parse a transcript into speaker turns.
    Handles formats like:
      - "Interviewer: ..." / "Interviewee: ..."
      - "Q: ..." / "A: ..."
      - "Speaker 1: ..." / "Speaker 2: ..."
    Returns list of {"speaker": str, "text": str}
    """
    lines = text.strip().splitlines()
    turns = []
    current_speaker = None
    current_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^([A-Za-z][A-Za-z0-9 _-]{0,30}):\s*(.*)', line)
        if match:
            if current_speaker and current_lines:
                turns.append({"speaker": current_speaker, "text": " ".join(current_lines)})
            current_speaker = match.group(1).strip()
            current_lines = [match.group(2).strip()] if match.group(2).strip() else []
        else:
            if current_speaker:
                current_lines.append(line)

    if current_speaker and current_lines:
        turns.append({"speaker": current_speaker, "text": " ".join(current_lines)})

    return turns


def _infer_speaker_roles(turns: list) -> list:
    """
    If all speaker names look generic (Speaker 1, Unknown, etc.) and there are
    exactly 2 speakers, relabel the one who asks more questions as 'Interviewer'
    and the other as 'Interviewee'.
    """
    speakers = list(dict.fromkeys(t["speaker"] for t in turns))
    if len(speakers) != 2:
        return turns
    if not all(_GENERIC_SPEAKER_RE.match(s) for s in speakers):
        return turns

    question_counts = {s: 0 for s in speakers}
    turn_counts = {s: 0 for s in speakers}
    for t in turns:
        turn_counts[t["speaker"]] += 1
        if t["text"].rstrip().endswith("?"):
            question_counts[t["speaker"]] += 1

    ratios = {s: question_counts[s] / turn_counts[s] for s in speakers}
    if ratios[speakers[0]] == ratios[speakers[1]]:
        return turns

    interviewer = max(ratios, key=ratios.get)
    interviewee = [s for s in speakers if s != interviewer][0]
    label_map = {interviewer: "Interviewer", interviewee: "Interviewee"}
    return [{"speaker": label_map[t["speaker"]], "text": t["text"]} for t in turns]


def _chunk_by_words(turns: list, limit: int = WORDS_PER_CHUNK) -> list:
    """Split turns into chunks where each chunk is at most `limit` words."""
    chunks = []
    current_chunk = []
    current_words = 0
    for turn in turns:
        turn_words = len(turn["text"].split())
        if current_chunk and current_words + turn_words > limit:
            chunks.append(current_chunk)
            current_chunk = [turn]
            current_words = turn_words
        else:
            current_chunk.append(turn)
            current_words += turn_words
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _turns_to_text(turns: list) -> str:
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)


def _compute_talk_ratio(turns: list) -> dict:
    word_counts = Counter()
    for t in turns:
        word_counts[t["speaker"]] += len(t["text"].split())
    total = sum(word_counts.values()) or 1
    return {speaker: round(count / total, 3) for speaker, count in word_counts.items()}


def _analyze_full(client: Groq, text: str, speakers: list) -> dict:
    """Single structured call for transcripts that fit in one chunk."""
    speaker_list = ", ".join(speakers)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": (
                f"Analyze this interview transcript. Speakers: {speaker_list}.\n\n"
                "Return a JSON object with exactly these fields:\n"
                '- "summary": string (3-5 sentences covering key topics and conclusions)\n'
                '- "themes": array of strings (main topics/themes discussed)\n'
                '- "key_quotes": array of {"speaker": string, "quote": string} objects (up to 5 notable quotes)\n'
                '- "sentiment": {"overall": "positive" or "neutral" or "negative", '
                '"tone": string (one sentence on emotional tone), '
                '"notable_moments": array of strings (notable emotional highs or lows)}\n'
                '- "speaker_sentiment": object where each key is a speaker name and value is a brief sentiment description\n\n'
                f"Transcript:\n{text}"
            ),
        }],
    )
    return json.loads(resp.choices[0].message.content)


def _analyze_chunk(client: Groq, chunk_text: str) -> dict:
    """Structured call for one chunk in the map phase."""
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": (
                "Analyze this excerpt from an interview transcript.\n\n"
                "Return a JSON object with exactly these fields:\n"
                '- "partial_summary": string (2-3 sentences on key points in this excerpt)\n'
                '- "themes": array of strings (topics mentioned in this excerpt)\n'
                '- "key_quotes": array of {"speaker": string, "quote": string} objects (up to 2 notable quotes)\n'
                '- "sentiment_signals": string (brief note on emotional tone in this excerpt)\n\n'
                f"Transcript excerpt:\n{chunk_text}"
            ),
        }],
    )
    return json.loads(resp.choices[0].message.content)


def _synthesize(client: Groq, partial_results: list, speakers: list) -> dict:
    """Reduce phase — combine chunk analyses into a single coherent output."""
    speaker_list = ", ".join(speakers)
    combined = json.dumps(partial_results, indent=2)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": (
                f"You have chunk-level analyses of a full interview transcript. "
                f"Speakers: {speaker_list}.\n\n"
                "Synthesize these into a final analysis. Return a JSON object with exactly these fields:\n"
                '- "summary": string (3-5 sentences, coherent overall summary of the full interview)\n'
                '- "themes": array of strings (deduplicated key themes across the full interview)\n'
                '- "key_quotes": array of {"speaker": string, "quote": string} objects (up to 5 best quotes from all chunks)\n'
                '- "sentiment": {"overall": "positive" or "neutral" or "negative", '
                '"tone": string (one sentence), '
                '"notable_moments": array of strings}\n'
                '- "speaker_sentiment": object where each key is a speaker name and value is a brief sentiment description\n\n'
                f"Chunk analyses:\n{combined}"
            ),
        }],
    )
    return json.loads(resp.choices[0].message.content)


def analyze_transcript(text: str, api_key: str) -> dict:
    client = Groq(api_key=api_key)
    turns = parse_transcript(text)

    # Fallback for plain text with no speaker labels
    if not turns:
        turns = [{"speaker": "Speaker", "text": text}]

    turns = _infer_speaker_roles(turns)
    speakers = list(dict.fromkeys(t["speaker"] for t in turns))
    talk_ratio = _compute_talk_ratio(turns)

    chunks = _chunk_by_words(turns)

    if len(chunks) == 1:
        final = _analyze_full(client, _turns_to_text(chunks[0]), speakers)
    else:
        partial_results = [_analyze_chunk(client, _turns_to_text(chunk)) for chunk in chunks]
        final = _synthesize(client, partial_results, speakers)

    return {
        "summary": final.get("summary", ""),
        "themes": final.get("themes", []),
        "key_quotes": final.get("key_quotes", []),
        "sentiment": final.get("sentiment", {}),
        "speaker_sentiment": final.get("speaker_sentiment", {}),
        "speakers": speakers,
        "talk_ratio": talk_ratio,
    }

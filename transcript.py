"""
Interview Transcript Analyzer
Parses speaker turns from .txt transcripts and uses Groq to summarize
and perform sentiment analysis.
"""

import re
from groq import Groq


def parse_transcript(text: str) -> list:
    """
    Parse a transcript into a list of speaker turns.
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


def analyze_transcript(text: str, api_key: str) -> dict:
    """
    Analyze an interview transcript using Groq.
    Returns:
        {
            "summary": str,
            "sentiment": str,
            "speakers": list[str],
        }
    """
    client = Groq(api_key=api_key)
    truncated = text[:8000]

    summary_result = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": (
                "You are analyzing an interview transcript. "
                "Provide a concise summary (3-5 sentences) of the key topics discussed, "
                "main points raised by the interviewee, and any conclusions or outcomes mentioned.\n\n"
                f"Transcript:\n{truncated}"
            ),
        }],
    )
    summary = summary_result.choices[0].message.content.strip()

    sentiment_result = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": (
                "You are analyzing an interview transcript. "
                "Provide a sentiment analysis covering:\n"
                "1. Overall tone (positive / neutral / negative) with a one-sentence explanation\n"
                "2. Emotional tone of the interviewee (e.g. enthusiastic, frustrated, uncertain, confident)\n"
                "3. Any notable positive or negative moments in the conversation\n\n"
                f"Transcript:\n{truncated}"
            ),
        }],
    )
    sentiment = sentiment_result.choices[0].message.content.strip()

    turns = parse_transcript(text)
    speakers = list(dict.fromkeys(t["speaker"] for t in turns))

    return {
        "summary": summary,
        "sentiment": sentiment,
        "speakers": speakers,
    }

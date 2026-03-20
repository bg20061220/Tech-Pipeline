"""
Text Analysis Pipeline
Sends each text column's responses to Groq API one question at a time,
using a rolling batch strategy to handle large response sets.
"""

from groq import Groq


def filter_responses(responses: list) -> list:
    """Drop responses with 2 words or fewer — not informative enough."""
    return [r for r in responses if isinstance(r, str) and len(r.split()) > 2]


def chunk(lst: list, size: int):
    """Yield successive chunks of given size from lst."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def summarize_column(client, question: str, responses: list, batch_size: int = 20) -> str | None:
    """
    Rolling summary for a single question's responses.
    Each batch refines the previous summary rather than replacing it.
    Returns None if no informative responses remain after filtering.
    """
    filtered = filter_responses(responses)
    batches = list(chunk(filtered, batch_size))

    if not batches:
        return None

    summary = None

    for batch in batches:
        response_block = "\n".join(f"- {r}" for r in batch)

        if summary is None:
            prompt = (
                f'You are analyzing open-ended survey responses to the question: "{question}"\n\n'
                f"Summarize the main themes, overall sentiment, key concerns, "
                f"and notable positive remarks from these responses:\n\n"
                f"{response_block}\n\n"
                f"Be concise. Focus on patterns across responses, not individual ones."
            )
        else:
            prompt = (
                f'You are analyzing open-ended survey responses to the question: "{question}"\n\n'
                f"Current summary:\n{summary}\n\n"
                f"Refine the summary using these additional responses, "
                f"updating themes and adding any new concerns or positives:\n\n"
                f"{response_block}\n\n"
                f"Keep the updated summary concise."
            )

        result = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        summary = result.choices[0].message.content.strip()

    return summary


def run_analysis(df_text, column_map: dict, api_key: str, batch_size: int = 20) -> dict:
    """
    Analyze all text columns from df_text.

    Args:
        df_text:      Text dataframe from pipeline (col_id columns, string values)
        column_map:   Typed column map from pipeline {col_id: {original, type}}
        api_key:      Groq API key
        batch_size:   Responses per API call (default 20)

    Returns:
        {
            col_id: {
                "question": original header string,
                "summary":  final analysis string,
            },
            ...
        }
    """
    client = Groq(api_key=api_key)
    results = {}

    for col_id in df_text.columns:
        question = column_map[col_id]["original"]
        responses = df_text[col_id].dropna().tolist()

        summary = summarize_column(client, question, responses, batch_size)

        if summary is not None:
            results[col_id] = {
                "question": question,
                "summary": summary,
            }

    return results

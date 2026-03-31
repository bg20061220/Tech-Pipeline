"""
PDF Report Generator
Rule-based summary + chart images + optional text analysis section.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
from fpdf import FPDF


# ---------------------------------------------------------------------------
# Rule-based text helpers
# ---------------------------------------------------------------------------

def _overall_summary(column_map, df_numerical, df_categorical, df_text, timestamp, analysis_results):
    parts = []

    total = len(timestamp)
    try:
        ts = pd.to_datetime(timestamp)
        date_min = ts.min().strftime("%b %d")
        date_max = ts.max().strftime("%b %d, %Y")
        parts.append(f"{total} responses were collected between {date_min} - {date_max}.")
    except Exception:
        parts.append(f"{total} responses were collected.")

    if not df_numerical.empty:
        means = {}
        for col in df_numerical.columns:
            s = df_numerical[col].dropna().astype(float)
            if not s.empty:
                means[col] = s.mean()
        if len(means) >= 2:
            top = max(means, key=means.get)
            low = min(means, key=means.get)
            parts.append(
                f"Highest rated: \"{column_map[top]['original']}\" (mean {means[top]:.1f}). "
                f"Lowest rated: \"{column_map[low]['original']}\" (mean {means[low]:.1f})."
            )
        elif len(means) == 1:
            col = list(means)[0]
            parts.append(f"Average rating for \"{column_map[col]['original']}\": {means[col]:.1f}.")

    if not df_categorical.empty:
        highlights = []
        for col in df_categorical.columns:
            label = column_map[col]["original"]
            vc = df_categorical[col].value_counts()
            if len(vc) > 0:
                top_val = vc.index[0]
                top_pct = vc.iloc[0] / vc.sum() * 100
                highlights.append(f"{top_pct:.0f}% selected \"{top_val}\" for \"{label}\"")
        if highlights:
            parts.append("Key categorical findings: " + "; ".join(highlights[:3]) + ".")

    if not df_text.empty:
        n = df_text.shape[1]
        word = "questions" if n > 1 else "question"
        verb = "were" if n > 1 else "was"
        parts.append(f"{n} open-ended {word} {verb} collected.")
        if analysis_results:
            parts.append("AI-generated summaries are included in the Text Analysis section.")

    return " ".join(parts)


def _numerical_context(series):
    mean = series.mean()
    median = series.median()
    mn = series.min()
    mx = series.max()
    if mean > median * 1.05:
        skew = "skews slightly high"
    elif mean < median * 0.95:
        skew = "skews slightly low"
    else:
        skew = "is fairly evenly distributed"
    return (
        f"Responses ranged from {mn:.0f} to {mx:.0f}. "
        f"The distribution {skew} (mean {mean:.2f}, median {median:.2f})."
    )


def _categorical_context(counts_df):
    total = counts_df["count"].sum()
    top_val = counts_df.iloc[0]["value"]
    top_pct = counts_df.iloc[0]["count"] / total * 100
    n_opts = len(counts_df)
    return (
        f"Most common response: \"{top_val}\" ({top_pct:.0f}% of {total} responses). "
        f"{n_opts} unique options recorded."
    )


# ---------------------------------------------------------------------------
# Chart → temp PNG file
# ---------------------------------------------------------------------------

def _fig_to_tempfile(fig, width=640, height=360):
    try:
        img_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=2)
        if not img_bytes:
            raise ValueError("kaleido returned empty image bytes")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(img_bytes)
        tmp.close()
        return tmp.name
    except Exception as e:
        raise RuntimeError(f"Chart image export failed: {e}") from e


# ---------------------------------------------------------------------------
# Unicode → latin-1 sanitizer
# ---------------------------------------------------------------------------

_UNICODE_REPLACEMENTS = {
    "\u2014": "--",   # em dash
    "\u2013": "-",    # en dash
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u00b7": "*",    # middle dot
    "\u2022": "*",    # bullet
    "\u00a0": " ",    # non-breaking space
}

def _sanitize(text: str) -> str:
    """Replace common non-latin-1 characters, then drop anything else."""
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


# ---------------------------------------------------------------------------
# PDF class
# ---------------------------------------------------------------------------

class SurveyPDF(FPDF):
    def __init__(self, survey_name):
        super().__init__()
        self.survey_name = survey_name
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 6, self.survey_name, align="L")
        self.ln(1)
        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def section_title(self, text):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(26, 95, 173)
        self.cell(0, 9, _sanitize(text).upper(), ln=True)
        self.set_draw_color(26, 95, 173)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def column_title(self, text):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, _sanitize(text))
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(70, 70, 70)
        self.multi_cell(0, 6, _sanitize(text))
        self.ln(5)
        self.set_text_color(0, 0, 0)

    def stats_table(self, stats: dict):
        col_w = 180 / len(stats)
        # Header row
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(240, 244, 250)
        self.set_text_color(26, 95, 173)
        for label in stats:
            self.cell(col_w, 7, label, border=1, align="C", fill=True)
        self.ln()
        # Value row
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_fill_color(255, 255, 255)
        for val in stats.values():
            self.cell(col_w, 8, str(val), border=1, align="C")
        self.ln(10)
        self.set_text_color(0, 0, 0)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report(
    column_map: dict,
    df_numerical,
    df_categorical,
    df_text,
    timestamp,
    analysis_results: dict | None,
    survey_name: str = "Survey",
    progress_callback=None,
) -> bytes:
    """
    progress_callback(fraction: float, message: str) is called at each stage.
    fraction is 0.0–1.0. Pass None to skip progress reporting.
    """
    def _progress(fraction, message):
        if progress_callback:
            progress_callback(fraction, message)

    # Pre-compute column counts for proportional progress budgets.
    n_num = df_numerical.shape[1] if not df_numerical.empty else 0
    n_cat = df_categorical.shape[1] if not df_categorical.empty else 0
    n_txt = len(analysis_results) if analysis_results else 0

    # Progress budget per section (fractions of 1.0):
    #   cover: 0.00 → 0.08
    #   numerical: 0.08 → 0.50  (only if columns exist)
    #   categorical: 0.50 → 0.80  (only if columns exist)
    #   text analysis: 0.80 → 0.93  (only if results exist)
    #   finalise: 0.93 → 1.00
    NUM_START, NUM_END = 0.08, 0.50
    CAT_START, CAT_END = 0.50, 0.80
    TXT_START, TXT_END = 0.80, 0.93

    temp_files = []

    try:
        _progress(0.0, "Building cover page...")
        pdf = SurveyPDF(_sanitize(survey_name))

        # ----------------------------------------------------------------
        # Cover page
        # ----------------------------------------------------------------
        pdf.add_page()

        pdf.ln(16)
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(26, 95, 173)
        pdf.multi_cell(0, 13, "Survey Analysis Report", align="C")
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 13)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 8, survey_name, align="C")
        pdf.ln(2)

        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, f"Generated {datetime.now().strftime('%B %d, %Y at %H:%M')}", align="C", ln=True)
        pdf.ln(10)

        # Metrics bar
        metrics = {
            "Total Responses": len(timestamp),
            "Numerical Cols": df_numerical.shape[1],
            "Categorical Cols": df_categorical.shape[1],
            "Text Cols": df_text.shape[1],
        }
        col_w = 180 / len(metrics)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(26, 95, 173)
        pdf.set_fill_color(240, 244, 250)
        for label in metrics:
            pdf.cell(col_w, 8, label, border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 30, 30)
        for val in metrics.values():
            pdf.cell(col_w, 12, str(val), border=1, align="C")
        pdf.ln(12)

        # Overall summary
        pdf.set_text_color(0, 0, 0)
        pdf.section_title("Overall Summary")
        summary = _overall_summary(
            column_map, df_numerical, df_categorical, df_text, timestamp, analysis_results
        )
        pdf.body_text(summary)
        _progress(0.08, "Cover page done.")

        # ----------------------------------------------------------------
        # Numerical section
        # ----------------------------------------------------------------
        if n_num > 0:
            pdf.add_page()
            pdf.section_title(f"Numerical Columns  ({n_num})")

            for i, col_id in enumerate(df_numerical.columns):
                label = column_map.get(col_id, {}).get("original", col_id)
                series = df_numerical[col_id].dropna().astype(float)
                if series.empty:
                    continue

                _progress(
                    NUM_START + (i / n_num) * (NUM_END - NUM_START),
                    f"Numerical: {label[:50]}...) " if len(label) > 50 else f"Numerical: {label}",
                )

                pdf.column_title(label)

                mean_val = series.mean()
                median_val = series.median()
                mode_vals = series.mode()
                mode_val = mode_vals.iloc[0] if not mode_vals.empty else float("nan")
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)

                pdf.stats_table({
                    "Mean": f"{mean_val:.2f}",
                    "Median": f"{median_val:.2f}",
                    "Mode": f"{mode_val:.2f}",
                    "Q1  (25%)": f"{q1:.2f}",
                    "Q3  (75%)": f"{q3:.2f}",
                })

                pdf.body_text(_numerical_context(series))

                fig = px.histogram(
                    series, x=col_id, nbins=20,
                    labels={col_id: label},
                    color_discrete_sequence=["#1A5FAD"],
                )
                fig.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    xaxis_title=label,
                    yaxis_title="Count",
                    bargap=0.05,
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                )
                try:
                    tmp = _fig_to_tempfile(fig)
                    temp_files.append(tmp)
                    pdf.ln(5)
                    pdf.image(tmp, w=170)
                except RuntimeError as e:
                    pdf.body_text(f"[Chart unavailable: {e}]")
                pdf.ln(14)

            _progress(NUM_END, f"Numerical section done ({n_num} columns).")

        # ----------------------------------------------------------------
        # Categorical section
        # ----------------------------------------------------------------
        if n_cat > 0:
            pdf.add_page()
            pdf.section_title(f"Categorical Columns  ({n_cat})")

            for i, col_id in enumerate(df_categorical.columns):
                label = column_map.get(col_id, {}).get("original", col_id)
                counts = df_categorical[col_id].value_counts().reset_index()
                counts.columns = ["value", "count"]

                _progress(
                    CAT_START + (i / n_cat) * (CAT_END - CAT_START),
                    f"Categorical: {label[:50]}..." if len(label) > 50 else f"Categorical: {label}",
                )

                pdf.column_title(label)
                pdf.body_text(_categorical_context(counts))

                fig = px.pie(
                    counts, names="value", values="count",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    showlegend=True,
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                )
                tmp = _fig_to_tempfile(fig, width=500, height=380)
                temp_files.append(tmp)
                pdf.image(tmp, w=120, x=45)
                pdf.ln(14)

            _progress(CAT_END, f"Categorical section done ({n_cat} columns).")

        # ----------------------------------------------------------------
        # Text analysis section
        # ----------------------------------------------------------------
        if analysis_results:
            pdf.add_page()
            pdf.section_title("Text Field Analysis")
            items = list(analysis_results.values())
            for i, info in enumerate(items):
                _progress(
                    TXT_START + (i / len(items)) * (TXT_END - TXT_START),
                    f"Text analysis: question {i + 1} of {len(items)}...",
                )
                pdf.column_title(info["question"])
                pdf.body_text(info["summary"])
                pdf.ln(3)

            _progress(TXT_END, "Text analysis section done.")

        _progress(0.93, "Finalising PDF...")
        output = pdf.output(dest='S')
        if isinstance(output, (bytes, bytearray)):
            result = bytes(output)
        else:
            result = output.encode("latin-1")

        _progress(1.0, "Done.")
        return result

    finally:
        for f in temp_files:
            try:
                Path(f).unlink()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Transcript Report
# ---------------------------------------------------------------------------

def generate_transcript_report(
    result: dict,
    transcript_name: str = "Transcript",
    progress_callback=None,
) -> bytes:
    """
    Generate a PDF report from transcript analysis results.
    No charts — text and tables only.
    progress_callback(fraction: float, message: str) is optional.
    """
    def _progress(fraction, message):
        if progress_callback:
            progress_callback(fraction, message)

    _progress(0.0, "Building cover page...")
    pdf = SurveyPDF(_sanitize(transcript_name))

    # ----------------------------------------------------------------
    # Cover page
    # ----------------------------------------------------------------
    pdf.add_page()
    pdf.ln(16)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(26, 95, 173)
    pdf.multi_cell(0, 13, "Interview Transcript Analysis", align="C")
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 8, _sanitize(transcript_name), align="C")
    pdf.ln(2)

    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 8, f"Generated {datetime.now().strftime('%B %d, %Y at %H:%M')}", align="C", ln=True)
    pdf.ln(10)

    speakers = result.get("speakers", [])
    talk_ratio = result.get("talk_ratio", {})

    if speakers:
        metrics = {"Speakers": str(len(speakers))}
        for spk in speakers:
            metrics[_sanitize(spk)] = f"{talk_ratio.get(spk, 0):.0%}"
        col_w = 180 / len(metrics)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(26, 95, 173)
        pdf.set_fill_color(240, 244, 250)
        for label in metrics:
            pdf.cell(col_w, 8, label, border=1, align="C", fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 30, 30)
        for val in metrics.values():
            pdf.cell(col_w, 12, val, border=1, align="C")
        pdf.ln(12)
        pdf.set_text_color(0, 0, 0)

    _progress(0.15, "Cover page done.")

    # ----------------------------------------------------------------
    # Analysis page
    # ----------------------------------------------------------------
    pdf.add_page()

    _progress(0.25, "Writing summary...")
    pdf.section_title("Summary")
    pdf.body_text(result.get("summary") or "")

    themes = result.get("themes") or []
    _progress(0.40, "Writing themes...")
    if themes:
        pdf.section_title("Themes")
        pdf.body_text("  *  ".join(t for t in themes if t))

    quotes = result.get("key_quotes") or []
    _progress(0.55, "Writing key quotes...")
    if quotes:
        pdf.section_title("Key Quotes")
        for q in quotes:
            if not isinstance(q, dict):
                continue
            speaker = _sanitize(q.get("speaker") or "")
            quote = _sanitize(q.get("quote") or "")
            if not quote:
                continue
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 6, f'"{quote}"')
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(26, 95, 173)
            pdf.cell(0, 6, f"-- {speaker}", ln=True)
            pdf.ln(4)
        pdf.set_text_color(0, 0, 0)

    sentiment = result.get("sentiment") or {}
    _progress(0.70, "Writing sentiment...")
    if sentiment:
        pdf.section_title("Sentiment")
        if isinstance(sentiment, str):
            pdf.body_text(sentiment)
        else:
            overall = sentiment.get("overall") or ""
            tone = sentiment.get("tone") or ""
            label = f"{overall.capitalize()} -- {tone}" if overall and tone else overall or tone
            if label:
                pdf.body_text(label)
            for moment in (sentiment.get("notable_moments") or []):
                if not moment:
                    continue
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(70, 70, 70)
                pdf.multi_cell(0, 6, _sanitize(f"* {moment}"))
            pdf.ln(4)
            pdf.set_text_color(0, 0, 0)

    speaker_sentiment = result.get("speaker_sentiment") or {}
    _progress(0.85, "Writing speaker breakdown...")
    if speakers:
        pdf.section_title("Speaker Breakdown")
        if talk_ratio:
            pdf.stats_table({_sanitize(spk): f"{talk_ratio.get(spk, 0):.0%}" for spk in speakers})
        if speaker_sentiment:
            for spk in speakers:
                sent = speaker_sentiment.get(spk)
                if sent:
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.set_text_color(30, 30, 30)
                    pdf.cell(0, 7, _sanitize(spk), ln=True)
                    pdf.body_text(sent)

    _progress(0.93, "Finalising PDF...")
    output = pdf.output(dest='S')
    if isinstance(output, (bytes, bytearray)):
        pdf_bytes = bytes(output)
    else:
        pdf_bytes = output.encode("latin-1")

    _progress(1.0, "Done.")
    return pdf_bytes

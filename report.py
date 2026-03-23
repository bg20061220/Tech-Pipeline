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
    img_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=2)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.write(img_bytes)
    tmp.close()
    return tmp.name


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
        self.cell(0, 9, text.upper(), ln=True)
        self.set_draw_color(26, 95, 173)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def column_title(self, text):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, text)
        self.ln(1)
        self.set_text_color(0, 0, 0)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(70, 70, 70)
        self.multi_cell(0, 6, text)
        self.ln(2)
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
        self.ln(5)
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
) -> bytes:
    temp_files = []

    try:
        pdf = SurveyPDF(survey_name)

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

        # ----------------------------------------------------------------
        # Numerical section
        # ----------------------------------------------------------------
        if not df_numerical.empty:
            pdf.add_page()
            pdf.section_title(f"Numerical Columns  ({df_numerical.shape[1]})")

            for col_id in df_numerical.columns:
                label = column_map.get(col_id, {}).get("original", col_id)
                series = df_numerical[col_id].dropna().astype(float)
                if series.empty:
                    continue

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
                tmp = _fig_to_tempfile(fig)
                temp_files.append(tmp)
                pdf.image(tmp, w=170)
                pdf.ln(8)

        # ----------------------------------------------------------------
        # Categorical section
        # ----------------------------------------------------------------
        if not df_categorical.empty:
            pdf.add_page()
            pdf.section_title(f"Categorical Columns  ({df_categorical.shape[1]})")

            for col_id in df_categorical.columns:
                label = column_map.get(col_id, {}).get("original", col_id)
                counts = df_categorical[col_id].value_counts().reset_index()
                counts.columns = ["value", "count"]

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
                pdf.ln(8)

        # ----------------------------------------------------------------
        # Text analysis section
        # ----------------------------------------------------------------
        if analysis_results:
            pdf.add_page()
            pdf.section_title("Text Field Analysis")
            for info in analysis_results.values():
                pdf.column_title(info["question"])
                pdf.body_text(info["summary"])
                pdf.ln(3)

        return bytes(pdf.output())

    finally:
        for f in temp_files:
            try:
                Path(f).unlink()
            except Exception:
                pass

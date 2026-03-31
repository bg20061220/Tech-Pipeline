import os
import io
import json
import base64
import time
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from pathlib import Path
from dotenv import load_dotenv
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_js_eval import streamlit_js_eval
from pipeline import run_pipeline
from analysis import run_analysis
from report import generate_report, generate_transcript_report
from transcript import analyze_transcript

load_dotenv()

STORAGE_KEY = "tech_pipeline_cache"
STORAGE_LIMIT_MB = 5

# --- Browser sessionStorage helpers ---

def _build_payload():
    payload = {}
    if "column_map" in st.session_state:
        payload["session"] = {
            "column_map": st.session_state["column_map"],
            "timestamp": pd.DataFrame({"timestamp": st.session_state["timestamp"]}).to_json(orient="split"),
            "df_numerical": st.session_state["df_numerical"].to_json(orient="split"),
            "df_categorical": st.session_state["df_categorical"].to_json(orient="split"),
            "df_text": st.session_state["df_text"].to_json(orient="split"),
            "file_bytes": base64.b64encode(st.session_state["file_bytes"]).decode(),
            "survey_name": st.session_state.get("survey_name", "Survey"),
        }
    if "analysis_results" in st.session_state:
        payload["analysis_results"] = st.session_state["analysis_results"]
    if "transcript_result" in st.session_state:
        payload["transcript_result"] = st.session_state["transcript_result"]
        payload["transcript_text"] = st.session_state.get("transcript_text", "")
        payload["transcript_name"] = st.session_state.get("transcript_name", "Transcript")
    return json.dumps(payload)


def save_cache():
    payload_str = _build_payload()
    size_mb = len(payload_str.encode()) / (1024 * 1024)
    if size_mb > STORAGE_LIMIT_MB:
        st.warning(
            f"Session data is {size_mb:.1f} MB — exceeds the {STORAGE_LIMIT_MB} MB browser "
            "sessionStorage limit. Your session will not be restored after a page refresh."
        )
        return
    b64 = base64.b64encode(payload_str.encode()).decode()
    components.html(
        f"<script>sessionStorage.setItem('{STORAGE_KEY}', atob('{b64}'));</script>",
        height=0,
    )


def restore_cache(json_str):
    try:
        data = json.loads(json_str)
    except Exception:
        return False
    if "session" in data:
        s = data["session"]
        st.session_state["column_map"] = s["column_map"]
        ts_df = pd.read_json(io.StringIO(s["timestamp"]), orient="split")
        st.session_state["timestamp"] = pd.to_datetime(ts_df["timestamp"])
        st.session_state["df_numerical"] = pd.read_json(io.StringIO(s["df_numerical"]), orient="split")
        st.session_state["df_categorical"] = pd.read_json(io.StringIO(s["df_categorical"]), orient="split")
        st.session_state["df_text"] = pd.read_json(io.StringIO(s["df_text"]), orient="split")
        st.session_state["file_bytes"] = base64.b64decode(s["file_bytes"])
        st.session_state["survey_name"] = s.get("survey_name", "Survey")
    if "analysis_results" in data:
        st.session_state["analysis_results"] = data["analysis_results"]
    if "transcript_result" in data:
        st.session_state["transcript_result"] = data["transcript_result"]
        st.session_state["transcript_text"] = data.get("transcript_text", "")
        st.session_state["transcript_name"] = data.get("transcript_name", "Transcript")
    return True


def clear_session():
    components.html(
        f"<script>sessionStorage.removeItem('{STORAGE_KEY}');</script>",
        height=0,
    )
    for key in ["column_map", "timestamp", "df_numerical", "df_categorical", "df_text",
                "file_bytes", "survey_name", "analysis_results", "pdf_bytes",
                "transcript_result", "transcript_text", "transcript_name", "transcript_pdf_bytes"]:
        st.session_state.pop(key, None)
    # Keep storage_checked=True so the startup restore block doesn't re-read
    # sessionStorage before the clear script has had a chance to execute.
    st.session_state["storage_checked"] = True


# --- Page config ---

st.set_page_config(page_title="Survey Analysis Pipeline", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1A5FAD;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Survey Analysis Pipeline")
st.caption("Google Forms / Google Sheets export → typed dataframes ready for analysis.")

# --- Restore from sessionStorage on first load ---
# streamlit_js_eval is async: returns None on the first render while JS executes,
# then returns the real value on the rerun it triggers. st.stop() blocks the rest
# of the page from rendering until the storage check is complete.
if "storage_checked" not in st.session_state:
    cached_json = streamlit_js_eval(
        js_expressions=f"sessionStorage.getItem('{STORAGE_KEY}') || '__empty__'",
        key="init_cache_read",
    )
    if cached_json is None:
        st.stop()
    st.session_state["storage_checked"] = True
    if cached_json != "__empty__":
        if restore_cache(cached_json):
            st.toast("Session restored from cache.", icon="✅")

# --- File uploaders ---
uploaded_file = st.file_uploader("Drop your CSV file here", type=["csv"])
uploaded_transcript = st.file_uploader("Drop an interview transcript here (.txt)", type=["txt"])

if uploaded_file is not None:
    survey_name = Path(uploaded_file.name).stem
    with st.spinner("Running pipeline..."):
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        result = run_pipeline(uploaded_file)

    st.session_state["column_map"] = result["column_map"]
    st.session_state["timestamp"] = result["timestamp"]
    st.session_state["df_numerical"] = result["df_numerical"]
    st.session_state["df_categorical"] = result["df_categorical"]
    st.session_state["df_text"] = result["df_text"]
    st.session_state["file_bytes"] = file_bytes
    st.session_state["survey_name"] = survey_name
    st.session_state.pop("analysis_results", None)
    st.session_state.pop("pdf_bytes", None)

    save_cache()

# --- Transcript uploader handler ---
if uploaded_transcript is not None:
    if not uploaded_transcript.name.lower().endswith(".txt"):
        st.error(f'"{uploaded_transcript.name}" is not a .txt file. Only plain text (.txt) transcripts are supported.')
        uploaded_transcript = None
    else:
        transcript_text = uploaded_transcript.read().decode("utf-8", errors="replace")
        st.session_state["transcript_text"] = transcript_text
        st.session_state["transcript_name"] = Path(uploaded_transcript.name).stem
        st.session_state.pop("transcript_result", None)
        st.session_state.pop("transcript_pdf_bytes", None)

# --- Transcript Analysis section ---
if "transcript_text" in st.session_state:
    st.divider()
    transcript_name = st.session_state.get("transcript_name", "Transcript")
    st.markdown(f'<p class="section-header">Interview Transcript — {transcript_name}</p>', unsafe_allow_html=True)

    env_key = os.getenv("GROQ_API_KEY", "")
    if env_key:
        transcript_api_key = env_key
    else:
        transcript_api_key = st.text_input("Groq API Key (transcript)", type="password", placeholder="gsk_...", key="transcript_api_key_input")

    if st.button("Analyse Transcript", disabled=not (env_key or transcript_api_key)):
        t_progress = st.progress(0, text="Starting analysis...")
        t_status = st.empty()
        steps = [
            (0.1, "Parsing transcript..."),
            (0.3, "Identifying speakers..."),
            (0.5, "Sending to LLM..."),
            (0.8, "Processing response..."),
            (0.95, "Finalising..."),
        ]
        for frac, msg in steps:
            t_progress.progress(frac, text=msg)
            t_status.text(msg)
            time.sleep(0.3)
        result = analyze_transcript(
            st.session_state["transcript_text"],
            env_key or transcript_api_key,
        )
        t_progress.progress(1.0, text="Done.")
        t_progress.empty()
        t_status.empty()
        st.session_state["transcript_result"] = result
        st.session_state.pop("transcript_pdf_bytes", None)
        save_cache()

    if "transcript_result" in st.session_state:
        result = st.session_state["transcript_result"]

        if result.get("speakers"):
            st.caption(f"Speakers detected: {', '.join(result['speakers'])}")

        st.markdown("**Summary**")
        st.write(result["summary"])

        if result.get("themes"):
            st.markdown("**Themes**")
            st.write("  ·  ".join(f"`{t}`" for t in result["themes"]))

        if result.get("key_quotes"):
            st.markdown("**Key Quotes**")
            for q in result["key_quotes"]:
                st.markdown(f"> *\"{q['quote']}\"*  \n> — **{q['speaker']}**")

        sentiment = result.get("sentiment", {})
        if sentiment:
            st.markdown("**Sentiment**")
            if isinstance(sentiment, str):
                st.write(sentiment)
            else:
                overall = sentiment.get("overall", "")
                tone = sentiment.get("tone", "")
                label = f"{overall.capitalize()} — {tone}" if overall and tone else overall or tone
                if label:
                    st.write(label)
                for moment in sentiment.get("notable_moments", []):
                    st.markdown(f"- {moment}")

        speaker_sentiment = result.get("speaker_sentiment", {})
        talk_ratio = result.get("talk_ratio", {})
        if speaker_sentiment or talk_ratio:
            st.markdown("**Speaker Breakdown**")
            rows = [
                {
                    "Speaker": spk,
                    "Talk Ratio": f"{talk_ratio.get(spk, 0):.0%}",
                    "Sentiment": speaker_sentiment.get(spk, "—"),
                }
                for spk in result.get("speakers", list(speaker_sentiment.keys()))
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # --- Transcript PDF ---
        st.divider()
        if st.button("Generate Report", key="transcript_generate_report"):
            t_pdf_progress = st.progress(0, text="Starting...")
            t_pdf_status = st.empty()

            def on_transcript_progress(fraction, message):
                t_pdf_progress.progress(min(fraction, 1.0), text=message)
                t_pdf_status.text(message)

            try:
                pdf_bytes = generate_transcript_report(
                    result,
                    transcript_name=transcript_name,
                    progress_callback=on_transcript_progress,
                )
                t_pdf_progress.empty()
                t_pdf_status.empty()
                st.session_state["transcript_pdf_bytes"] = pdf_bytes
                st.rerun()
            except Exception as e:
                t_pdf_progress.empty()
                t_pdf_status.empty()
                st.error(f"Report generation failed: {e}")

        if "transcript_pdf_bytes" in st.session_state:
            st.download_button(
                label="Download PDF",
                data=st.session_state["transcript_pdf_bytes"],
                file_name=f"{transcript_name}_transcript_report.pdf",
                mime="application/pdf",
            )

    # Clear transcript button
    if st.button("🗑 Clear Transcript"):
        for key in ["transcript_text", "transcript_name", "transcript_result", "transcript_pdf_bytes"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()

# --- Render if session data exists ---
if "column_map" in st.session_state:
    column_map = st.session_state["column_map"]
    timestamp = st.session_state["timestamp"]
    df_numerical = st.session_state["df_numerical"]
    df_categorical = st.session_state["df_categorical"]
    df_text = st.session_state["df_text"]
    file_bytes = st.session_state["file_bytes"]
    survey_name = st.session_state.get("survey_name", "Survey")

    # Clear session button
    if st.button("🗑 Clear Session"):
        clear_session()
        st.rerun()

    # --- Summary metrics ---
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Responses", len(timestamp))
    c2.metric("Numerical Columns", df_numerical.shape[1])
    c3.metric("Categorical Columns", df_categorical.shape[1])
    c4.metric("Text Columns", df_text.shape[1])
    style_metric_cards(background_color="#F0F4FA", border_left_color="#1A5FAD")

    st.divider()

    # --- Column Map ---
    st.markdown('<p class="section-header">Column Map</p>', unsafe_allow_html=True)
    col_map_rows = [
        {"col_id": col_id, "original_header": info["original"], "type": info["type"]}
        for col_id, info in column_map.items()
    ]
    col_map_df = pd.DataFrame(col_map_rows)

    st.caption("You can override the detected type for any column below.")
    TYPE_OPTIONS = ["datetime", "numerical", "categorical", "text"]
    edited_map_df = st.data_editor(
        col_map_df,
        column_config={
            "col_id": st.column_config.TextColumn("Col ID", disabled=True),
            "original_header": st.column_config.TextColumn("Original Header", disabled=True),
            "type": st.column_config.SelectboxColumn("Type", options=TYPE_OPTIONS),
        },
        use_container_width=True,
        hide_index=True,
        key="col_map_editor",
    )

    overrides_applied = not edited_map_df["type"].equals(col_map_df["type"])
    if overrides_applied:
        st.info("Type overrides detected — re-running split with your changes.")
        for _, row in edited_map_df.iterrows():
            column_map[row["col_id"]]["type"] = row["type"]

        from pipeline import handle_nulls, split_dataframes, load_csv, rename_columns
        raw_df = load_csv(io.BytesIO(file_bytes))
        df_internal = rename_columns(raw_df)
        df_internal = handle_nulls(df_internal, column_map)
        df_numerical, df_categorical, df_text = split_dataframes(df_internal, column_map)

        st.session_state["column_map"] = column_map
        st.session_state["df_numerical"] = df_numerical
        st.session_state["df_categorical"] = df_categorical
        st.session_state["df_text"] = df_text

        save_cache()

    st.divider()

    # --- Numerical ---
    st.markdown(f'<p class="section-header">Numerical Columns — {df_numerical.shape[1]} cols</p>', unsafe_allow_html=True)
    if df_numerical.empty:
        st.write("_No numerical columns detected._")
    else:
        for col_id in df_numerical.columns:
            label = column_map.get(col_id, {}).get("original", col_id)
            series = df_numerical[col_id].dropna().astype(float)

            left, right = st.columns([1, 2])

            with left:
                st.subheader(label)

                mean_val = series.mean()
                median_val = series.median()
                mode_vals = series.mode()
                mode_val = mode_vals.iloc[0] if not mode_vals.empty else float("nan")
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)

                s1, s2 = st.columns(2)
                s1.metric("Mean", f"{mean_val:.2f}")
                s2.metric("Median", f"{median_val:.2f}")
                s3, s4, s5 = st.columns(3)
                s3.metric("Mode", f"{mode_val:.2f}")
                s4.metric("Q1 (25%)", f"{q1:.2f}")
                s5.metric("Q3 (75%)", f"{q3:.2f}")

            with right:
                fig = px.histogram(
                    series,
                    x=col_id,
                    nbins=20,
                    labels={col_id: label},
                    color_discrete_sequence=["#1A5FAD"],
                )
                fig.update_layout(
                    margin=dict(t=20, b=20),
                    xaxis_title=label,
                    yaxis_title="Count",
                    bargap=0.05,
                    dragmode=False,
                )
                st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})

            st.divider()

    # --- Categorical ---
    st.markdown(f'<p class="section-header">Categorical Columns — {df_categorical.shape[1]} cols</p>', unsafe_allow_html=True)
    if df_categorical.empty:
        st.write("_No categorical columns detected._")
    else:
        for col_id in df_categorical.columns:
            label = column_map.get(col_id, {}).get("original", col_id)
            counts = df_categorical[col_id].value_counts().reset_index()
            counts.columns = ["value", "count"]

            left, right = st.columns([1, 2])

            with left:
                st.subheader(label)

            with right:
                fig = px.pie(
                    counts,
                    names="value",
                    values="count",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(margin=dict(t=20, b=20), showlegend=True, dragmode=False)
                st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})

            st.divider()

    # --- Text ---
    st.markdown(f'<p class="section-header">Text Columns — {df_text.shape[1]} cols</p>', unsafe_allow_html=True)
    if df_text.empty:
        st.write("_No free-text columns detected._")
    else:
        for col_id in df_text.columns:
            label = column_map.get(col_id, {}).get("original", col_id)
            st.markdown(f"- {label}")

    st.divider()

    # --- Text Analysis ---
    st.markdown('<p class="section-header">Text Field Analysis</p>', unsafe_allow_html=True)
    if df_text.empty:
        st.write("_No free-text columns to analyse._")
    else:
        env_key = os.getenv("GROQ_API_KEY", "")
        if env_key:
            st.caption("Groq API key loaded from `.env`.")
            groq_api_key = env_key
        else:
            groq_api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")

        if st.button("Run Analysis on Text Fields", disabled=not groq_api_key):
            with st.spinner(f"Analysing {df_text.shape[1]} text column(s)..."):
                analysis_results = run_analysis(df_text, column_map, groq_api_key)
            st.session_state["analysis_results"] = analysis_results
            st.session_state.pop("pdf_bytes", None)
            save_cache()

        if "analysis_results" in st.session_state and st.session_state["analysis_results"]:
            results = st.session_state["analysis_results"]
            for info in results.values():
                st.markdown(f"**{info['question']}**")
                st.write(info["summary"])
                st.divider()

    # --- PDF Report ---
    st.divider()
    st.markdown('<p class="section-header">PDF Report</p>', unsafe_allow_html=True)

    if st.button("Generate Report", key="csv_generate_report"):
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()

        def on_progress(fraction, message):
            progress_bar.progress(min(fraction, 1.0), text=message)
            status_text.text(message)

        MAX_ATTEMPTS = 2
        pdf_bytes = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                if attempt > 0:
                    on_progress(0.0, "Something went wrong — retrying...")
                pdf_bytes = generate_report(
                    column_map, df_numerical, df_categorical, df_text, timestamp,
                    st.session_state.get("analysis_results"),
                    survey_name=survey_name,
                    progress_callback=on_progress,
                )
                break
            except Exception as e:
                if attempt == MAX_ATTEMPTS - 1:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"Report generation failed: {e}")

        if pdf_bytes:
            progress_bar.empty()
            status_text.empty()
            st.session_state["pdf_bytes"] = pdf_bytes
            st.success("Report ready.")

    if "pdf_bytes" in st.session_state:
        st.download_button(
            label="Download PDF",
            data=st.session_state["pdf_bytes"],
            file_name=f"{survey_name}_report.pdf",
            mime="application/pdf",
        )

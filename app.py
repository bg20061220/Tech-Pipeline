import os
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from streamlit_extras.metric_cards import style_metric_cards
from pipeline import run_pipeline
from analysis import run_analysis

load_dotenv()

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

uploaded_file = st.file_uploader("Drop your CSV file here", type=["csv"])

if uploaded_file is not None:
    with st.spinner("Running pipeline..."):
        result = run_pipeline(uploaded_file)

    column_map = result["column_map"]
    timestamp = result["timestamp"]
    df_numerical = result["df_numerical"]
    df_categorical = result["df_categorical"]
    df_text = result["df_text"]

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
        uploaded_file.seek(0)
        raw_df = load_csv(uploaded_file)
        df_internal = rename_columns(raw_df)
        df_internal = handle_nulls(df_internal, column_map)
        df_numerical, df_categorical, df_text = split_dataframes(df_internal, column_map)

    st.divider()

    # --- Numerical ---
    st.markdown(f'<p class="section-header">Numerical Columns — {df_numerical.shape[1]} cols</p>', unsafe_allow_html=True)
    if df_numerical.empty:
        st.write("_No numerical columns detected._")
    else:
        for col_id in df_numerical.columns:
            label = column_map.get(col_id, {}).get("original", col_id)
            series = df_numerical[col_id].dropna().astype(float)

            st.subheader(label)

            # Stats
            mean_val = series.mean()
            median_val = series.median()
            mode_vals = series.mode()
            mode_val = mode_vals.iloc[0] if not mode_vals.empty else float("nan")
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)

            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Mean", f"{mean_val:.2f}")
            s2.metric("Median", f"{median_val:.2f}")
            s3.metric("Mode", f"{mode_val:.2f}")
            s4.metric("Q1 (25%)", f"{q1:.2f}")
            s5.metric("Q3 (75%)", f"{q3:.2f}")

            # Histogram
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

            st.subheader(label)

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

        if "analysis_results" in st.session_state and st.session_state["analysis_results"]:
            results = st.session_state["analysis_results"]
            for info in results.values():
                st.markdown(f"**{info['question']}**")
                st.write(info["summary"])
                st.divider()

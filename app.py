import streamlit as st
import pandas as pd
from pipeline import run_pipeline

st.set_page_config(page_title="CSV Parsing Pipeline", layout="wide")
st.title("CSV Parsing Pipeline")
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

    st.success(f"Parsed {len(timestamp)} rows across {len(column_map)} columns.")

    # --- Column Map ---
    st.header("Column Map")
    col_map_rows = [
        {"col_id": col_id, "original_header": info["original"], "type": info["type"]}
        for col_id, info in column_map.items()
    ]
    col_map_df = pd.DataFrame(col_map_rows)

    # Manual override
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

    # Apply overrides if user changed anything
    overrides_applied = not edited_map_df["type"].equals(col_map_df["type"])
    if overrides_applied:
        st.info("Type overrides detected — re-running split with your changes.")
        for _, row in edited_map_df.iterrows():
            column_map[row["col_id"]]["type"] = row["type"]

        # Re-split with updated types
        from pipeline import handle_nulls, split_dataframes
        # Re-load from uploaded file to get clean df
        uploaded_file.seek(0)
        from pipeline import load_csv, rename_columns
        raw_df = load_csv(uploaded_file)
        df_internal = rename_columns(raw_df)
        df_internal = handle_nulls(df_internal, column_map)
        df_numerical, df_categorical, df_text = split_dataframes(df_internal, column_map)

    st.divider()

    # --- Timestamp ---
    st.header("Timestamp Series (col_0)")
    ts_df = timestamp.to_frame(name="timestamp")
    ts_df.index.name = "row"
    st.dataframe(ts_df, use_container_width=True, height=200)

    st.divider()

    # --- Numerical ---
    st.header(f"df_numerical  ({df_numerical.shape[0]} rows × {df_numerical.shape[1]} cols)")
    if df_numerical.empty:
        st.write("_No numerical columns detected._")
    else:
        # Show human-readable headers in display
        display_cols = {c: column_map[c]["original"] for c in df_numerical.columns if c in column_map}
        st.dataframe(df_numerical.rename(columns=display_cols), use_container_width=True, height=300)
        st.subheader("Descriptive Statistics")
        st.dataframe(df_numerical.describe().rename(columns=display_cols), use_container_width=True)

    st.divider()

    # --- Categorical ---
    st.header(f"df_categorical  ({df_categorical.shape[0]} rows × {df_categorical.shape[1]} cols)")
    if df_categorical.empty:
        st.write("_No categorical columns detected._")
    else:
        display_cols = {c: column_map[c]["original"] for c in df_categorical.columns if c in column_map}
        st.dataframe(df_categorical.rename(columns=display_cols), use_container_width=True, height=300)
        st.subheader("Value Counts")
        for col_id in df_categorical.columns:
            label = column_map.get(col_id, {}).get("original", col_id)
            counts = df_categorical[col_id].value_counts().reset_index()
            counts.columns = ["value", "count"]
            with st.expander(label):
                st.bar_chart(counts.set_index("value")["count"])

    st.divider()

    # --- Text ---
    st.header(f"df_text  ({df_text.shape[0]} rows × {df_text.shape[1]} cols)")
    if df_text.empty:
        st.write("_No free-text columns detected._")
    else:
        display_cols = {c: column_map[c]["original"] for c in df_text.columns if c in column_map}
        st.dataframe(df_text.rename(columns=display_cols), use_container_width=True, height=300)

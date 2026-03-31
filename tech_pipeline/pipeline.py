"""
CSV Parsing Pipeline
Google Forms / Google Sheets export → typed pandas dataframes ready for analysis.
"""

import pandas as pd
import numpy as np


def load_csv(file) -> pd.DataFrame:
    """Step 1: Load CSV with all columns as raw strings, drop fully empty rows."""
    df = pd.read_csv(file, dtype=str, keep_default_na=False)
    df = df.replace("", np.nan)
    df = df.dropna(how="all")
    return df


def extract_column_map(df: pd.DataFrame) -> dict:
    """Step 2: Build column map {col_id: original_header}."""
    return {f"col_{i}": col for i, col in enumerate(df.columns)}


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Step 3: Rename columns to col_0, col_1, ..."""
    df = df.copy()
    df.columns = [f"col_{i}" for i in range(len(df.columns))]
    return df


def parse_timestamp(df: pd.DataFrame) -> pd.Series:
    """Step 4: Parse col_0 (Timestamp) as datetime."""
    return pd.to_datetime(df["col_0"], errors="coerce")


def classify_column(series: pd.Series) -> str:
    """Step 5: Classify a single column as numerical, categorical, or text."""
    non_null = series.dropna()
    if non_null.empty:
        return "categorical"

    # Try numerical: all values coerce to float
    numeric_converted = pd.to_numeric(non_null, errors="coerce")
    if numeric_converted.notna().all():
        return "numerical"

    # Text signals — check before categorical to handle low-response surveys
    avg_len = non_null.str.len().mean()
    unique_ratio = non_null.nunique() / len(non_null)

    if avg_len > 30 or unique_ratio > 0.6:
        return "text"

    # Categorical: small fixed set of short repeated values
    if non_null.nunique() <= 8:
        return "categorical"

    return "text"


def build_typed_column_map(df: pd.DataFrame, column_map: dict) -> dict:
    """Enrich column_map with type info for each column (skip col_0)."""
    typed_map = {}
    for col_id, original_header in column_map.items():
        if col_id == "col_0":
            typed_map[col_id] = {"original": original_header, "type": "datetime"}
        else:
            col_type = classify_column(df[col_id])
            typed_map[col_id] = {"original": original_header, "type": col_type}
    return typed_map


def handle_nulls(df: pd.DataFrame, typed_map: dict) -> pd.DataFrame:
    """Step 6: Handle nulls per column type."""
    df = df.copy()
    for col_id, info in typed_map.items():
        if col_id not in df.columns:
            continue
        if info["type"] == "numerical":
            df[col_id] = pd.to_numeric(df[col_id], errors="coerce")
        elif info["type"] == "categorical":
            df[col_id] = df[col_id].fillna("no_response")
    return df


def split_dataframes(df: pd.DataFrame, typed_map: dict) -> tuple:
    """Step 7: Split into df_numerical, df_categorical, df_text."""
    numerical_cols = [c for c, info in typed_map.items() if info["type"] == "numerical"]
    categorical_cols = [c for c, info in typed_map.items() if info["type"] == "categorical"]
    text_cols = [c for c, info in typed_map.items() if info["type"] == "text"]

    df_numerical = df[numerical_cols].copy() if numerical_cols else pd.DataFrame()
    df_categorical = df[categorical_cols].copy() if categorical_cols else pd.DataFrame()
    df_text = df[text_cols].copy() if text_cols else pd.DataFrame()

    # Drop fully empty text rows
    if not df_text.empty:
        df_text = df_text.dropna(how="all")

    return df_numerical, df_categorical, df_text


def run_pipeline(file) -> dict:
    """
    Full pipeline entry point.
    Returns:
        {
            "column_map": typed column map dict,
            "timestamp": pd.Series,
            "df_numerical": pd.DataFrame,
            "df_categorical": pd.DataFrame,
            "df_text": pd.DataFrame,
        }
    """
    raw_df = load_csv(file)
    column_map_raw = extract_column_map(raw_df)
    df = rename_columns(raw_df)
    timestamp = parse_timestamp(df)
    typed_map = build_typed_column_map(df, column_map_raw)
    df = handle_nulls(df, typed_map)
    df_numerical, df_categorical, df_text = split_dataframes(df, typed_map)

    return {
        "column_map": typed_map,
        "timestamp": timestamp,
        "df_numerical": df_numerical,
        "df_categorical": df_categorical,
        "df_text": df_text,
    }

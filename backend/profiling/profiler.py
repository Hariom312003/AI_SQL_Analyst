"""Automated data profiling (module: Data Profiling)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_round(value, ndigits: int = 3):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), ndigits)


def profile_dataframe(df: pd.DataFrame) -> dict:
    n_rows = len(df)
    missing = df.isna().sum()

    profile: dict = {
        "row_count": n_rows,
        "column_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": {},
    }

    numeric_df = df.select_dtypes(include=[np.number])
    profile["correlations"] = (
        numeric_df.corr(numeric_only=True).round(3).to_dict() if numeric_df.shape[1] > 1 else {}
    )

    for col in df.columns:
        series = df[col]
        col_profile = {
            "dtype": str(series.dtype),
            "missing_count": int(missing[col]),
            "missing_pct": round(float(missing[col]) / n_rows * 100, 2) if n_rows else 0.0,
            "unique_count": int(series.nunique(dropna=True)),
        }

        if pd.api.types.is_numeric_dtype(series):
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = series[(series < lower) | (series > upper)]
            col_profile.update(
                {
                    "mean": _safe_round(series.mean()),
                    "std": _safe_round(series.std()),
                    "min": _safe_round(series.min()),
                    "max": _safe_round(series.max()),
                    "p25": _safe_round(q1),
                    "p50": _safe_round(series.median()),
                    "p75": _safe_round(q3),
                    "outlier_count": int(outliers.shape[0]),
                }
            )
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_profile.update(
                {
                    "min_date": str(series.min()) if series.notna().any() else None,
                    "max_date": str(series.max()) if series.notna().any() else None,
                }
            )
        else:
            top_values = series.value_counts(dropna=True).head(5)
            col_profile["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        profile["columns"][col] = col_profile

    return profile

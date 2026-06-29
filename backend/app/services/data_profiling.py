import polars as pl
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from app.services.data_ingestion import data_ingestion_service


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    category: str
    missing_count: int
    missing_percentage: float
    unique_count: int
    unique_percentage: float
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    mean_value: Optional[float] = None
    median_value: Optional[float] = None
    std_value: Optional[float] = None
    quantiles: Optional[Dict[str, float]] = None
    top_values: Optional[List[Dict[str, Any]]] = None
    sample_values: Optional[List[Any]] = None


class DataProfilingService:
    def __init__(self):
        self.ingestion = data_ingestion_service

    def detect_column_category(self, series: pl.Series) -> str:
        dtype = str(series.dtype)
        if dtype in ["Int64", "Int32", "Int16", "Int8", "Float64", "Float32"]:
            return "numeric"
        elif dtype in ["Datetime", "Date"]:
            return "datetime"
        elif dtype == "Boolean":
            return "boolean"
        elif dtype == "String" or dtype == "Categorical":
            return "categorical"
        return "unknown"

    def profile_column(self, series: pl.Series) -> ColumnProfile:
        category = self.detect_column_category(series)
        missing_count = series.null_count()
        missing_percentage = (missing_count / len(series)) * 100 if len(series) > 0 else 0
        unique_count = series.n_unique()
        unique_percentage = (unique_count / len(series)) * 100 if len(series) > 0 else 0
        sample_values = series.drop_nulls().head(5).to_list()

        profile = ColumnProfile(
            name=series.name,
            dtype=str(series.dtype),
            category=category,
            missing_count=missing_count,
            missing_percentage=round(missing_percentage, 2),
            unique_count=unique_count,
            unique_percentage=round(unique_percentage, 2),
            sample_values=sample_values,
        )

        if category == "numeric":
            clean_series = series.drop_nulls()
            if len(clean_series) > 0:
                profile.min_value = float(clean_series.min())
                profile.max_value = float(clean_series.max())
                profile.mean_value = float(clean_series.mean())
                profile.median_value = float(clean_series.median())
                profile.std_value = float(clean_series.std())
                quantiles = clean_series.quantile([0.25, 0.5, 0.75])
                profile.quantiles = {
                    "q1": float(quantiles[0]),
                    "q2": float(quantiles[1]),
                    "q3": float(quantiles[2]),
                }

        elif category == "categorical":
            value_counts = series.value_counts().head(10)
            profile.top_values = [
                {"value": row[series.name], "count": row["count"]}
                for row in value_counts.to_dicts()
            ]

        elif category == "datetime":
            clean_series = series.drop_nulls()
            if len(clean_series) > 0:
                profile.min_value = str(clean_series.min())
                profile.max_value = str(clean_series.max())

        return profile

    def profile_dataset(self, df: pl.DataFrame) -> Dict[str, Any]:
        profiles = []
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []
        boolean_cols = []

        for col in df.columns:
            profile = self.profile_column(df[col])
            profiles.append(profile)

            if profile.category == "numeric":
                numeric_cols.append(col)
            elif profile.category == "categorical":
                categorical_cols.append(col)
            elif profile.category == "datetime":
                datetime_cols.append(col)
            elif profile.category == "boolean":
                boolean_cols.append(col)

        duplicate_rows = df.n_unique(subset=df.columns) if len(df.columns) > 0 else len(df)
        total_duplicates = len(df) - duplicate_rows

        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "numeric_columns": len(numeric_cols),
            "categorical_columns": len(categorical_cols),
            "datetime_columns": len(datetime_cols),
            "boolean_columns": len(boolean_cols),
            "numeric_features": numeric_cols,
            "categorical_features": categorical_cols,
            "datetime_features": datetime_cols,
            "boolean_features": boolean_cols,
            "duplicate_rows": total_duplicates,
            "duplicate_percentage": round((total_duplicates / len(df)) * 100, 2) if len(df) > 0 else 0,
            "column_profiles": [vars(p) for p in profiles],
        }

    def detect_outliers_iqr(self, series: pl.Series) -> Dict[str, Any]:
        if self.detect_column_category(series) != "numeric":
            return {"method": "iqr", "outlier_count": 0, "outlier_indices": [], "bounds": {}}

        clean_series = series.drop_nulls()
        if len(clean_series) < 4:
            return {"method": "iqr", "outlier_count": 0, "outlier_indices": [], "bounds": {}}

        q1 = clean_series.quantile(0.25)
        q3 = clean_series.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outlier_mask = (series < lower_bound) | (series > upper_bound)
        outlier_indices = outlier_mask.arg_true().to_list()
        outlier_count = len(outlier_indices)

        return {
            "method": "iqr",
            "outlier_count": outlier_count,
            "outlier_indices": outlier_indices,
            "bounds": {
                "lower": float(lower_bound),
                "upper": float(upper_bound),
                "q1": float(q1),
                "q3": float(q3),
                "iqr": float(iqr),
            },
        }

    def detect_outliers_zscore(self, series: pl.Series, threshold: float = 3.0) -> Dict[str, Any]:
        if self.detect_column_category(series) != "numeric":
            return {"method": "zscore", "outlier_count": 0, "outlier_indices": [], "threshold": threshold}

        clean_series = series.drop_nulls()
        if len(clean_series) < 2:
            return {"method": "zscore", "outlier_count": 0, "outlier_indices": [], "threshold": threshold}

        mean_val = clean_series.mean()
        std_val = clean_series.std()
        if std_val == 0:
            return {"method": "zscore", "outlier_count": 0, "outlier_indices": [], "threshold": threshold}

        z_scores = (series - mean_val) / std_val
        outlier_mask = z_scores.abs() > threshold
        outlier_indices = outlier_mask.arg_true().to_list()
        outlier_count = len(outlier_indices)

        return {
            "method": "zscore",
            "outlier_count": outlier_count,
            "outlier_indices": outlier_indices,
            "threshold": threshold,
            "mean": float(mean_val),
            "std": float(std_val),
        }


data_profiling_service = DataProfilingService()
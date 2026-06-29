import polars as pl
import pandas as pd
import os
from typing import Tuple, Dict, Any, List
from app.core.config import settings


class DataIngestionService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)

    def detect_file_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".csv":
            return "csv"
        elif ext in [".xlsx", ".xls"]:
            return "excel"
        return "unknown"

    def read_file(self, file_path: str, file_type: str) -> pl.DataFrame:
        if file_type == "csv":
            return pl.read_csv(
                file_path,
                infer_schema_length=10000,
                try_parse_dates=True,
                truncate_ragged_lines=True,
            )
        elif file_type == "excel":
            return pl.read_excel(file_path)
        raise ValueError(f"Unsupported file type: {file_type}")

    def save_upload(self, file_content: bytes, filename: str) -> str:
        file_path = os.path.join(self.upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(file_content)
        return file_path

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

    def get_preview(self, df: pl.DataFrame, n_rows: int = 10) -> List[Dict[str, Any]]:
        return df.head(n_rows).to_dicts()

    def get_column_info(self, df: pl.DataFrame) -> List[Dict[str, Any]]:
        columns_info = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            nullable = series.null_count() > 0
            unique_count = series.n_unique()
            missing_count = series.null_count()
            missing_percentage = (missing_count / len(df)) * 100 if len(df) > 0 else 0
            sample_values = series.drop_nulls().head(5).to_list()

            columns_info.append({
                "name": col,
                "dtype": dtype,
                "nullable": nullable,
                "unique_count": unique_count,
                "missing_count": missing_count,
                "missing_percentage": round(missing_percentage, 2),
                "sample_values": sample_values,
            })
        return columns_info

    def get_data_types(self, df: pl.DataFrame) -> Dict[str, str]:
        return {col: str(df[col].dtype) for col in df.columns}

    def get_missing_values(self, df: pl.DataFrame) -> Dict[str, int]:
        return {col: df[col].null_count() for col in df.columns}


data_ingestion_service = DataIngestionService()
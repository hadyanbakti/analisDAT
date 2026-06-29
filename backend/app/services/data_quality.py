import polars as pl
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from app.services.data_profiling import data_profiling_service, ColumnProfile


@dataclass
class QualityCheck:
    check_name: str
    score: float
    max_score: float
    details: Dict[str, Any]
    passed: bool


class DataQualityService:
    def __init__(self):
        self.profiling = data_profiling_service

    def calculate_quality_score(self, df: pl.DataFrame) -> Dict[str, Any]:
        checks = []

        checks.append(self._check_missing_values(df))
        checks.append(self._check_duplicates(df))
        checks.append(self._check_outliers(df))
        checks.append(self._check_data_types(df))
        checks.append(self._check_consistency(df))
        checks.append(self._check_unique_ratios(df))

        total_score = sum(c.score for c in checks)
        max_total = sum(c.max_score for c in checks)
        overall_score = round((total_score / max_total) * 100, 1) if max_total > 0 else 0

        quality_category = self._get_quality_category(overall_score)

        return {
            "overall_score": overall_score,
            "quality_category": quality_category,
            "checks": [vars(c) for c in checks],
            "summary": {
                "total_checks": len(checks),
                "passed": sum(1 for c in checks if c.passed),
                "failed": sum(1 for c in checks if not c.passed),
            },
        }

    def _check_missing_values(self, df: pl.DataFrame) -> QualityCheck:
        total_cells = len(df) * len(df.columns)
        missing_cells = sum(df[col].null_count() for col in df.columns)
        missing_percentage = (missing_cells / total_cells) * 100 if total_cells > 0 else 0

        if missing_percentage == 0:
            score = 20
        elif missing_percentage < 5:
            score = 18
        elif missing_percentage < 15:
            score = 14
        elif missing_percentage < 30:
            score = 8
        else:
            score = 3

        missing_by_col = {col: df[col].null_count() for col in df.columns}

        return QualityCheck(
            check_name="Missing Values",
            score=score,
            max_score=20,
            details={
                "total_missing": missing_cells,
                "missing_percentage": round(missing_percentage, 2),
                "missing_by_column": missing_by_col,
            },
            passed=missing_percentage < 15,
        )

    def _check_duplicates(self, df: pl.DataFrame) -> QualityCheck:
        if len(df) == 0:
            return QualityCheck("Duplicate Records", 15, 15, {"duplicate_count": 0, "duplicate_percentage": 0}, True)

        unique_rows = df.n_unique(subset=df.columns)
        duplicate_count = len(df) - unique_rows
        duplicate_percentage = (duplicate_count / len(df)) * 100 if len(df) > 0 else 0

        if duplicate_percentage == 0:
            score = 15
        elif duplicate_percentage < 1:
            score = 12
        elif duplicate_percentage < 5:
            score = 8
        elif duplicate_percentage < 10:
            score = 4
        else:
            score = 1

        return QualityCheck(
            check_name="Duplicate Records",
            score=score,
            max_score=15,
            details={
                "duplicate_count": duplicate_count,
                "duplicate_percentage": round(duplicate_percentage, 2),
            },
            passed=duplicate_percentage < 5,
        )

    def _check_outliers(self, df: pl.DataFrame) -> QualityCheck:
        numeric_cols = [col for col in df.columns if self.profiling.detect_column_category(df[col]) == "numeric"]

        if not numeric_cols:
            return QualityCheck("Outliers", 15, 15, {"message": "No numeric columns"}, True)

        total_outliers = 0
        outlier_details = {}

        for col in numeric_cols:
            result = self.profiling.detect_outliers_iqr(df[col])
            outlier_count = result["outlier_count"]
            total_outliers += outlier_count
            outlier_details[col] = result

        total_numeric_cells = sum(len(df[col].drop_nulls()) for col in numeric_cols)
        outlier_percentage = (total_outliers / total_numeric_cells) * 100 if total_numeric_cells > 0 else 0

        if outlier_percentage == 0:
            score = 15
        elif outlier_percentage < 1:
            score = 12
        elif outlier_percentage < 5:
            score = 8
        elif outlier_percentage < 10:
            score = 4
        else:
            score = 1

        return QualityCheck(
            check_name="Outliers",
            score=score,
            max_score=15,
            details={
                "total_outliers": total_outliers,
                "outlier_percentage": round(outlier_percentage, 2),
                "by_column": outlier_details,
            },
            passed=outlier_percentage < 5,
        )

    def _check_data_types(self, df: pl.DataFrame) -> QualityCheck:
        type_issues = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)

            if dtype == "String":
                sample = series.drop_nulls().head(100)
                if len(sample) > 0:
                    numeric_like = sum(1 for v in sample if self._is_numeric_string(str(v)))
                    if numeric_like / len(sample) > 0.8:
                        type_issues.append(f"{col}: String but appears numeric")

                    date_like = sum(1 for v in sample if self._is_date_string(str(v)))
                    if date_like / len(sample) > 0.8:
                        type_issues.append(f"{col}: String but appears datetime")

        issue_count = len(type_issues)

        if issue_count == 0:
            score = 15
        elif issue_count <= 2:
            score = 12
        elif issue_count <= 5:
            score = 8
        else:
            score = 4

        return QualityCheck(
            check_name="Data Types",
            score=score,
            max_score=15,
            details={
                "type_issues": type_issues,
                "issue_count": issue_count,
            },
            passed=issue_count <= 2,
        )

    def _is_numeric_string(self, s: str) -> bool:
        try:
            float(s.replace(",", "").replace("$", "").strip())
            return True
        except:
            return False

    def _is_date_string(self, s: str) -> bool:
        import re
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\d{2}/\d{2}/\d{4}",
            r"\d{2}-\d{2}-\d{4}",
        ]
        return any(re.match(p, s.strip()) for p in date_patterns)

    def _check_consistency(self, df: pl.DataFrame) -> QualityCheck:
        consistency_issues = []

        for col in df.columns:
            series = df[col]
            if self.profiling.detect_column_category(series) == "categorical":
                values = series.drop_nulls().unique().to_list()
                if len(values) > 1:
                    lower_values = [str(v).lower().strip() for v in values]
                    if len(set(lower_values)) < len(lower_values):
                        consistency_issues.append(f"{col}: Case/whitespace inconsistency")

                    for v in values:
                        s = str(v).strip()
                        if s != str(v):
                            consistency_issues.append(f"{col}: Leading/trailing whitespace in '{v}'")
                            break

        issue_count = len(consistency_issues)

        if issue_count == 0:
            score = 15
        elif issue_count <= 3:
            score = 12
        elif issue_count <= 6:
            score = 8
        else:
            score = 4

        return QualityCheck(
            check_name="Data Consistency",
            score=score,
            max_score=15,
            details={
                "issues": consistency_issues,
                "issue_count": issue_count,
            },
            passed=issue_count <= 3,
        )

    def _check_unique_ratios(self, df: pl.DataFrame) -> QualityCheck:
        issues = []
        for col in df.columns:
            series = df[col]
            unique_count = series.n_unique()
            total_count = len(series.drop_nulls())

            if total_count > 0:
                ratio = unique_count / total_count
                if ratio == 1.0 and total_count > 10:
                    issues.append(f"{col}: All values unique (possible ID column)")
                elif ratio < 0.01 and total_count > 100:
                    issues.append(f"{col}: Very low cardinality ({ratio:.2%} unique)")

        issue_count = len(issues)

        if issue_count == 0:
            score = 20
        elif issue_count <= 2:
            score = 16
        elif issue_count <= 4:
            score = 12
        else:
            score = 8

        return QualityCheck(
            check_name="Unique Value Ratio",
            score=score,
            max_score=20,
            details={
                "issues": issues,
                "issue_count": issue_count,
            },
            passed=issue_count <= 2,
        )

    def _get_quality_category(self, score: float) -> str:
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Fair"
        else:
            return "Needs Improvement"


data_quality_service = DataQualityService()
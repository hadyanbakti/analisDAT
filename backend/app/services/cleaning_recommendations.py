import polars as pl
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from app.services.data_quality import data_quality_service, QualityCheck


@dataclass
class CleaningRecommendation:
    issue: str
    column: Optional[str]
    recommendation: str
    method: str
    priority: str


class CleaningRecommendationService:
    def __init__(self):
        self.quality_service = data_quality_service

    def generate_recommendations(self, df: pl.DataFrame, quality_result: Dict[str, Any]) -> Dict[str, Any]:
        detected_issues = []
        recommendations = []

        for check in quality_result.get("checks", []):
            check_name = check.get("check_name", "")
            details = check.get("details", {})
            passed = check.get("passed", True)

            if not passed:
                issue_recs = self._get_recommendations_for_check(check_name, df, details)
                detected_issues.extend(issue_recs["issues"])
                recommendations.extend(issue_recs["recommendations"])

        return {
            "detected_issues": detected_issues,
            "recommendations": [vars(r) for r in recommendations],
        }

    def _get_recommendations_for_check(self, check_name: str, df: pl.DataFrame, details: Dict[str, Any]) -> Dict[str, Any]:
        issues = []
        recommendations = []

        if check_name == "Missing Values":
            missing_by_col = details.get("missing_by_column", {})
            for col, count in missing_by_col.items():
                if count > 0:
                    pct = (count / len(df)) * 100
                    issues.append({"column": col, "issue": "missing_values", "count": count, "percentage": round(pct, 2)})

                    series = df[col]
                    category = self.quality_service.profiling.detect_column_category(series)

                    if category == "numeric":
                        recommendations.append(CleaningRecommendation(
                            issue="Missing values",
                            column=col,
                            recommendation=f"Replace missing values with median (robust to outliers)",
                            method="median_imputation",
                            priority="high" if pct > 10 else "medium"
                        ))
                    elif category == "categorical":
                        recommendations.append(CleaningRecommendation(
                            issue="Missing values",
                            column=col,
                            recommendation=f"Replace missing values with mode (most frequent category)",
                            method="mode_imputation",
                            priority="high" if pct > 10 else "medium"
                        ))
                    else:
                        recommendations.append(CleaningRecommendation(
                            issue="Missing values",
                            column=col,
                            recommendation=f"Consider removing rows or using domain-specific imputation",
                            method="drop_or_custom",
                            priority="medium"
                        ))

        elif check_name == "Duplicate Records":
            dup_count = details.get("duplicate_count", 0)
            dup_pct = details.get("duplicate_percentage", 0)
            if dup_count > 0:
                issues.append({"column": None, "issue": "duplicate_rows", "count": dup_count, "percentage": round(dup_pct, 2)})
                recommendations.append(CleaningRecommendation(
                    issue="Duplicate rows",
                    column=None,
                    recommendation="Remove duplicate rows keeping first occurrence",
                    method="drop_duplicates",
                    priority="high" if dup_pct > 5 else "medium"
                ))

        elif check_name == "Outliers":
            by_col = details.get("by_column", {})
            for col, outlier_info in by_col.items():
                count = outlier_info.get("outlier_count", 0)
                if count > 0:
                    total = len(df[col].drop_nulls())
                    pct = (count / total) * 100 if total > 0 else 0
                    issues.append({"column": col, "issue": "outliers", "count": count, "percentage": round(pct, 2)})
                    recommendations.append(CleaningRecommendation(
                        issue="Outliers detected",
                        column=col,
                        recommendation=f"Apply IQR-based treatment: cap values at 1.5*IQR bounds or investigate",
                        method="iqr_capping",
                        priority="medium" if pct < 5 else "high"
                    ))

        elif check_name == "Data Types":
            type_issues = details.get("type_issues", [])
            for issue in type_issues:
                col = issue.split(":")[0].strip()
                issues.append({"column": col, "issue": "data_type_mismatch", "description": issue})
                if "appears numeric" in issue:
                    recommendations.append(CleaningRecommendation(
                        issue="String column with numeric data",
                        column=col,
                        recommendation=f"Convert column '{col}' to numeric type",
                        method="cast_to_numeric",
                        priority="high"
                    ))
                elif "appears datetime" in issue:
                    recommendations.append(CleaningRecommendation(
                        issue="String column with datetime data",
                        column=col,
                        recommendation=f"Convert column '{col}' to datetime type",
                        method="cast_to_datetime",
                        priority="high"
                    ))

        elif check_name == "Data Consistency":
            consistency_issues = details.get("issues", [])
            for issue in consistency_issues:
                col = issue.split(":")[0].strip()
                issues.append({"column": col, "issue": "consistency", "description": issue})
                if "Case/whitespace" in issue:
                    recommendations.append(CleaningRecommendation(
                        issue="Case/whitespace inconsistency",
                        column=col,
                        recommendation=f"Standardize text: lowercase and trim whitespace for '{col}'",
                        method="standardize_text",
                        priority="medium"
                    ))
                elif "whitespace" in issue:
                    recommendations.append(CleaningRecommendation(
                        issue="Leading/trailing whitespace",
                        column=col,
                        recommendation=f"Trim whitespace from '{col}' values",
                        method="trim_whitespace",
                        priority="medium"
                    ))

        elif check_name == "Unique Value Ratio":
            unique_issues = details.get("issues", [])
            for issue in unique_issues:
                col = issue.split(":")[0].strip()
                issues.append({"column": col, "issue": "unique_ratio", "description": issue})
                if "All values unique" in issue:
                    recommendations.append(CleaningRecommendation(
                        issue="All values unique (possible ID column)",
                        column=col,
                        recommendation=f"Consider setting '{col}' as index/ID column, exclude from analysis",
                        method="set_as_index",
                        priority="low"
                    ))
                elif "Very low cardinality" in issue:
                    recommendations.append(CleaningRecommendation(
                        issue="Very low cardinality",
                        column=col,
                        recommendation=f"Column '{col}' has very few unique values - verify if useful for analysis",
                        method="review_column",
                        priority="low"
                    ))

        return {"issues": issues, "recommendations": recommendations}


cleaning_service = CleaningRecommendationService()
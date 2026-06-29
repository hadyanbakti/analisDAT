import polars as pl
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from app.services.data_profiling import data_profiling_service
from app.services.statistical_analysis import statistical_service


@dataclass
class Insight:
    id: str
    title: str
    description: str
    insight_type: str
    score: float
    supporting_data: Dict[str, Any]
    visualization: Optional[Dict[str, Any]] = None


class InsightEngine:
    def __init__(self):
        self.profiling = data_profiling_service

    def discover_insights(self, df: pl.DataFrame, profiling_result: Dict, stats_result: Dict, quality_result: Dict) -> List[Dict[str, Any]]:
        insights = []

        insights.extend(self._detect_trends(df, profiling_result, stats_result))
        insights.extend(self._detect_correlations(df, stats_result))
        insights.extend(self._detect_outliers(df, profiling_result))
        insights.extend(self._detect_dominance(df, profiling_result))
        insights.extend(self._detect_distributions(df, profiling_result, stats_result))
        insights.extend(self._detect_quality_issues(df, quality_result))

        return [asdict(i) for i in insights]

    def _detect_trends(self, df: pl.DataFrame, profiling: Dict, stats: Dict) -> List[Insight]:
        insights = []
        trends = stats.get("trends", [])

        for trend in trends[:5]:
            if trend.get("r_squared", 0) > 0.3:
                col = trend.get("column", "")
                direction = trend.get("direction", "stable")
                slope = trend.get("slope", 0)

                if direction == "increasing":
                    title = f"Upward Trend in {col}"
                    desc = f"Column '{col}' shows a statistically significant upward trend (R²={trend['r_squared']:.2f})."
                elif direction == "decreasing":
                    title = f"Downward Trend in {col}"
                    desc = f"Column '{col}' shows a statistically significant downward trend (R²={trend['r_squared']:.2f})."
                else:
                    continue

                insights.append(Insight(
                    id=f"trend_{col}",
                    title=title,
                    description=desc,
                    insight_type="trend",
                    score=min(90, 50 + trend["r_squared"] * 40),
                    supporting_data={"column": col, "slope": slope, "r_squared": trend["r_squared"], "p_value": trend.get("p_value")},
                ))

        return insights

    def _detect_correlations(self, df: pl.DataFrame, stats: Dict) -> List[Insight]:
        insights = []
        correlations = stats.get("correlations", [])

        for corr in correlations[:10]:
            strength = corr.get("strength", "")
            if strength in ["strong", "very_strong"]:
                col_x = corr.get("column_x", "")
                col_y = corr.get("column_y", "")
                r = corr.get("correlation", 0)
                direction = "positive" if r > 0 else "negative"

                insights.append(Insight(
                    id=f"corr_{col_x}_{col_y}",
                    title=f"Strong {direction.title()} Correlation: {col_x} & {col_y}",
                    description=f"Columns '{col_x}' and '{col_y}' have a {strength} {direction} correlation (r={r:.3f}).",
                    insight_type="correlation",
                    score=min(95, 60 + abs(r) * 30),
                    supporting_data={"column_x": col_x, "column_y": col_y, "correlation": r, "method": corr.get("method")},
                ))

        return insights

    def _detect_outliers(self, df: pl.DataFrame, profiling: Dict) -> List[Insight]:
        insights = []
        numeric_cols = profiling.get("numeric_features", [])

        for col in numeric_cols[:10]:
            series = df[col].drop_nulls()
            if len(series) < 10:
                continue

            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            outlier_count = int(((series < lower) | (series > upper)).sum())
            if outlier_count > 0:
                total = len(series)
                pct = (outlier_count / total) * 100

                insights.append(Insight(
                    id=f"outlier_{col}",
                    title=f"Outliers Detected in {col}",
                    description=f"Found {outlier_count} outliers ({pct:.1f}%) in column '{col}' using IQR method.",
                    insight_type="outlier",
                    score=min(85, 50 + pct * 3),
                    supporting_data={"column": col, "outlier_count": outlier_count, "outlier_percentage": round(pct, 2), "bounds": {"lower": lower, "upper": upper}},
                ))

        return insights

    def _detect_dominance(self, df: pl.DataFrame, profiling: Dict) -> List[Insight]:
        insights = []
        categorical_cols = profiling.get("categorical_features", [])

        for col in categorical_cols[:5]:
            value_counts = df[col].drop_nulls().value_counts()
            if len(value_counts) < 2:
                continue

            total = value_counts["count"].sum()
            top_row = value_counts.to_dicts()[0]
            top_value = top_row[col]
            top_count = top_row["count"]
            top_pct = (top_count / total) * 100

            if top_pct > 50:
                insights.append(Insight(
                    id=f"dominance_{col}",
                    title=f"Dominance in {col}",
                    description=f"'{top_value}' dominates '{col}' with {top_pct:.1f}% of all values.",
                    insight_type="dominance",
                    score=min(90, 55 + top_pct * 0.35),
                    supporting_data={"column": col, "top_value": str(top_value), "top_percentage": round(top_pct, 2), "value_counts": value_counts.head(5).to_dicts()},
                ))

        return insights

    def _detect_distributions(self, df: pl.DataFrame, profiling: Dict, stats: Dict) -> List[Insight]:
        insights = []
        distributions = stats.get("distributions", [])

        for dist in distributions[:5]:
            if not dist.get("is_normal", True):
                skew = dist.get("parameters", {}).get("skewness", 0)
                if abs(skew) > 1:
                    direction = "right" if skew > 0 else "left"
                    insights.append(Insight(
                        id=f"dist_{dist.get('column', '')}",
                        title=f"Skewed Distribution: {dist.get('column', '')}",
                        description=f"Column '{dist.get('column', '')}' has a {direction}-skewed distribution (skewness={skew:.2f}).",
                        insight_type="distribution",
                        score=70,
                        supporting_data={"column": dist.get("column"), "skewness": skew, "kurtosis": dist.get("parameters", {}).get("kurtosis")},
                    ))

        return insights

    def _detect_quality_issues(self, df: pl.DataFrame, quality_result: Dict) -> List[Insight]:
        insights = []
        score = quality_result.get("overall_score", 100)

        if score < 80:
            insights.append(Insight(
                id="quality_overall",
                title="Data Quality Below Standard",
                description=f"Overall data quality score is {score}/100 ({quality_result.get('quality_category', 'Unknown')}). Consider cleaning the data.",
                insight_type="quality",
                score=max(10, 100 - score),
                supporting_data={"quality_score": score, "category": quality_result.get("quality_category")},
            ))

        return insights

    def rank_insights(self, insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        ranked = sorted(insights, key=lambda x: x.get("score", 0), reverse=True)
        top_insight = ranked[0] if ranked else None
        return {
            "insights": ranked,
            "top_insight": top_insight,
        }


insight_service = InsightEngine()
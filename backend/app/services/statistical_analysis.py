import polars as pl
import numpy as np
from scipy import stats
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from app.services.data_profiling import data_profiling_service


@dataclass
class CorrelationResult:
    column_x: str
    column_y: str
    correlation: float
    p_value: float
    method: str
    strength: str


@dataclass
class TrendResult:
    column: str
    trend_type: str
    slope: float
    r_squared: float
    p_value: float
    direction: str


@dataclass
class DistributionResult:
    column: str
    distribution_type: str
    parameters: Dict[str, float]
    goodness_of_fit: float
    is_normal: bool


class StatisticalAnalysisService:
    def __init__(self):
        self.profiling = data_profiling_service

    def analyze(self, df: pl.DataFrame) -> Dict[str, Any]:
        numeric_cols = [col for col in df.columns if self.profiling.detect_column_category(df[col]) == "numeric"]
        datetime_cols = [col for col in df.columns if self.profiling.detect_column_category(df[col]) == "datetime"]

        result = {"correlations": [], "trends": [], "distributions": [], "summary_stats": {}}
        errors = []

        try:
            result["correlations"] = self._analyze_correlations(df, numeric_cols)
        except Exception as e:
            errors.append(f"correlations: {e}")
        try:
            result["trends"] = self._analyze_trends(df, numeric_cols, datetime_cols)
        except Exception as e:
            errors.append(f"trends: {e}")
        try:
            result["distributions"] = self._analyze_distributions(df, numeric_cols)
        except Exception as e:
            errors.append(f"distributions: {e}")
        try:
            result["summary_stats"] = self._get_summary_stats(df, numeric_cols)
        except Exception as e:
            errors.append(f"summary_stats: {e}")

        if errors:
            result["_errors"] = errors
        return result

    def _analyze_correlations(self, df: pl.DataFrame, numeric_cols: List[str]) -> List[Dict[str, Any]]:
        correlations = []
        if len(numeric_cols) < 2:
            return correlations

        for i, col_x in enumerate(numeric_cols):
            for col_y in numeric_cols[i+1:]:
                try:
                    clean_x = df[col_x].drop_nulls()
                    clean_y = df[col_y].drop_nulls()

                    min_len = min(len(clean_x), len(clean_y))
                    if min_len < 3:
                        continue

                    aligned_x = clean_x[:min_len].to_numpy().astype(float)
                    aligned_y = clean_y[:min_len].to_numpy().astype(float)

                    pearson_r, pearson_p = stats.pearsonr(aligned_x, aligned_y)
                    spearman_r, spearman_p = stats.spearmanr(aligned_x, aligned_y)

                    strength = self._get_correlation_strength(abs(pearson_r))

                    correlations.append(CorrelationResult(
                        column_x=col_x,
                        column_y=col_y,
                        correlation=round(float(pearson_r), 4),
                        p_value=round(float(pearson_p), 6),
                        method="pearson",
                        strength=strength,
                    ).__dict__)

                    if abs(spearman_r - pearson_r) > 0.1:
                        correlations.append(CorrelationResult(
                            column_x=col_x,
                            column_y=col_y,
                            correlation=round(float(spearman_r), 4),
                            p_value=round(float(spearman_p), 6),
                            method="spearman",
                            strength=self._get_correlation_strength(abs(spearman_r)),
                        ).__dict__)
                except:
                    pass

        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return correlations[:20]

    def _get_correlation_strength(self, r: float) -> str:
        if r >= 0.7:
            return "very_strong"
        elif r >= 0.5:
            return "strong"
        elif r >= 0.3:
            return "moderate"
        elif r >= 0.1:
            return "weak"
        return "negligible"

    def _analyze_trends(self, df: pl.DataFrame, numeric_cols: List[str], datetime_cols: List[str]) -> List[Dict[str, Any]]:
        trends = []

        if not datetime_cols:
            return trends

        time_col = datetime_cols[0]
        time_series = df[time_col].drop_nulls()
        if len(time_series) < 3:
            return trends

        time_numeric = np.arange(len(time_series))

        for num_col in numeric_cols:
            clean_series = df[num_col].drop_nulls()
            if len(clean_series) < 3:
                continue

            min_len = min(len(time_numeric), len(clean_series))
            if min_len < 3:
                continue

            x = time_numeric[:min_len]
            y = clean_series[:min_len].to_numpy().astype(float)

            try:
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                r_squared = r_value ** 2

                trend_type = "linear"
                direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"

                if r_squared < 0.1:
                    trend_type = "no_clear_trend"
                    direction = "stable"

                trends.append(TrendResult(
                    column=num_col,
                    trend_type=trend_type,
                    slope=round(slope, 6),
                    r_squared=round(r_squared, 4),
                    p_value=round(p_value, 6),
                    direction=direction,
                ).__dict__)
            except:
                pass

        trends.sort(key=lambda x: x.get("r_squared", 0), reverse=True)
        return trends

    def _analyze_distributions(self, df: pl.DataFrame, numeric_cols: List[str]) -> List[Dict[str, Any]]:
        distributions = []

        for col in numeric_cols:
            clean_series = df[col].drop_nulls()
            if len(clean_series) < 10:
                continue

            data = clean_series.to_numpy().astype(float)

            try:
                if len(data) <= 5000:
                    shapiro_stat, shapiro_p = stats.shapiro(data)
                else:
                    shapiro_stat, shapiro_p = None, None
                is_normal = bool(shapiro_p > 0.05) if shapiro_p is not None else False

                dist_type = "normal" if is_normal else "non_normal"
                if not is_normal:
                    skew = stats.skew(data)
                    kurt = stats.kurtosis(data)
                    if abs(skew) > 1:
                        dist_type = "skewed"
                    elif abs(kurt) > 3:
                        dist_type = "heavy_tailed"

                distributions.append(DistributionResult(
                    column=col,
                    distribution_type=dist_type,
                    parameters={
                        "mean": float(np.mean(data)),
                        "std": float(np.std(data)),
                        "skewness": float(stats.skew(data)),
                        "kurtosis": float(stats.kurtosis(data)),
                    },
                    goodness_of_fit=round(shapiro_stat, 4) if shapiro_stat else 0,
                    is_normal=is_normal,
                ).__dict__)
            except:
                pass

        return distributions

    def _get_summary_stats(self, df: pl.DataFrame, numeric_cols: List[str]) -> Dict[str, Any]:
        summary = {}
        for col in numeric_cols:
            clean_series = df[col].drop_nulls()
            if len(clean_series) == 0:
                continue
            data = clean_series.to_numpy().astype(float)
            try:
                q1 = float(np.percentile(data, 25))
                q3 = float(np.percentile(data, 75))
            except Exception:
                q1 = float(np.min(data))
                q3 = float(np.max(data))
            summary[col] = {
                "count": len(data),
                "mean": float(np.mean(data)),
                "median": float(np.median(data)),
                "std": float(np.std(data)),
                "min": float(np.min(data)),
                "max": float(np.max(data)),
                "q1": q1,
                "q3": q3,
                "skewness": float(stats.skew(data)) if len(data) > 2 else 0.0,
                "kurtosis": float(stats.kurtosis(data)) if len(data) > 2 else 0.0,
            }
        return summary


statistical_service = StatisticalAnalysisService()
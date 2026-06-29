import polars as pl
import json
from typing import Dict, Any, List, Optional
from app.services.llm_layer import llm_service
from app.services.data_profiling import data_profiling_service


class LLMVisualizationService:
    async def generate_visualizations(self, df: pl.DataFrame, profiling_result: Dict[str, Any], stats_result: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_viz_prompt(df, profiling_result, stats_result)
        result = await llm_service._call_llm(prompt)
        if not result or "visualizations" not in result:
            return {"visualizations": [], "summary": "Could not generate visualizations. LLM unavailable."}

        viz_list = result.get("visualizations", [])
        enriched = []
        for v in viz_list:
            chart_data = self._build_chart_data(df, v)
            enriched.append({
                "chart_type": v.get("chart_type", "scatter"),
                "title": v.get("title", ""),
                "x_axis": v.get("x", ""),
                "y_axis": v.get("y", ""),
                "color": v.get("color"),
                "data": chart_data,
                "layout": v.get("layout", {}),
                "reason": v.get("reason", ""),
            })

        return {
            "visualizations": enriched,
            "summary": result.get("summary", f"Generated {len(enriched)} LLM-recommended visualizations"),
        }

    def _build_chart_data(self, df: pl.DataFrame, viz_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        chart_type = viz_config.get("chart_type", "scatter")
        x_col = viz_config.get("x")
        y_col = viz_config.get("y")
        color_col = viz_config.get("color")
        try:
            if chart_type == "histogram" and x_col:
                clean = df[x_col].drop_nulls().to_list()
                return [{"x": clean, "type": "histogram", "opacity": 0.7, "name": x_col}]
            elif chart_type == "bar" and x_col:
                counts = df[x_col].drop_nulls().value_counts().sort("count", descending=True).head(20)
                return [{
                    "x": counts[x_col].cast(pl.Utf8).to_list(),
                    "y": counts["count"].to_list(),
                    "type": "bar",
                    "marker": {"color": "#6366f1"},
                }]
            elif chart_type in ("scatter", "line") and x_col and y_col:
                temp = df.select([x_col, y_col]).drop_nulls()
                if len(temp) == 0:
                    return []
                result = [{
                    "x": temp[x_col].to_list(),
                    "y": temp[y_col].to_list(),
                    "type": "scatter",
                    "mode": "lines" if chart_type == "line" else "markers",
                    "marker": {"size": 5, "opacity": 0.6, "color": "#6366f1"},
                }]
                if color_col and color_col in df.columns:
                    temp_color = df.select([x_col, y_col, color_col]).drop_nulls()
                    for val in temp_color[color_col].unique().to_list()[:10]:
                        subset = temp_color.filter(pl.col(color_col) == val)
                        result.append({
                            "x": subset[x_col].to_list(),
                            "y": subset[y_col].to_list(),
                            "type": "scatter",
                            "mode": "markers",
                            "name": str(val),
                            "marker": {"size": 5, "opacity": 0.6},
                        })
                    result = result[1:]
                return result
            elif chart_type == "box" and y_col:
                clean = df[y_col].drop_nulls().to_list()
                if x_col and x_col in df.columns:
                    result = []
                    for val in df[x_col].unique().to_list()[:10]:
                        subset = df.filter(pl.col(x_col) == val)[y_col].drop_nulls().to_list()
                        if subset:
                            result.append({"y": subset, "name": str(val), "type": "box"})
                    return result
                return [{"y": clean, "type": "box", "name": y_col}]
            elif chart_type == "heatmap":
                corr_cols = [c for c in [x_col, y_col] if c and c in df.columns]
                if len(corr_cols) < 2:
                    numeric_cols = [c for c in df.columns if str(df[c].dtype) in ["Int64", "Float64", "Int32", "Float32"]][:8]
                    if len(numeric_cols) < 2:
                        return []
                    corr_cols = numeric_cols
                temp = df.select(corr_cols).drop_nulls()
                if len(temp) < 2:
                    return []
                corr_matrix = temp.to_pandas().corr().values.tolist()
                return [{"z": corr_matrix, "x": corr_cols, "y": corr_cols, "type": "heatmap", "colorscale": "RdBu_r", "zmin": -1, "zmax": 1}]
            elif chart_type == "pie" and x_col:
                counts = df[x_col].drop_nulls().value_counts().sort("count", descending=True).head(10)
                return [{"labels": counts[x_col].cast(pl.Utf8).to_list(), "values": counts["count"].to_list(), "type": "pie"}]
        except Exception as e:
            return [{"error": str(e)}]
        return []

    def _build_viz_prompt(self, df: pl.DataFrame, profiling_result: Dict[str, Any], stats_result: Dict[str, Any]) -> str:
        numeric_cols = profiling_result.get("numeric_features", [])
        categorical_cols = profiling_result.get("categorical_features", [])
        datetime_cols = profiling_result.get("datetime_features", [])
        column_descriptions = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            nulls = series.null_count()
            uniques = series.n_unique()
            sample = series.drop_nulls().head(3).to_list()
            column_descriptions.append(f"- {col} ({dtype}): {uniques} unique, {nulls} nulls, sample={sample}")

        stats_text = ""
        summary_stats = stats_result.get("summary_stats", {})
        if summary_stats:
            for col, s in list(summary_stats.items())[:5]:
                stats_text += f"\n  {col}: mean={s.get('mean', 'N/A')}, min={s.get('min', 'N/A')}, max={s.get('max', 'N/A')}, skew={s.get('skewness', 'N/A')}"

        correlations = stats_result.get("correlations", [])
        corr_text = ""
        for c in correlations[:5]:
            corr_text += f"\n  {c.get('column_x')} vs {c.get('column_y')}: r={c.get('correlation', 'N/A')} ({c.get('strength', 'N/A')})"

        return f"""You are a data visualization expert. Recommend the most insightful visualizations for this dataset.

Dataset: {len(df)} rows, {len(df.columns)} columns
Numeric: {numeric_cols[:8]}
Categorical: {categorical_cols[:5]}
Datetime: {datetime_cols[:3]}

Column Details:
{chr(10).join(column_descriptions)}

Summary Statistics:{stats_text}

Top Correlations:{corr_text}

Generate a JSON response with:
1. "summary": Brief explanation of your visualization strategy
2. "visualizations": Array of 4-8 visualization objects, each with:
   - "chart_type": "histogram", "bar", "scatter", "line", "box", "heatmap", or "pie"
   - "title": Clear, descriptive title
   - "x": X-axis column name
   - "y": Y-axis column name (omit for histogram, pie)
   - "color": (optional) Color/group column
   - "reason": Why this visualization is useful for this dataset
   - "layout": (optional) Layout config like {{"xaxis": {{"tickangle": -45}}}}

Choose chart types that best reveal patterns in THIS specific data. Prioritize:
- Histograms for numeric distributions
- Bar charts for categorical value counts  
- Scatter plots for numeric relationships
- Line charts for time series
- Box plots for outlier detection
- Heatmap for correlation overview
- Pie charts only for 2-5 category breakdowns

Respond in JSON format only. No markdown."""

llm_viz_service = LLMVisualizationService()

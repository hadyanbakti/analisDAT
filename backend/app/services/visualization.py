import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional
from app.services.data_profiling import data_profiling_service
from app.services.statistical_analysis import statistical_service


class VisualizationService:
    def __init__(self):
        self.profiling = data_profiling_service

    def generate_dashboard(self, df: pl.DataFrame, profiling_result: Dict, stats_result: Dict) -> Dict[str, Any]:
        visualizations = []
        numeric_cols = profiling_result.get("numeric_features", [])
        categorical_cols = profiling_result.get("categorical_features", [])
        datetime_cols = profiling_result.get("datetime_features", [])

        if datetime_cols and numeric_cols:
            time_chart = self._generate_time_series(df, datetime_cols[0], numeric_cols[:3])
            if time_chart:
                visualizations.append(time_chart)

        if numeric_cols:
            dist_chart = self._generate_distribution(df, numeric_cols[:4])
            if dist_chart:
                visualizations.append(dist_chart)

        if len(numeric_cols) >= 2:
            corr_chart = self._generate_correlation_heatmap(df, numeric_cols[:6])
            if corr_chart:
                visualizations.append(corr_chart)

        for cat_col in categorical_cols[:3]:
            bar_chart = self._generate_bar_chart(df, cat_col)
            if bar_chart:
                visualizations.append(bar_chart)

        if len(numeric_cols) >= 2:
            scatter_chart = self._generate_scatter(df, numeric_cols[0], numeric_cols[1])
            if scatter_chart:
                visualizations.append(scatter_chart)

        if numeric_cols:
            box_chart = self._generate_box_plot(df, numeric_cols[:4])
            if box_chart:
                visualizations.append(box_chart)

        summary = self._generate_summary(visualizations, profiling_result)

        return {
            "visualizations": visualizations,
            "summary": summary,
        }

    def _generate_time_series(self, df: pl.DataFrame, time_col: str, value_cols: List[str]) -> Optional[Dict[str, Any]]:
        try:
            temp_df = df.select([time_col] + value_cols).drop_nulls().sort(time_col)
            if len(temp_df) < 2:
                return None

            data = []
            for col in value_cols:
                data.append({
                    "x": temp_df[time_col].cast(pl.Utf8).to_list(),
                    "y": temp_df[col].to_list(),
                    "name": col,
                    "type": "scatter",
                    "mode": "lines",
                })

            return {
                "chart_type": "line",
                "title": f"Time Series Analysis",
                "x_axis": time_col,
                "y_axis": "Value",
                "data": data,
                "layout": {
                    "xaxis": {"title": time_col},
                    "yaxis": {"title": "Value"},
                    "showlegend": len(value_cols) > 1,
                },
            }
        except:
            return None

    def _generate_distribution(self, df: pl.DataFrame, numeric_cols: List[str]) -> Optional[Dict[str, Any]]:
        try:
            data = []
            for col in numeric_cols:
                clean = df[col].drop_nulls().to_list()
                if len(clean) > 0:
                    data.append({
                        "x": clean,
                        "name": col,
                        "type": "histogram",
                        "opacity": 0.6,
                    })

            if not data:
                return None

            return {
                "chart_type": "histogram",
                "title": "Distribution of Numeric Columns",
                "x_axis": "Value",
                "y_axis": "Frequency",
                "data": data,
                "layout": {
                    "barmode": "overlay",
                    "showlegend": len(numeric_cols) > 1,
                },
            }
        except:
            return None

    def _generate_correlation_heatmap(self, df: pl.DataFrame, numeric_cols: List[str]) -> Optional[Dict[str, Any]]:
        try:
            temp_df = df.select(numeric_cols).drop_nulls()
            if len(temp_df) < 2 or len(numeric_cols) < 2:
                return None

            corr_matrix = temp_df.to_pandas().corr().values.tolist()

            data = [{
                "z": corr_matrix,
                "x": numeric_cols,
                "y": numeric_cols,
                "type": "heatmap",
                "colorscale": "RdBu_r",
                "zmin": -1,
                "zmax": 1,
            }]

            return {
                "chart_type": "heatmap",
                "title": "Correlation Matrix",
                "x_axis": "",
                "y_axis": "",
                "data": data,
                "layout": {
                    "xaxis": {"tickangle": -45},
                    "yaxis": {},
                },
            }
        except:
            return None

    def _generate_bar_chart(self, df: pl.DataFrame, cat_col: str) -> Optional[Dict[str, Any]]:
        try:
            counts = df[cat_col].drop_nulls().value_counts().sort("count", descending=True).head(15)
            if len(counts) == 0:
                return None

            data = [{
                "x": counts[cat_col].cast(pl.Utf8).to_list(),
                "y": counts["count"].to_list(),
                "type": "bar",
                "marker": {"color": "#6366f1"},
            }]

            return {
                "chart_type": "bar",
                "title": f"Top Categories: {cat_col}",
                "x_axis": cat_col,
                "y_axis": "Count",
                "data": data,
                "layout": {
                    "xaxis": {"tickangle": -45},
                    "yaxis": {"title": "Count"},
                },
            }
        except:
            return None

    def _generate_scatter(self, df: pl.DataFrame, x_col: str, y_col: str) -> Optional[Dict[str, Any]]:
        try:
            temp_df = df.select([x_col, y_col]).drop_nulls()
            if len(temp_df) < 2:
                return None

            data = [{
                "x": temp_df[x_col].to_list(),
                "y": temp_df[y_col].to_list(),
                "type": "scatter",
                "mode": "markers",
                "marker": {"size": 6, "color": "#6366f1", "opacity": 0.6},
            }]

            return {
                "chart_type": "scatter",
                "title": f"{x_col} vs {y_col}",
                "x_axis": x_col,
                "y_axis": y_col,
                "data": data,
                "layout": {
                    "xaxis": {"title": x_col},
                    "yaxis": {"title": y_col},
                },
            }
        except:
            return None

    def _generate_box_plot(self, df: pl.DataFrame, numeric_cols: List[str]) -> Optional[Dict[str, Any]]:
        try:
            data = []
            for col in numeric_cols:
                clean = df[col].drop_nulls().to_list()
                if len(clean) > 0:
                    data.append({
                        "y": clean,
                        "name": col,
                        "type": "box",
                    })

            if not data:
                return None

            return {
                "chart_type": "box",
                "title": "Box Plot Distribution",
                "x_axis": "Column",
                "y_axis": "Value",
                "data": data,
                "layout": {
                    "showlegend": len(numeric_cols) > 1,
                },
            }
        except:
            return None

    def _generate_summary(self, visualizations: List[Dict], profiling: Dict) -> str:
        viz_count = len(visualizations)
        row_count = profiling.get("row_count", 0)
        col_count = profiling.get("column_count", 0)
        return f"Dashboard generated with {viz_count} visualizations for dataset with {row_count:,} rows and {col_count} columns"


visualization_service = VisualizationService()
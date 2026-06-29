import polars as pl
import json
import re
from typing import Dict, Any, List, Optional
from app.services.llm_layer import llm_service
from app.services.data_ingestion import data_ingestion_service
from app.core.config import settings


class LLMCleaningService:
    async def generate_plan(self, df: pl.DataFrame, quality_result: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_cleaning_prompt(df, quality_result)
        result = await llm_service._call_llm(prompt)
        if not result or "steps" not in result:
            return {"steps": [], "summary": "Could not generate cleaning plan. LLM unavailable."}
        result["summary"] = result.get("summary", f"Generated {len(result['steps'])} cleaning steps")
        return result

    async def preview_cleaning(self, df: pl.DataFrame, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        sample_df = df.head(100)
        results = []
        for step in steps:
            if step.get("approved", True):
                try:
                    code = step.get("code", "")
                    column = step.get("column")
                    before_preview = sample_df[column].to_list() if column else None
                    cleaned_sample = self._execute_code(sample_df.clone(), code)
                    after_preview = cleaned_sample[column].to_list() if column else None
                    results.append({
                        "step_id": step.get("id", 0),
                        "description": step.get("description", ""),
                        "before": {"sample": before_preview[:5] if before_preview else None, "null_count": sample_df[column].null_count() if column else 0},
                        "after": {"sample": after_preview[:5] if after_preview else None, "null_count": cleaned_sample[column].null_count() if column else 0},
                        "success": True,
                    })
                except Exception as e:
                    results.append({
                        "step_id": step.get("id", 0),
                        "description": step.get("description", ""),
                        "error": str(e),
                        "success": False,
                    })
        return {"preview_results": results}

    async def apply_cleaning(self, df: pl.DataFrame, steps: List[Dict[str, Any]], original_filename: str) -> Dict[str, Any]:
        cleaned_df = df.clone()
        applied_steps = []
        for step in steps:
            if step.get("approved", True):
                try:
                    code = step.get("code", "")
                    cleaned_df = self._execute_code(cleaned_df, code)
                    applied_steps.append({
                        "id": step.get("id", 0),
                        "description": step.get("description", ""),
                        "method": step.get("method", ""),
                        "column": step.get("column"),
                        "reason": step.get("reason", ""),
                        "success": True,
                    })
                except Exception as e:
                    applied_steps.append({
                        "id": step.get("id", 0),
                        "description": step.get("description", ""),
                        "error": str(e),
                        "success": False,
                    })

        import os
        base, _ = os.path.splitext(original_filename)
        clean_name = f"cleaned_{base}.csv"
        file_path = data_ingestion_service.save_upload(cleaned_df.write_csv().encode(), clean_name)
        return {
            "cleaned_filename": clean_name,
            "cleaned_file_path": file_path,
            "original_rows": len(df),
            "cleaned_rows": len(cleaned_df),
            "applied_steps": applied_steps,
        }

    def _execute_code(self, df: pl.DataFrame, code: str) -> pl.DataFrame:
        local_vars = {"df": df, "pl": pl}
        safe_code = code.strip()
        if safe_code.startswith("```python"):
            safe_code = safe_code.split("```python")[1].split("```")[0]
        elif safe_code.startswith("```"):
            safe_code = safe_code.split("```")[1].split("```")[0]
        if "df =" in safe_code:
            lines = safe_code.split("\n")
            cleaned_lines = [l for l in lines if l.strip().startswith("df =") or not l.strip().startswith("df =")]
            safe_code = "\n".join(cleaned_lines)
            safe_code = safe_code.replace("df = df", "df = df")
        exec(safe_code, {"pl": pl, "pd": None}, local_vars)
        return local_vars["df"]

    def _build_cleaning_prompt(self, df: pl.DataFrame, quality_result: Dict[str, Any]) -> str:
        columns_info = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            nulls = series.null_count()
            uniques = series.n_unique()
            sample = series.drop_nulls().head(3).to_list()
            columns_info.append(f"- {col} (dtype={dtype}, nulls={nulls}, unique={uniques}, sample={sample})")

        issues_text = ""
        for check in quality_result.get("checks", []):
            issues_text += f"\nCheck: {check.get('check_name', '')} (score={check.get('score', 0)}/{check.get('max_score', 0)}, passed={check.get('passed', False)})"
            details = check.get("details", {})
            if isinstance(details, dict):
                for k, v in details.items():
                    issues_text += f"\n  {k}: {v}"

        return f"""You are a data cleaning expert. Analyze this dataset and generate cleaning steps.

Dataset: {len(df)} rows, {len(df.columns)} columns

Columns:
{chr(10).join(columns_info)}

Quality Issues Detected:
{issues_text}

Sample data (first 3 rows):
{json.dumps(df.head(3).to_dicts(), indent=2, default=str)}

Generate a JSON response with:
1. "summary": Brief summary of cleaning approach
2. "steps": Array of cleaning step objects, each with:
   - "id": unique integer
   - "description": Human-readable description
   - "method": Cleaning method (e.g., "median_imputation", "drop_duplicates", "cast_type", "trim_whitespace", "cap_outliers")
   - "column": Column name or null for row-level operations
   - "reason": Why this step is needed
   - "code": Polars code that operates on a variable named 'df'. Example: 'df = df.with_columns(pl.col("age").fill_null(pl.median("age")))'
   - "priority": "high", "medium", or "low"

IMPORTANT: The code must be valid Python using the 'pl' (polars) module and a variable named 'df'. Use only these operations: with_columns, fill_null, drop_nulls, unique, cast, str.strip, str.to_lowercase, filter.

Respond in JSON format only. No markdown."""
llm_cleaning_service = LLMCleaningService()

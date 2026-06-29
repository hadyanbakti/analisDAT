import polars as pl
import json
import os
from typing import Dict, Any, List, Optional
from app.core.config import settings


class LLMLayer:
    def __init__(self):
        self.gemini_client = None
        self.openai_client = None
        self._init_clients()

    def _init_clients(self):
        try:
            if settings.GEMINI_API_KEY:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        except Exception as e:
            print(f"Gemini init failed: {e}")

        try:
            if settings.OPENAI_API_KEY:
                from openai import OpenAI
                kwargs = {"api_key": settings.OPENAI_API_KEY}
                if settings.OPENAI_BASE_URL:
                    kwargs["base_url"] = settings.OPENAI_BASE_URL
                self.openai_client = OpenAI(**kwargs)
        except Exception as e:
            print(f"OpenAI init failed: {e}")

    async def generate_storytelling_report(self, df: pl.DataFrame, insights: Dict, quality_result: Dict, profiling_result: Dict) -> Dict[str, Any]:
        context = self._build_context(df, insights, quality_result, profiling_result)
        prompt = self._build_storytelling_prompt(context)

        result = await self._call_llm(prompt)

        return {
            "narrative": result.get("narrative", self._generate_fallback_story(context)),
            "key_findings": result.get("key_findings", []),
            "recommendations": result.get("recommendations", []),
            "reasoning": result.get("reasoning"),
        }

    async def chat_with_data(self, user_message: str, df: pl.DataFrame, context: Dict) -> Dict[str, Any]:
        prompt = self._build_chat_prompt(user_message, df, context)
        result = await self._call_llm(prompt)
        if result:
            resp = {
                "response": result.get("response") or result.get("narrative") or "I cannot process your request at this time.",
                "visualization_data": result.get("visualization_data"),
                "supporting_stats": result.get("supporting_stats"),
            }
            if result.get("reasoning"):
                resp["reasoning"] = result["reasoning"]
            return resp
        return self._chat_fallback(user_message, df, context)
        return self._chat_fallback(user_message, df, context)

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        if settings.LLM_PROVIDER == "gemini" and self.gemini_client:
            return await self._call_gemini(prompt)
        elif self.openai_client:
            return await self._call_openai(prompt)
        return {}

    def _chat_fallback(self, user_message: str, df: pl.DataFrame, context: Dict) -> Dict[str, Any]:
        n_rows = context.get("rows", 0)
        n_cols = context.get("columns", 0)
        q_score = context.get("quality_score", 0)

        preview_rows = df.head(3).to_dicts() if len(df) > 0 else []
        stats = []
        for col in df.columns[:8]:
            s = df[col].drop_nulls()
            if len(s) > 0 and "float" in str(s.dtype).lower() or "int" in str(s.dtype).lower():
                stats.append(f"- {col}: mean={s.mean():.2f}, min={s.min()}, max={s.max()}")
            elif len(s) > 0:
                uniq = s.n_unique()
                stats.append(f"- {col}: {uniq} unique values")

        summary = f"Dataset: {n_rows} rows × {n_cols} columns, Quality Score: {q_score}/100\n\n"
        if stats:
            summary += "Column Stats:\n" + "\n".join(stats[:6]) + "\n\n"
        if preview_rows:
            import json
            summary += f"Sample data:\n{json.dumps(preview_rows, indent=2, default=str)[:500]}\n\n"
        summary += f'Your question: "{user_message}"\n\n'
        summary += "💡 Tip: Set GEMINI_API_KEY or OPENAI_API_KEY in .env for full AI-powered responses."

        return {
            "response": summary,
            "visualization_data": None,
            "supporting_stats": {"rows": n_rows, "columns": n_cols, "quality_score": q_score},
        }

    async def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text
            return self._parse_llm_response(text)
        except Exception as e:
            err = str(e)
            print(f"Gemini error: {err[:200]}")
            if "RESOURCE_EXHAUSTED" in err:
                return {"response": "⚠️ Gemini API credits depleted. Add billing at https://ai.studio or use a new API key."}
            return {}

    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.3,
            )
            message = response.choices[0].message
            reasoning = getattr(message, "reasoning_content", None)
            text = message.content or reasoning or ""
            result = self._parse_llm_response(text)
            if reasoning:
                result["reasoning"] = reasoning
            return result
        except Exception as e:
            print(f"OpenAI error: {e}")
            return {}

    def _parse_llm_response(self, text: str) -> Dict[str, Any]:
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
                return json.loads(json_str)
            elif "{":
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
        except:
            pass
        return {"narrative": text, "key_findings": [], "recommendations": []}

    def _build_context(self, df: pl.DataFrame, insights: Dict, quality_result: Dict, profiling_result: Dict) -> Dict[str, Any]:
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "quality_score": quality_result.get("overall_score", 0),
            "quality_category": quality_result.get("quality_category", "Unknown"),
            "insights_count": len(insights.get("insights", [])),
            "top_insight": insights.get("top_insight"),
            "numeric_columns": profiling_result.get("numeric_features", []),
            "categorical_columns": profiling_result.get("categorical_features", []),
            "datetime_columns": profiling_result.get("datetime_features", []),
            "duplicate_rows": profiling_result.get("duplicate_rows", 0),
        }

    def _build_storytelling_prompt(self, context: Dict) -> str:
        return f"""You are a professional data analyst assistant. Generate a comprehensive storytelling report for this dataset.

Dataset Summary:
- Rows: {context['rows']:,}
- Columns: {context['columns']}
- Quality Score: {context['quality_score']}/100 ({context['quality_category']})
- Numeric columns: {', '.join(context['numeric_columns'][:5])}
- Categorical columns: {', '.join(context['categorical_columns'][:5])}
- Duplicate rows: {context['duplicate_rows']}

Top Insight: {json.dumps(context.get('top_insight', {}), indent=2)}

Generate a JSON response with:
1. "narrative": A professional paragraph summarizing key findings and their business implications
2. "key_findings": Array of 3-5 most important findings
3. "recommendations": Array of 3-5 actionable recommendations

Respond in JSON format only."""

    def _build_chat_prompt(self, user_message: str, df: pl.DataFrame, context: Dict) -> str:
        preview = df.head(5).to_dicts() if len(df) > 0 else []
        stats_summary = ""
        for col in df.columns[:10]:
            series = df[col].drop_nulls()
            if len(series) > 0 and str(series.dtype) in ["Int64", "Float64", "Int32", "Float32"]:
                stats_summary += f"\n- {col}: mean={series.mean():.2f}, min={series.min()}, max={series.max()}"

        return f"""You are a data analyst assistant. Answer the user's question about the dataset.

Dataset Info:
- {context.get('rows', 0):,} rows, {context.get('columns', 0)} columns
- Quality: {context.get('quality_score', 0)}/100

Column Statistics:
{stats_summary}

Sample Data (first 5 rows):
{json.dumps(preview, indent=2, default=str)}

User Question: {user_message}

Respond in JSON format with:
1. "response": Your clear, concise answer
2. "visualization_data": (optional) Visualization config if helpful
3. "supporting_stats": (optional) Key stats that support your answer

JSON only, no other text."""

    def _generate_fallback_story(self, context: Dict) -> str:
        return f"""This dataset contains {context['rows']:,} rows and {context['columns']} columns.
The data quality score is {context['quality_score']}/100 ({context['quality_category']}).
The dataset includes {len(context.get('numeric_columns', []))} numeric and {len(context.get('categorical_columns', []))} categorical columns.
{context['duplicate_rows']} duplicate rows were detected.

For detailed insights and recommendations, please configure an LLM provider (Gemini or OpenAI) in your environment variables."""


llm_service = LLMLayer()
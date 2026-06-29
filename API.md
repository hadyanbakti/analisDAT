# analisDAT API Documentation

**Base URL:** `http://localhost:8000/api/v1`
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

## Health

### GET /health

Check if the server is running.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Datasets

### POST /api/v1/datasets/upload

Upload a CSV or XLSX file. Processing (profiling, quality, cleaning, statistics, visualizations, insights, storytelling) runs in the background.

**Request:** `multipart/form-data`
| Field | Type | Description |
|---|---|---|
| file | File | CSV or XLSX file (max 50MB) |

**Response `201` — `DatasetResponse`:**
```json
{
  "id": 1,
  "filename": "abc123_data.csv",
  "original_filename": "data.csv",
  "file_size": 2048576,
  "file_type": "csv",
  "rows": 15000,
  "columns": 12,
  "quality_score": null,
  "quality_category": null,
  "created_at": "2026-06-29T10:00:00",
  "updated_at": null
}
```

**Errors:** `400` — Unsupported file type or file too large.

---

### GET /api/v1/datasets

List all uploaded datasets.

**Query Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| skip | int | 0 | Number of records to skip |
| limit | int | 20 | Max records to return |

**Response `200` — `List[DatasetResponse]`:**
```json
[
  {
    "id": 1,
    "filename": "abc123_data.csv",
    "original_filename": "data.csv",
    "file_size": 2048576,
    "file_type": "csv",
    "rows": 15000,
    "columns": 12,
    "quality_score": 78.5,
    "quality_category": "Good",
    "created_at": "2026-06-29T10:00:00",
    "updated_at": "2026-06-29T10:02:00"
  }
]
```

---

### GET /api/v1/datasets/{dataset_id}

Get full dataset details including quality, cleaning, insights, visualizations, and storytelling report (populated after background processing completes).

**Response `200` — `DatasetDetailResponse`:**
```json
{
  "id": 1,
  "filename": "abc123_data.csv",
  "original_filename": "data.csv",
  "file_size": 2048576,
  "file_type": "csv",
  "rows": 15000,
  "columns": 12,
  "quality_score": 78.5,
  "quality_category": "Good",
  "created_at": "2026-06-29T10:00:00",
  "updated_at": "2026-06-29T10:02:00",
  "columns_info": [
    {
      "name": "age",
      "dtype": "Int64",
      "nullable": true,
      "unique_count": 75,
      "missing_count": 23,
      "missing_percentage": 0.15,
      "sample_values": [25, 34, 41]
    }
  ],
  "data_types": { "age": "numeric", "name": "string" },
  "missing_values": { "age": 23, "name": 0 },
  "duplicates_count": 0,
  "quality_details": { "overall_score": 78.5, "quality_category": "Good", "checks": [], "summary": {} },
  "cleaning_recommendations": { "detected_issues": [], "recommendations": [] },
  "insights": { "insights": [], "top_insight": {} },
  "visualizations": { "visualizations": [], "summary": "" },
  "storytelling_report": "Report text..."
}
```

**Errors:** `404` — Dataset not found.

---

### GET /api/v1/datasets/{dataset_id}/preview

Get a preview of the dataset (first N rows).

**Query Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| rows | int | 10 | Number of rows to preview |

**Response `200` — `DatasetPreview`:**
```json
{
  "rows": 15000,
  "columns": 12,
  "columns_info": [
    { "name": "age", "dtype": "Int64", "nullable": true, "unique_count": 75, "missing_count": 23, "missing_percentage": 0.15, "sample_values": [25, 34, 41] }
  ],
  "sample_data": [
    { "age": 25, "name": "Alice" },
    { "age": 34, "name": "Bob" }
  ],
  "file_metadata": {
    "filename": "data.csv",
    "size": 2048576,
    "type": "csv"
  }
}
```

---

### DELETE /api/v1/datasets/{dataset_id}

Delete a dataset and its file.

**Response `200`:**
```json
{
  "message": "Dataset deleted successfully"
}
```

---

## Analysis

All analysis endpoints require `{dataset_id}`. They read the file and compute results in real-time (not from cached DB values).

### GET /api/v1/analysis/{dataset_id}/profile

Get dataset profiling: row/column counts, detected column types, and data type map.

**Response `200` — `DataProfiling`:**
```json
{
  "rows": 15000,
  "columns": 12,
  "numeric_columns": ["age", "salary", "score"],
  "categorical_columns": ["name", "department", "city"],
  "datetime_columns": ["join_date"],
  "data_types": { "age": "numeric", "name": "string" }
}
```

---

### GET /api/v1/analysis/{dataset_id}/quality

Get data quality score with individual checks.

**Response `200` — `DataQualityResult`:**
```json
{
  "overall_score": 78.5,
  "quality_category": "Good",
  "checks": [
    { "check_name": "missing_values", "score": 85.0, "details": { "missing_cells": 45 }, "passed": true }
  ],
  "summary": { "total_cells": 180000, "missing_cells": 45, "duplicate_rows": 0 }
}
```

Quality categories:
| Score Range | Category |
|---|---|
| >= 90 | Excellent |
| >= 75 | Good |
| >= 50 | Fair |
| < 50 | Poor |

---

### GET /api/v1/analysis/{dataset_id}/cleaning-recommendations

Get cleaning recommendations based on quality issues.

**Response `200` — `DataCleaningResult`:**
```json
{
  "detected_issues": [
    { "column": "age", "issue": "missing_values", "severity": "medium", "count": 23 }
  ],
  "recommendations": [
    {
      "issue": "missing_values",
      "column": "age",
      "recommendation": "Impute missing values with median (34.0)",
      "method": "median_imputation",
      "priority": "medium"
    }
  ]
}
```

---

### GET /api/v1/analysis/{dataset_id}/statistics

Get statistical analysis: summary stats, correlations, trends, distributions, outlier detection.

**Response `200` — `StatisticalAnalysisResult`:**
```json
{
  "summary_stats": {
    "age": {
      "count": 14977,
      "mean": 37.2,
      "median": 34.0,
      "std": 12.5,
      "min": 18,
      "max": 85,
      "q1": 28.0,
      "q3": 45.0,
      "skewness": 0.45,
      "kurtosis": -0.23
    }
  },
  "correlations": [
    {
      "column_x": "age",
      "column_y": "salary",
      "correlation": 0.62,
      "p_value": 0.0001,
      "method": "pearson",
      "strength": "strong"
    }
  ],
  "trends": [
    {
      "column": "sales",
      "trend_type": "linear",
      "slope": 2.34,
      "r_squared": 0.89,
      "p_value": 0.001,
      "direction": "increasing"
    }
  ],
  "distributions": [
    {
      "column": "age",
      "distribution_type": "normal",
      "is_normal": true,
      "shapiro_p_value": 0.12,
      "skewness": 0.45,
      "kurtosis": -0.23
    }
  ],
  "outliers": {
    "age": { "count": 12, "method": "iqr", "bounds": { "lower": 2.5, "upper": 70.5 } }
  }
}
```

---

### GET /api/v1/analysis/{dataset_id}/visualizations

Get a Plotly dashboard with visualizations (histograms, box plots, correlation heatmaps, scatter plots, time series).

**Response `200` — `DashboardResponse`:**
```json
{
  "visualizations": [
    {
      "chart_type": "histogram",
      "title": "Distribution of Age",
      "x_axis": "age",
      "y_axis": "count",
      "color": null,
      "data": [
        { "age": 20, "count": 150 },
        { "age": 30, "count": 320 }
      ],
      "layout": {}
    }
  ],
  "summary": "Generated 8 visualizations including distributions, correlations, and relationships."
}
```

---

### GET /api/v1/analysis/{dataset_id}/insights

Get ranked insights: trend detection, correlation insights, outlier insights, dominance insights.

**Response `200` — `InsightRanking`:**
```json
{
  "insights": [
    {
      "id": "trend_1",
      "title": "Sales showing strong upward trend",
      "description": "Sales column shows a strong increasing trend (R²=0.89, slope=2.34)",
      "insight_type": "trend",
      "score": 89.0,
      "supporting_data": { "column": "sales", "slope": 2.34, "r_squared": 0.89 },
      "visualization": null
    }
  ],
  "top_insight": {
    "id": "trend_1",
    "title": "Sales showing strong upward trend",
    "description": "Sales column shows a strong increasing trend (R²=0.89, slope=2.34)",
    "insight_type": "trend",
    "score": 89.0,
    "supporting_data": {},
    "visualization": null
  }
}
```

---

## Chat

### POST /api/v1/chat/{dataset_id}/chat

Send a message to the AI assistant about the dataset. Creates a new session if `session_id` is omitted.

**Request Body — `ChatMessageRequest`:**
```json
{
  "message": "What are the main trends in this data?",
  "session_id": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| message | string | yes | User's question about the dataset |
| session_id | int or null | no | Existing session ID (null = new session) |

**Response `200` — `ChatMessageResponse`:**
```json
{
  "id": 42,
  "role": "assistant",
  "content": "Based on the data, here are the main trends...",
  "visualization_data": { "chart_type": "line", "data": [] },
  "supporting_stats": { "correlation": 0.85 },
  "reasoning": "The assistant used statistical analysis to determine...",
  "created_at": "2026-06-29T10:05:00"
}
```

---

### GET /api/v1/chat/{dataset_id}/sessions

List all chat sessions for a dataset.

**Response `200` — `List[ChatSessionResponse]`:**
```json
[
  {
    "id": 1,
    "dataset_id": 1,
    "session_name": "Chat - data.csv",
    "created_at": "2026-06-29T10:05:00",
    "messages": [
      {
        "id": 41,
        "role": "user",
        "content": "What are the main trends?",
        "visualization_data": null,
        "supporting_stats": null,
        "reasoning": null,
        "created_at": "2026-06-29T10:05:00"
      }
    ]
  }
]
```

---

### GET /api/v1/chat/sessions/{session_id}

Get a specific chat session with all messages.

**Response `200` — `ChatSessionResponse`** (same schema as above).

**Errors:** `404` — Session not found.

---

## Error Handling

All errors return the standard FastAPI format:

```json
{
  "detail": "Dataset not found"
}
```

Global 500 errors include `error` field when `DEBUG=true` in the environment.

---

## Schemas

### DatasetResponse

| Field | Type | Description |
|---|---|---|
| id | int | Dataset ID |
| filename | string | Stored filename |
| original_filename | string | Original uploaded filename |
| file_size | int | File size in bytes |
| file_type | string | `csv` or `xlsx` |
| rows | int | Number of rows |
| columns | int | Number of columns |
| quality_score | float or null | Quality score (0-100) |
| quality_category | string or null | `Excellent`, `Good`, `Fair`, or `Poor` |
| created_at | datetime | Upload timestamp |
| updated_at | datetime or null | Last update timestamp |

### DatasetDetailResponse (extends DatasetResponse)

| Field | Type | Description |
|---|---|---|
| columns_info | list | Per-column metadata |
| data_types | dict | Column -> type mapping |
| missing_values | dict | Column -> missing count |
| duplicates_count | int | Number of duplicate rows |
| quality_details | DataQualityResult | Full quality report |
| cleaning_recommendations | DataCleaningResult | Cleaning suggestions |
| insights | InsightRanking | Ranked insights |
| visualizations | DashboardResponse | Plotly charts |
| storytelling_report | string | AI-generated report |

### ChatMessageRequest

| Field | Type | Description |
|---|---|---|
| message | string | User's message |
| session_id | int or null | Session to continue, or null for new session |

### ChatMessageResponse

| Field | Type | Description |
|---|---|---|
| id | int | Message ID |
| role | string | `user` or `assistant` |
| content | string | Message content |
| visualization_data | dict or null | Plotly chart data (assistant only) |
| supporting_stats | dict or null | Statistics supporting the response |
| reasoning | string or null | LLM reasoning chain |
| created_at | datetime | Timestamp |

### ChatSessionResponse

| Field | Type | Description |
|---|---|---|
| id | int | Session ID |
| dataset_id | int | Associated dataset |
| session_name | string or null | Human-readable name |
| created_at | datetime | Creation timestamp |
| messages | list[ChatMessageResponse] | All messages in session |

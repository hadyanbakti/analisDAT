from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    nullable: bool
    unique_count: int
    missing_count: int
    missing_percentage: float
    sample_values: List[Any] = []


class DatasetPreview(BaseModel):
    rows: int
    columns: int
    columns_info: List[ColumnInfo]
    sample_data: List[Dict[str, Any]]
    file_metadata: Dict[str, Any]


class DataProfiling(BaseModel):
    rows: int
    columns: int
    numeric_columns: List[str]
    categorical_columns: List[str]
    datetime_columns: List[str]
    data_types: Dict[str, str]


class QualityCheck(BaseModel):
    check_name: str
    score: float
    details: Dict[str, Any]
    passed: bool


class DataQualityResult(BaseModel):
    overall_score: float
    quality_category: str
    checks: List[QualityCheck]
    summary: Dict[str, Any]


class CleaningRecommendation(BaseModel):
    issue: str
    column: Optional[str] = None
    recommendation: str
    method: str
    priority: str


class DataCleaningResult(BaseModel):
    detected_issues: List[Dict[str, Any]]
    recommendations: List[CleaningRecommendation]


class VisualizationConfig(BaseModel):
    chart_type: str
    title: str
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    color: Optional[str] = None
    data: List[Dict[str, Any]]
    layout: Dict[str, Any] = {}


class DashboardResponse(BaseModel):
    visualizations: List[VisualizationConfig]
    summary: str


class CleaningStep(BaseModel):
    id: int
    description: str
    method: str
    column: Optional[str] = None
    reason: str
    code: str
    priority: str = "medium"
    approved: bool = True


class LLMCleaningPlan(BaseModel):
    summary: str
    steps: List[CleaningStep]


class CleaningPreviewResult(BaseModel):
    step_id: int
    description: str
    before: Dict[str, Any]
    after: Dict[str, Any]
    error: Optional[str] = None
    success: bool = True


class CleaningPreviewResponse(BaseModel):
    preview_results: List[CleaningPreviewResult]


class ApplyCleaningResponse(BaseModel):
    cleaned_filename: str
    cleaned_file_path: str
    original_rows: int
    cleaned_rows: int
    applied_steps: List[Dict[str, Any]]


class Insight(BaseModel):
    id: str
    title: str
    description: str
    insight_type: str
    score: float
    supporting_data: Dict[str, Any]
    visualization: Optional[VisualizationConfig] = None


class InsightRanking(BaseModel):
    insights: List[Insight]
    top_insight: Optional[Insight] = None


class StorytellingReport(BaseModel):
    narrative: str
    key_findings: List[str]
    recommendations: List[str]


class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    visualization_data: Optional[Dict[str, Any]] = None
    supporting_stats: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    dataset_id: int
    session_name: Optional[str] = None
    created_at: datetime
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True


class DatasetResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    rows: int
    columns: int
    quality_score: Optional[float] = None
    quality_category: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DatasetDetailResponse(DatasetResponse):
    columns_info: Optional[List[ColumnInfo]] = None
    data_types: Optional[Dict[str, str]] = None
    missing_values: Optional[Dict[str, int]] = None
    duplicates_count: int = 0
    quality_details: Optional[DataQualityResult] = None
    cleaning_recommendations: Optional[DataCleaningResult] = None
    insights: Optional[InsightRanking] = None
    visualizations: Optional[DashboardResponse] = None
    storytelling_report: Optional[StorytellingReport] = None
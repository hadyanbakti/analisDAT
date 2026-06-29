from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import polars as pl
import os
from app.core.config import settings
from app.services.data_ingestion import data_ingestion_service
from app.services.data_profiling import data_profiling_service
from app.services.data_quality import data_quality_service
from app.db.database import get_db
from app.models.dataset import Dataset
from app.schemas.dataset import (
    DatasetResponse,
    DatasetDetailResponse,
    DatasetPreview,
)
from app.services.cleaning_recommendations import cleaning_service
from app.services.statistical_analysis import statistical_service
from app.services.visualization import visualization_service
from app.services.insight_engine import insight_service
from app.services.llm_layer import llm_service

router = APIRouter()


@router.post("/upload", response_model=DatasetResponse)
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    file_type = data_ingestion_service.detect_file_type(file.filename)
    if file_type == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported file type. Use CSV or XLSX")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 50MB")

    file_path = data_ingestion_service.save_upload(content, file.filename)
    file_info = data_ingestion_service.get_file_info(file_path)

    df = data_ingestion_service.read_file(file_path, file_type)

    dataset = Dataset(
        filename=os.path.basename(file_path),
        original_filename=file.filename,
        file_size=file_info["size"],
        file_type=file_type,
        rows=len(df),
        columns=len(df.columns),
        columns_info=data_ingestion_service.get_column_info(df),
        data_types=data_ingestion_service.get_data_types(df),
        missing_values=data_ingestion_service.get_missing_values(df),
    )

    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    background_tasks.add_task(process_dataset_background, dataset.id, file_path, dataset.file_type)

    return dataset


@router.get("", response_model=List[DatasetResponse])
async def list_datasets(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).offset(skip).limit(limit).order_by(Dataset.created_at.desc()))
    return result.scalars().all()


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
async def preview_dataset(dataset_id: int, rows: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    return DatasetPreview(
        rows=len(df),
        columns=len(df.columns),
        columns_info=data_ingestion_service.get_column_info(df),
        sample_data=data_ingestion_service.get_preview(df, rows),
        file_metadata={"filename": dataset.original_filename, "size": dataset.file_size, "type": dataset.file_type},
    )


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(dataset)
    await db.commit()
    return {"message": "Dataset deleted successfully"}


async def process_dataset_background(dataset_id: int, file_path: str, file_type: str):
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            df = data_ingestion_service.read_file(file_path, file_type)
            profiling_result = data_profiling_service.profile_dataset(df)
            quality_result = data_quality_service.calculate_quality_score(df)
            cleaning_result = cleaning_service.generate_recommendations(df, quality_result)
            stats_result = statistical_service.analyze(df)
            viz_result = visualization_service.generate_dashboard(df, profiling_result, stats_result)
            insights_result = insight_service.discover_insights(df, profiling_result, stats_result, quality_result)
            ranked_insights = insight_service.rank_insights(insights_result)
            story_result = await llm_service.generate_storytelling_report(df, ranked_insights, quality_result, profiling_result)

            result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
            dataset = result.scalar_one_or_none()
            if dataset:
                dataset.quality_score = quality_result["overall_score"]
                dataset.quality_details = quality_result
                dataset.cleaning_recommendations = cleaning_result
                dataset.insights = ranked_insights
                dataset.visualizations = viz_result
                dataset.storytelling_report = story_result.get("narrative", "")
                dataset.duplicates_count = profiling_result.get("duplicate_rows", 0)
                await db.commit()
        except Exception as e:
            print(f"Background processing error: {e}")
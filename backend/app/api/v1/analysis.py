from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
from app.core.config import settings
from app.db.database import get_db
from app.models.dataset import Dataset
from app.services.data_ingestion import data_ingestion_service
from app.services.data_profiling import data_profiling_service
from app.services.data_quality import data_quality_service
from app.services.cleaning_recommendations import cleaning_service
from app.services.statistical_analysis import statistical_service
from app.services.visualization import visualization_service
from app.services.insight_engine import insight_service

router = APIRouter()


@router.get("/{dataset_id}/profile")
async def get_profiling(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    return data_profiling_service.profile_dataset(df)


@router.get("/{dataset_id}/quality")
async def get_quality(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    return data_quality_service.calculate_quality_score(df)


@router.get("/{dataset_id}/cleaning-recommendations")
async def get_cleaning(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    quality_result = data_quality_service.calculate_quality_score(df)
    return cleaning_service.generate_recommendations(df, quality_result)


@router.get("/{dataset_id}/statistics")
async def get_statistics(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    return statistical_service.analyze(df)


@router.get("/{dataset_id}/visualizations")
async def get_visualizations(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    profiling_result = data_profiling_service.profile_dataset(df)
    stats_result = statistical_service.analyze(df)
    return visualization_service.generate_dashboard(df, profiling_result, stats_result)


@router.get("/{dataset_id}/insights")
async def get_insights(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)
    profiling_result = data_profiling_service.profile_dataset(df)
    quality_result = data_quality_service.calculate_quality_score(df)
    stats_result = statistical_service.analyze(df)
    insights = insight_service.discover_insights(df, profiling_result, stats_result, quality_result)
    return insight_service.rank_insights(insights)
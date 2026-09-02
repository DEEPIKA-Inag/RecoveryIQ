"""
routers/model_quality.py
GET /model-quality -- runs the calibration check (same held-out split as
training) and returns it as JSON so the frontend can display it directly,
instead of only being available as a terminal script.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from ..ml.calibration_check import run_calibration_check

router = APIRouter(tags=["model_quality"])


class CalibrationBin(BaseModel):
    range_label: str
    sample_count: int
    mean_predicted: float
    actual_recovery_rate: float
    gap: float


class ModelQualityResult(BaseModel):
    bins: List[CalibrationBin]
    weighted_calibration_error: float


@router.get("/model-quality", response_model=ModelQualityResult)
def model_quality():
    rows, weighted_error = run_calibration_check()
    bins = [
        CalibrationBin(
            range_label=label,
            sample_count=int(n),
            mean_predicted=round(float(mean_pred), 4),
            actual_recovery_rate=round(float(actual), 4),
            gap=round(float(gap), 4),
        )
        for label, n, mean_pred, actual, gap in rows
    ]
    return ModelQualityResult(bins=bins, weighted_calibration_error=round(float(weighted_error), 4))
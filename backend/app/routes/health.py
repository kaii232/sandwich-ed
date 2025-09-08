from fastapi import APIRouter
from app.models.schemas import WellbeingCheckRequest, WellbeingCheckResult, WellbeingLastResponse
from app.services.wellbeing import record_check, last_check

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "healthy", "message": "AI Course System is running"}

@router.post("/wellbeing/check", response_model=WellbeingCheckResult)
def wellbeing_check(req: WellbeingCheckRequest):
    return record_check(req.model_dump())

@router.get("/wellbeing/last", response_model=WellbeingLastResponse)
def wellbeing_last():
    last = last_check()
    return {"last": last}  # may be None

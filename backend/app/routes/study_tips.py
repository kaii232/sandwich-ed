from typing import List
from fastapi import APIRouter, HTTPException
from tutor import AITutor                     # <-- same import pattern as lesson_chat
from app.models.schemas import StudyTipsRequest

router = APIRouter()
tutor = AITutor()                             # reuse a single instance

@router.post("/study_tips", response_model=List[str])
def study_tips(p: StudyTipsRequest) -> List[str]:
    try:
        tips = tutor.generate_study_tips(
            p.week_info,
            p.course_context,
            p.student_performance,
        )
        # make sure we always return up to 5 strings
        tips = [str(t).strip() for t in (tips or []) if str(t).strip()]
        return tips[:5]
    except Exception as e:
        # surface a clean 500 instead of a raw traceback
        raise HTTPException(status_code=500, detail=f"study_tips_failed: {e}")
from pydantic import BaseModel
from typing import Optional

class ChatbotRequest(BaseModel):
    state: dict
    user_input: Optional[str] = None

class ChatbotResponse(BaseModel):
    state: dict
    bot: str
    summary: Optional[dict] = None
    syllabus: Optional[str] = None
    course_ready: Optional[bool] = None
    error: Optional[str] = None

class CourseRequest(BaseModel):
    syllabus_text: str
    course_context: dict

class WeekContentRequest(BaseModel):
    week_number: int
    course_data: dict

class LessonContentRequest(BaseModel):
    lesson_info: dict
    course_context: dict

class QuizRequest(BaseModel):
    week_info: dict
    course_context: dict

class QuizSubmissionRequest(BaseModel):
    quiz_session: dict
    user_answers: dict

class AdaptiveWeekRequest(BaseModel):
    week_info: dict
    course_context: dict

class TutoringRequest(BaseModel):
    question: str
    week_info: dict
    course_context: dict

class ChatPayload(BaseModel):
    question: str
    history: list | None = None
    course_context: dict | None = None
    week_context: dict | None = None

class WellbeingCheckRequest(BaseModel):
    mood: int                      # 1–5 (1=very low, 5=great)
    phq2: list[int] | None = None  # two items, each 0–3
    gad2: list[int] | None = None  # two items, each 0–3
    free_text: str | None = None

class WellbeingCheckResult(BaseModel):
    timestamp: str
    mood: int
    phq2_total: int
    gad2_total: int
    risk: str                      # "low" | "watch" | "elevated" | "urgent"
    message: str
    show_resources: bool = False

class WellbeingLastResponse(BaseModel):
    last: WellbeingCheckResult | None

from typing import Optional, Dict, List
from pydantic import BaseModel

class StudyTipsRequest(BaseModel):
    week_info: Dict
    course_context: Dict
    student_performance: Optional[Dict] = None

class StudyTipsRequest(BaseModel):
    week_info: Dict
    course_context: Dict
    student_performance: Optional[Dict] = None
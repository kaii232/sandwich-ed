from fastapi import APIRouter, HTTPException
from datetime import datetime
from tutor import AITutor, create_quiz_session, submit_quiz_answers, adjust_next_week_content, get_tutoring_help, get_personalized_study_tips
from syllabus_generator import SyllabusGenerator, initialize_course_from_syllabus
from app.models.schemas import (
    CourseRequest, WeekContentRequest, LessonContentRequest,
    QuizRequest, QuizSubmissionRequest, TutoringRequest
)
from app.services.progressive import (
    load_course_data, save_course_data, generate_next_week_content
)

router = APIRouter()
tutor = AITutor()

@router.post("/initialize_course")
async def initialize_course(req: CourseRequest):
    try:
        course_data = initialize_course_from_syllabus(req.syllabus_text, req.course_context)
        return {"success": True, "course_data": course_data, "message": "Course initialized successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/get_week_content")
async def get_week_content(req: WeekContentRequest):
    try:
        course_data = req.course_data
        weeks = course_data.get("weeks", [])
        progressive = load_course_data()
        p_weeks = progressive.get("weeks", [])
        all_weeks = weeks + [w for w in p_weeks if not any(sw.get('week_number') == w.get('week_number') for sw in weeks)]
        week_content = next((w for w in all_weeks if w.get("week_number")==req.week_number), None)
        if not week_content:
            if req.week_number > 1:
                raise HTTPException(status_code=404, detail=f"Week {req.week_number} is not available yet. Complete previous weeks to unlock it.")
            raise HTTPException(status_code=404, detail="Week not found")
        navigation = course_data.get("navigation", {})
        navigation.update({"total_weeks": len(all_weeks), "available_weeks": len(all_weeks)})
        return {"success": True, "week_content": week_content, "navigation": navigation, "is_progressive": bool(week_content.get("created_at"))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_quiz")
async def create_quiz(req: QuizRequest):
    try:
        week_number = req.week_info.get("week_number")
        progressive = load_course_data()
        pre = progressive.get("pre_generated_quizzes", {})
        if str(week_number) in pre:
            quiz_session = {
                "quiz": pre[str(week_number)],
                "week_info": req.week_info,
                "course_context": req.course_context,
                "start_time": datetime.now().isoformat(),
                "time_remaining": 30 * 60,
                "status": "active",
            }
            return {"success": True, "quiz_session": quiz_session, "pre_generated": True}
        quiz_session = create_quiz_session(req.week_info, req.course_context)
        return {"success": True, "quiz_session": quiz_session, "pre_generated": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit_quiz")
async def submit_quiz(req: QuizSubmissionRequest):
    try:
        completed = submit_quiz_answers(req.quiz_session, req.user_answers)
        results = completed.get("results", {})
        quiz = req.quiz_session.get("quiz", {})
        cur_week = quiz.get("week_number", 1)
        pct = results.get("percentage", 0)

        template_next = {"week_number": cur_week+1, "title": f"Week {cur_week+1}: Advanced Topics", "topics": []}
        adapted = adjust_next_week_content(template_next, req.quiz_session.get("course_context", {}), completed)

        if pct >= 70:
            try:
                course_data = await generate_next_week_content(cur_week, req.quiz_session.get("course_context", {}), results)
                for w in course_data.get("weeks", []):
                    if w.get("week_number") == cur_week+1:
                        adapted = w; break
            except Exception:
                pass

        adaptation_type = "accelerated" if pct >= 90 else "reinforced" if pct < 70 else "balanced"
        return {
            "success": True,
            "quiz_results": results,
            "adapted_next_week": adapted,
            "adaptation_summary": {
                "current_week": cur_week,
                "performance": pct,
                "adaptation_type": adaptation_type,
                "next_week_difficulty": adapted.get("difficulty_level", "standard"),
                "next_quiz_difficulty": adapted.get("quiz_difficulty", "same")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/get_tutoring_help")
async def get_tutoring_help_endpoint(req: TutoringRequest):
    try:
        return {"success": True, "tutoring_response": get_tutoring_help(req.question, req.week_info, req.course_context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/get_study_tips")
async def get_study_tips(req: TutoringRequest):
    try:
        return {"success": True, "study_tips": get_personalized_study_tips(req.week_info, req.course_context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/get_lesson_content")
async def get_lesson_content(req: LessonContentRequest):
    try:
        generator = SyllabusGenerator()
        return {"success": True, "lesson_content": generator.generate_lesson_content(req.lesson_info, req.course_context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

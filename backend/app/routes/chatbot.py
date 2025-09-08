from fastapi import APIRouter, HTTPException
from tutor import AITutor
from app.models.schemas import ChatbotRequest, ChatbotResponse, ChatPayload
from app.services.chatbot import chatbot_step

router = APIRouter()
tutor = AITutor()  # reuse a single instance

@router.post("/chatbot_step", response_model=ChatbotResponse)
async def chatbot_step_api(req: ChatbotRequest):
    try:
        state, resp = chatbot_step(req.state, req.user_input)
        return ChatbotResponse(
            state=state,
            bot=resp.get("bot",""),
            summary=resp.get("summary"),
            syllabus=resp.get("syllabus"),
            course_ready=resp.get("course_ready"),
            error=resp.get("error"),
        )
    except Exception as e:
        return ChatbotResponse(state=req.state, bot="I hit an error—please try again.", error=str(e))

@router.post("/lesson_chat")
def lesson_chat(p: ChatPayload):
    answer = tutor.chat_about_lesson(
        p.course_context or {}, p.week_context or {}, p.question, p.history or []
    )
    return {"answer": answer}

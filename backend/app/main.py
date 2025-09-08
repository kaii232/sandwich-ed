import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.chatbot import router as chatbot_router
from app.routes.course import router as course_router
from app.routes.health import router as health_router
from app.routes.study_tips import router as study_tips_router
from app.core.config import ALLOW_ORIGINS

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="AI Course Planning & Learning System", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chatbot_router)
app.include_router(course_router)
app.include_router(health_router)
app.include_router(study_tips_router)
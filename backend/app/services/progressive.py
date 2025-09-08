import os, json, logging
from datetime import datetime
from typing import Dict, List
from app.core.bedrock import ask_claude
from app.core.config import COURSE_DATA_FILE
from tutor import AITutor

log = logging.getLogger(__name__)

def load_course_data() -> dict:
    try:
        if os.path.exists(COURSE_DATA_FILE):
            with open(COURSE_DATA_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Error loading course data: {e}")
    return {"weeks": [], "navigation": {"current_week": 1, "total_weeks": 1}}

def save_course_data(course_data: dict):
    try:
        with open(COURSE_DATA_FILE, "w") as f:
            json.dump(course_data, f, indent=2)
    except Exception as e:
        log.error(f"Error saving course data: {e}")

def identify_weak_areas(quiz_results: dict) -> list:
    weak = []
    if not quiz_results.get("feedback"): return weak
    for fb in quiz_results["feedback"]:
        if not fb.get("is_correct", True):
            qt = fb.get("question_text", "").lower()
            if "calculate" in qt or "math" in qt: weak.append("Mathematical calculations")
            elif "theory" in qt or "concept" in qt: weak.append("Theoretical understanding")
            elif "apply" in qt or "practical" in qt: weak.append("Practical application")
            elif "problem" in qt: weak.append("Problem solving")
    return list(set(weak))

# ----- adaptive generation (same logic as your api.py) -----
async def generate_next_week_content(completed_week_number: int, course_context: dict, quiz_results: dict) -> dict:
    next_week_number = completed_week_number + 1
    course_topic = course_context.get("topic", "General Studies")
    course_data = load_course_data()

    if any(w.get("week_number") == next_week_number for w in course_data.get("weeks", [])):
        return course_data

    performance = quiz_results.get("percentage", 75)
    weak_areas = identify_weak_areas(quiz_results)
    next_week_data = await generate_adaptive_week_content(
        week_number=next_week_number,
        course_topic=course_topic,
        performance_data=quiz_results,
        weak_areas=weak_areas,
        course_context=course_context,
    )
    course_data.setdefault("weeks", []).append(next_week_data)
    course_data["navigation"] = {
        "current_week": next_week_number,
        "total_weeks": len(course_data["weeks"]),
        "course_status": "in_progress",
    }

    # pre-generate quiz
    try:
        tutor = AITutor()
        quiz = tutor.create_quiz(next_week_data, course_context)
        course_data.setdefault("pre_generated_quizzes", {})[str(next_week_number)] = quiz
    except Exception as e:
        log.error(f"Failed to pre-generate quiz: {e}")

    save_course_data(course_data)
    return course_data

async def generate_adaptive_week_content(week_number: int, course_topic: str, performance_data: dict, weak_areas: list, course_context: dict) -> dict:
    pct = performance_data.get("percentage", 75)
    if pct >= 85:
        difficulty, focus = "advanced", "expansion"
    elif pct >= 70:
        difficulty, focus = "standard", "progression"
    else:
        difficulty, focus = "supportive", "reinforcement"

    prompt = f"""Generate Week {week_number} for {course_topic}.
Prev quiz: {pct}% | Weak areas: {', '.join(weak_areas) or 'None'} | Focus: {focus} | Difficulty: {difficulty}
Sections: Week Title, Overview, 4 Lesson Topics (with objectives & key concepts), 3-4 Additional Resources.
Adaptive notes accordingly.
Format clearly."""
    try:
        response = ask_claude([{"role":"user","content":prompt}], temperature=0.3, max_tokens=2000)
        return parse_week_content_response(response, week_number, difficulty, course_context)
    except Exception as e:
        log.error(f"Error generating week: {e}")
        return create_fallback_week_data(week_number, course_topic, difficulty)

def parse_week_content_response(response: str, week_number: int, difficulty_level: str, course_context: dict) -> dict:
    title = response.split("\n")[0].replace("**","").replace("#","").strip() or f"Week {week_number}: Advanced Concepts"
    week = {
        "week_number": week_number,
        "title": title,
        "difficulty_level": difficulty_level,
        "overview": "This week builds on previous concepts with new challenging material.",
        "lesson_topics": [],
        "additional_resources": [],
        "created_at": datetime.now().isoformat(),
        "status": "ready"
    }
    # simple parse for up to 4 lessons
    lessons = [l for l in response.split("\n") if "lesson" in l.lower()]
    for i, line in enumerate(lessons[:4], start=1):
        week["lesson_topics"].append({
            "title": line.replace("**","").replace("-","").strip() or f"Lesson {i}",
            "type": "lesson",
            "content": f"Detailed content for lesson {i} covering key concepts.",
            "learning_objectives": [
                f"Understand key concept {i}",
                "Apply learned principles in practical scenarios",
                "Analyze complex problems using new methods"
            ]
        })
    while len(week["lesson_topics"]) < 4:
        n = len(week["lesson_topics"]) + 1
        week["lesson_topics"].append({
            "title": f"Advanced Topic {n}",
            "type": "lesson",
            "content": f"Comprehensive coverage of advanced topic {n}.",
            "learning_objectives": [
                f"Master advanced concept {n}",
                "Apply knowledge to real-world scenarios",
                "Develop critical thinking skills"
            ]
        })
    return week

def create_fallback_week_data(week_number: int, course_topic: str, difficulty_level: str) -> dict:
    return {
        "week_number": week_number,
        "title": f"Week {week_number}: {course_topic} - Advanced Concepts",
        "difficulty_level": difficulty_level,
        "overview": f"This week covers advanced {course_topic} concepts.",
        "lesson_topics": [
            {"title": f"{course_topic} Fundamentals Review", "type":"lesson","content":"Review fundamentals.",
             "learning_objectives":["Review key principles","Strengthen understanding","Prepare for advanced topics"]},
            {"title": f"Advanced {course_topic} Concepts", "type":"lesson","content":"Complex topics & applications.",
             "learning_objectives":["Learn advanced concepts","Understand applications","Develop problem-solving skills"]},
            {"title": "Practical Applications", "type":"lesson","content":"Real-world case studies.",
             "learning_objectives":["Apply knowledge","Analyze scenarios","Develop implementation skills"]},
            {"title": "Assessment Guide", "type":"lesson","content":"Assessment prep.",
             "learning_objectives":["Prepare for assessment","Self-evaluate","Identify areas for improvement"]}
        ],
        "additional_resources": ["Supplementary reading", "Practice exercises", "Extra resources"],
        "created_at": datetime.now().isoformat(),
        "status": "ready"
    }

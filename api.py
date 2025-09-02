import os
import json
import logging
from typing import Dict, Tuple, Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Import our custom modules
from syllabus_generator import SyllabusGenerator, initialize_course_from_syllabus
from tutor import AITutor, create_quiz_session, submit_quiz_answers, adjust_next_week_content, get_tutoring_help, get_personalized_study_tips

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Course Planning & Learning System", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class ChatbotRequest(BaseModel):
    state: dict
    user_input: Optional[str] = None

class CourseRequest(BaseModel):
    syllabus_text: str
    course_context: dict

class QuizRequest(BaseModel):
    week_info: dict
    course_context: dict

class QuizSubmissionRequest(BaseModel):
    quiz_session: dict
    user_answers: dict

class TutoringRequest(BaseModel):
    question: str
    week_info: dict
    course_context: dict

class WeekContentRequest(BaseModel):
    week_number: int
    course_data: dict

class ChatbotResponse(BaseModel):
    state: dict
    bot: str
    summary: Optional[dict] = None
    syllabus: Optional[str] = None
    course_ready: Optional[bool] = None
    error: Optional[str] = None

# Load AWS credentials
load_dotenv()

def get_bedrock_client():
    """Initialize Bedrock client with error handling"""
    try:
        client = boto3.client(
            'bedrock-runtime',
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock client: {str(e)}")
        raise

client = get_bedrock_client()

def ask_claude(messages: list, temperature: float = 0.7, max_tokens: int = 800) -> str:
    """Send a conversation to Claude and return response text with improved error handling"""
    try:
        response = client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            })
        )
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text'].strip()
    except (ClientError, BotoCoreError) as e:
        logger.error(f"AWS Bedrock error: {str(e)}")
        return "I'm having trouble connecting to my AI service. Please try again in a moment."
    except Exception as e:
        logger.error(f"Unexpected error in ask_claude: {str(e)}")
        return "I encountered an unexpected error. Please try again."

def get_conversation_context(state: dict) -> str:
    """Build conversation context from current state"""
    context_parts = []
    if state.get("topic"):
        context_parts.append(f"Topic: {state['topic']}")
    if state.get("difficulty"):
        context_parts.append(f"Difficulty: {state['difficulty']}")
    if state.get("duration"):
        context_parts.append(f"Duration: {state['duration']}")
    if state.get("learner_type"):
        context_parts.append(f"Learner type: {state['learner_type']}")
    if state.get("extra_info"):
        context_parts.append(f"Additional info: {state['extra_info']}")
    
    return " | ".join(context_parts) if context_parts else "Starting conversation"

def ai_intelligent_response(step: str, user_input: str, state: dict, specific_request: str = "") -> str:
    """Generate intelligent, contextual responses using Claude"""
    context = get_conversation_context(state)
    
    prompts = {
        "welcome": """You are Sandwich, a friendly AI learning assistant that helps people create personalized course plans. 
        Start a warm, engaging conversation by introducing yourself and asking what they'd like to learn. 
        Be enthusiastic and make them feel excited about their learning journey. Keep it conversational and brief.""",
        
        "topic_extraction": f"""You are Sandwich, an AI learning assistant. The user said: "{user_input}"
        
        Your task is to:
        1. Extract the learning topic from their message
        2. If the topic is clear, acknowledge it enthusiastically and ask about their experience level (beginner, intermediate, advanced)
        3. If the topic is unclear or too vague, ask them to be more specific in a friendly way
        4. If they mentioned multiple topics, help them choose one to focus on
        
        Context: {context}
        Be conversational, encouraging, and helpful. Keep your response concise but warm.""",
        
        "difficulty_assessment": f"""You are Sandwich, an AI learning assistant. The user wants to learn: {state.get('topic', 'the topic')}
        They said: "{user_input}" regarding their experience level.
        
        Your task is to:
        1. Acknowledge their experience level
        2. Ask how much time they can dedicate to learning (daily/weekly schedule or total duration)
        3. Be encouraging about their chosen difficulty level
        
        Context: {context}
        Keep it conversational and supportive.""",
        
        "duration_assessment": f"""You are Sandwich, an AI learning assistant. 
        User wants to learn: {state.get('topic', 'the topic')} at {state.get('difficulty', 'their chosen')} level
        They said: "{user_input}" about their time availability.
        
        Your task is to:
        1. Acknowledge their time commitment
        2. Assess if this is realistic for their topic and difficulty level
        3. If realistic: Ask about their learning style (visual, hands-on, reading, videos, etc.)
        4. If unrealistic: Gently suggest either narrowing the scope or extending the timeline, but be flexible
        
        Context: {context}
        Be helpful and realistic but not discouraging.""",
        
        "learning_style": f"""You are Sandwich, an AI learning assistant.
        User wants to learn: {state.get('topic', 'the topic')} at {state.get('difficulty', 'their chosen')} level in {state.get('duration', 'their timeframe')}
        They said: "{user_input}" about their learning preferences.
        
        Your task is to:
        1. Acknowledge their learning style preferences
        2. Ask if there's anything specific they want to focus on or any particular goals they have
        3. Let them know they can say "nothing specific" if they just want a general course
        
        Context: {context}
        Be encouraging and show that you understand their preferences.""",
        
        "final_details": f"""You are Sandwich, an AI learning assistant.
        The user said: "{user_input}" about their specific goals or focus areas.
        
        Current plan summary:
        - Topic: {state.get('topic', 'Not specified')}
        - Difficulty: {state.get('difficulty', 'Not specified')}
        - Duration: {state.get('duration', 'Not specified')}
        - Learning style: {state.get('learner_type', 'Not specified')}
        - Specific focus: {user_input if user_input and user_input.lower() not in ['nothing', 'none', 'nothing specific'] else 'General overview'}
        
        Your task is to:
        1. Acknowledge their input
        2. Present a brief, enthusiastic summary of their course plan
        3. Ask if they're ready to generate their personalized course or if they'd like to modify anything
        
        Be excited and encouraging about their learning journey!""",
        
        "scope_check": f"""You are an expert course planning consultant. Analyze this learning request:
        
        Topic: {state.get('topic', 'Unknown')}
        Difficulty: {state.get('difficulty', 'Unknown')}
        Duration: {state.get('duration', 'Unknown')}
        
        Assess if this is realistic and provide guidance:
        1. Is the duration appropriate for this topic and difficulty level?
        2. If too ambitious, suggest specific ways to narrow the scope OR extend the timeline
        3. If reasonable, acknowledge that and suggest the best approach
        4. Be encouraging but realistic
        
        Keep your response conversational and helpful, not academic or rigid."""
    }
    
    prompt = prompts.get(step, f"You are Sandwich, a helpful AI learning assistant. Respond appropriately to: '{user_input}' in the context of: {context}")
    
    if specific_request:
        prompt += f"\n\nSpecific request: {specific_request}"
    
    messages = [{"role": "user", "content": prompt}]
    return ask_claude(messages)

def extract_learning_info(user_input: str, info_type: str) -> str:
    """Extract and clean specific information from user input"""
    user_input = user_input.strip()
    
    if info_type == "topic":
        # Remove common prefixes
        prefixes = [
            "i want to learn", "i'd like to learn", "i want to study", 
            "teach me", "i'm interested in", "about", "learn", "study"
        ]
        text = user_input.lower()
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text.strip() or user_input
    
    return user_input

def chatbot_step(state: dict, user_input: Optional[str] = None) -> Tuple[dict, dict]:
    """Main chatbot conversation flow"""
    current_step = state.get("step", "welcome")
    
    try:
        # Welcome step - start conversation
        if current_step == "welcome":
            state["step"] = "topic"
            response = ai_intelligent_response("welcome", "", state)
            return state, {"bot": response}
        
        # Topic extraction and validation
        elif current_step == "topic" and user_input:
            response = ai_intelligent_response("topic_extraction", user_input, state)
            
            # Try to extract topic from user input
            topic = extract_learning_info(user_input, "topic")
            if topic and len(topic.split()) >= 1:  # Basic validation
                state["topic"] = topic
                state["step"] = "difficulty"
            # If topic extraction failed, AI response will ask for clarification
            
            return state, {"bot": response}
        
        # Difficulty/experience level
        elif current_step == "difficulty" and user_input:
            state["difficulty"] = user_input.strip()
            state["step"] = "duration"
            response = ai_intelligent_response("difficulty_assessment", user_input, state)
            return state, {"bot": response}
        
        # Duration and scope checking
        elif current_step == "duration" and user_input:
            state["duration"] = user_input.strip()
            
            # Check if scope is reasonable
            scope_check = ai_intelligent_response("scope_check", "", state)
            
            # If scope seems problematic, give user choice
            if any(word in scope_check.lower() for word in ["too", "unrealistic", "challenging", "difficult", "narrow", "extend"]):
                state["step"] = "scope_confirmation"
                state["scope_message"] = scope_check
                return state, {"bot": f"{scope_check}\n\nWould you like to proceed anyway, or would you prefer to adjust your plan?"}
            else:
                state["step"] = "learning_style"
                response = ai_intelligent_response("duration_assessment", user_input, state)
                return state, {"bot": response}
        
        # Handle scope confirmation
        elif current_step == "scope_confirmation" and user_input:
            user_lower = user_input.lower()
            if any(word in user_lower for word in ["proceed", "continue", "yes", "go ahead", "stick with"]):
                state["step"] = "learning_style"
                response = ai_intelligent_response("learning_style", "continuing with original plan", state)
                return state, {"bot": f"Great! Let's proceed with your original plan. {response}"}
            else:
                state["step"] = "topic"  # Start over with topic
                return state, {"bot": "No problem! Let's revise your learning plan. What would you like to focus on learning?"}
        
        # Learning style/preferences
        elif current_step == "learning_style" and user_input:
            state["learner_type"] = user_input.strip()
            state["step"] = "extra_info"
            response = ai_intelligent_response("learning_style", user_input, state)
            return state, {"bot": response}
        
        # Additional information and summary
        elif current_step == "extra_info" and user_input:
            state["extra_info"] = user_input.strip() if user_input.lower() not in ["nothing", "none", "nothing specific"] else ""
            state["step"] = "confirmation"
            
            response = ai_intelligent_response("final_details", user_input, state)
            
            return state, {
                "bot": response,
                "summary": {
                    "topic": state.get("topic", ""),
                    "difficulty": state.get("difficulty", ""),
                    "duration": state.get("duration", ""),
                    "learner_type": state.get("learner_type", ""),
                    "extra_info": state.get("extra_info", "")
                }
            }
        
        # Final confirmation
        elif current_step == "confirmation" and user_input:
            user_lower = user_input.lower()
            if any(word in user_lower for word in ["yes", "generate", "create", "go", "proceed", "ready"]):
                syllabus = generate_course_plan(state)
                state["step"] = "course_generated"
                return state, {
                    "bot": "🎉 Here's your personalized course plan! I've designed it specifically for your learning goals and preferences.",
                    "syllabus": syllabus,
                    "course_ready": True
                }
            elif any(word in user_lower for word in ["no", "modify", "change", "edit", "different"]):
                state["step"] = "modification"
                return state, {"bot": "What would you like to modify? You can say things like 'change the topic', 'different difficulty', 'more time', etc."}
            else:
                return state, {"bot": "I'd love to help! Just let me know if you'd like me to generate your course plan or if you'd like to modify something first."}
        
        # Handle modifications
        elif current_step == "modification" and user_input:
            user_lower = user_input.lower()
            if "topic" in user_lower:
                state["step"] = "topic"
                return state, {"bot": "What would you like to learn instead?"}
            elif "difficulty" in user_lower or "level" in user_lower:
                state["step"] = "difficulty"
                return state, {"bot": f"Got it! What's your experience level with {state.get('topic', 'this topic')}?"}
            elif "time" in user_lower or "duration" in user_lower:
                state["step"] = "duration"
                return state, {"bot": "How much time can you dedicate to learning?"}
            elif "style" in user_lower or "learning" in user_lower:
                state["step"] = "learning_style"
                return state, {"bot": "What's your preferred learning style?"}
            else:
                # Let AI figure out what they want to change
                response = f"I'd be happy to help you modify your plan! Could you be more specific about what you'd like to change? For example:\n- Topic: {state.get('topic', '')}\n- Difficulty: {state.get('difficulty', '')}\n- Duration: {state.get('duration', '')}\n- Learning style: {state.get('learner_type', '')}"
                return state, {"bot": response}
        
        # Course generated - ready to proceed
        elif current_step == "course_generated":
            if user_input and "proceed" in user_input.lower():
                return state, {"bot": "Great! Your course is ready to begin.", "course_ready": True}
            else:
                return state, {"bot": "Your course plan is ready! Would you like to proceed to the course, or do you have any questions?"}
        
        # Conversation complete
        elif current_step == "complete":
            return state, {"bot": "Your course plan is ready! Is there anything else you'd like to know about your learning journey?"}
        
        # Fallback for missing input
        else:
            return state, {"bot": "I'd love to help you! Could you please share what you're thinking?"}
            
    except Exception as e:
        logger.error(f"Error in chatbot_step: {str(e)}")
        return state, {"bot": "I apologize, but I encountered an issue. Could you please try rephrasing your message?"}

def generate_course_plan(state: dict) -> str:
    """Generate a comprehensive course plan using Claude"""
    prompt = f"""You are Sandwich, an expert AI learning assistant. Create a detailed, personalized course syllabus based on this information:

📚 **Course Details:**
- **Topic:** {state.get('topic', 'General')}
- **Difficulty Level:** {state.get('difficulty', 'Not specified')}
- **Time Commitment:** {state.get('duration', 'Flexible')}
- **Learning Style:** {state.get('learner_type', 'Mixed approach')}
- **Specific Focus:** {state.get('extra_info', 'Comprehensive overview')}

Create a structured course plan that includes:

1. **Course Overview** - Brief description and learning objectives
2. **Weekly/Module Breakdown** - Organized learning progression
3. **Learning Activities** - Tailored to their learning style preference
4. **Practice Exercises** - Hands-on applications
5. **Assessment Ideas** - Ways to test understanding
6. **Resources** - Recommended materials and tools
7. **Final Project** - Capstone experience
8. **Success Tips** - Personalized advice for staying motivated

Make it engaging, practical, and perfectly suited to their specified preferences. Use emojis and formatting to make it visually appealing and easy to follow.

Format the response in markdown for better readability."""

    messages = [{"role": "user", "content": prompt}]
    return ask_claude(messages, temperature=0.6, max_tokens=1500)

# API Endpoints

@app.post("/chatbot_step", response_model=ChatbotResponse)
async def chatbot_step_api(req: ChatbotRequest):
    """Main chatbot conversation endpoint"""
    try:
        state, response = chatbot_step(req.state, req.user_input)
        return ChatbotResponse(
            state=state,
            bot=response.get("bot", ""),
            summary=response.get("summary"),
            syllabus=response.get("syllabus"),
            course_ready=response.get("course_ready"),
            error=response.get("error")
        )
    except Exception as e:
        logger.error(f"Error in chatbot_step_api: {str(e)}")
        return ChatbotResponse(
            state=req.state,
            bot="I apologize, but I encountered an error. Please try again.",
            error=str(e)
        )

@app.post("/initialize_course")
async def initialize_course(req: CourseRequest):
    """Initialize a full course from syllabus text"""
    try:
        course_data = initialize_course_from_syllabus(req.syllabus_text, req.course_context)
        return {
            "success": True,
            "course_data": course_data,
            "message": "Course initialized successfully!"
        }
    except Exception as e:
        logger.error(f"Error initializing course: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_week_content")
async def get_week_content(req: WeekContentRequest):
    """Get detailed content for a specific week"""
    try:
        course_data = req.course_data
        weeks = course_data.get("weeks", [])
        
        week_content = None
        for week in weeks:
            if week.get("week_number") == req.week_number:
                week_content = week
                break
        
        if not week_content:
            raise HTTPException(status_code=404, detail="Week not found")
        
        return {
            "success": True,
            "week_content": week_content,
            "navigation": course_data.get("navigation", {})
        }
    except Exception as e:
        logger.error(f"Error getting week content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_quiz")
async def create_quiz(req: QuizRequest):
    """Create a quiz for a specific week"""
    try:
        quiz_session = create_quiz_session(req.week_info, req.course_context)
        return {
            "success": True,
            "quiz_session": quiz_session
        }
    except Exception as e:
        logger.error(f"Error creating quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_quiz")
async def submit_quiz(req: QuizSubmissionRequest):
    try:
        completed_quiz = submit_quiz_answers(req.quiz_session, req.user_answers)

        # Get current week number from the quiz session
        current_week_number = req.quiz_session.get("week_number", 1)
        course_data = req.quiz_session.get("course_data", {})
        weeks = course_data.get("weeks", [])

        # Find the next week info
        next_week_info = None
        for week in weeks:
            if week.get("week_number") == current_week_number + 1:
                next_week_info = week
                break

        course_context = req.quiz_session.get("course_context", {})
        recent_quiz = completed_quiz

        if next_week_info:
            revised_week_info = adjust_next_week_content(next_week_info, course_context, recent_quiz)
        else:
            revised_week_info = None

        return {
            "success": True,
            "quiz_results": completed_quiz,
            "revised_week_info": revised_week_info
        }
    except Exception as e:
        logger.error(f"Error submitting quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_tutoring_help")
async def get_tutoring_help_endpoint(req: TutoringRequest):
    """Get AI tutoring help for a question"""
    try:
        help_response = get_tutoring_help(req.question, req.week_info, req.course_context)
        return {
            "success": True,
            "tutoring_response": help_response
        }
    except Exception as e:
        logger.error(f"Error getting tutoring help: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_study_tips")
async def get_study_tips(req: TutoringRequest):
    """Get personalized study tips"""
    try:
        tips = get_personalized_study_tips(req.week_info, req.course_context)
        return {
            "success": True,
            "study_tips": tips
        }
    except Exception as e:
        logger.error(f"Error getting study tips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "AI Course System is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
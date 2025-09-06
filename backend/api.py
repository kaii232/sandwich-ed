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
        "welcome": """You are Sandwich, an AI learning assistant. 
        Ask what they'd like to learn in a brief, friendly way. Keep it under 20 words.""",
        
        "topic_extraction": f"""You are Sandwich, an AI learning assistant. The user said: "{user_input}"
        
        Extract the learning topic. If clear, acknowledge briefly and ask about experience level.
        If unclear, ask them to be more specific.
        If too broad (like "programming" or "business"), suggest 2-3 specific subtopics but say they can proceed with the broad topic if they prefer.
        
        Keep response under 30 words. No excitement phrases or lengthy encouragement.""",
        
        "difficulty_assessment": f"""You are Sandwich. The user wants to learn: {state.get('topic', 'the topic')}
        They said: "{user_input}" about experience level.
        
        Acknowledge briefly, then ask about time commitment. Keep under 20 words.""",
        
        "duration_assessment": f"""You are Sandwich. 
        Topic: {state.get('topic', 'the topic')} at {state.get('difficulty', 'their')} level
        They said: "{user_input}" about time.
        
        If unrealistic (like "1 day" for complex topics), suggest a better timeframe but say they can proceed if they insist.
        Then ask about learning style. Keep under 30 words.""",
        
        "learning_style": f"""You are Sandwich.
        Topic: {state.get('topic', 'the topic')}, Level: {state.get('difficulty', 'their chosen')}, Duration: {state.get('duration', 'their timeframe')}
        
        Ask them to choose their preferred learning style from these options:
        A) Videos and visual content
        B) Reading and text-based materials  
        C) Hands-on practice and projects
        D) Mix of all approaches
        
        Keep response under 25 words.""",
        
        "final_details": f"""You are Sandwich.
        
        Ask if they have specific goals (like job hunting, certification, personal project) or if they want a general course.
        Keep under 20 words.""",
        
        "confirmation": f"""You are Sandwich.
        
        Show this summary:
        • Topic: {state.get('topic', 'Not specified')}
        • Level: {state.get('difficulty', 'Not specified')}
        • Duration: {state.get('duration', 'Not specified')}
        • Style: {state.get('learner_type', 'Not specified')}
        • Goals: {state.get('extra_info', 'General learning')}
        
        Ask "Ready to generate your course?" Keep under 10 words after the summary.""",
        
        "scope_check": f"""You are Sandwich. Analyze this request:
        
        Topic: {state.get('topic', 'Unknown')}
        Level: {state.get('difficulty', 'Unknown')}  
        Duration: {state.get('duration', 'Unknown')}
        
        If the topic is too broad, suggest 2-3 specific subtopics but mention they can proceed anyway.
        If duration is too short, suggest a realistic timeframe but mention they can proceed anyway.
        If reasonable, just say "Looks good!"
        
        Keep response under 40 words. No lengthy explanations."""
    }
    
    prompt = prompts.get(step, f"You are Sandwich. Respond briefly to: '{user_input}'. Context: {context}. Under 20 words.")
    
    if specific_request:
        prompt += f"\n\nSpecific request: {specific_request}"
    
    # Add instruction to avoid action descriptions
    prompt += "\n\nImportant: Do not include action descriptions like *smiles* or *greets*. Just respond naturally and concisely."
    
    messages = [{"role": "user", "content": prompt}]
    return ask_claude(messages, temperature=0.5, max_tokens=200)  # Reduced max_tokens for conciseness

def chatbot_step(state: dict, user_input: Optional[str] = None) -> Tuple[dict, dict]:
    """Main chatbot conversation flow"""
    current_step = state.get("step", "welcome")
    
    try:
        # Welcome step - start conversation
        if current_step == "welcome":
            state["step"] = "topic"
            return state, {"bot": "Hi! I'm Sandwich, your learning assistant. What would you like to learn?"}
        
        # Topic extraction and validation
        elif current_step == "topic" and user_input:
            # First check if the input actually contains a learning topic
            topic_check_prompt = f"""
            Does this message contain a specific learning topic or subject the user wants to learn?
            
            Message: "{user_input}"
            
            Examples of messages WITH learning topics:
            - "I want to learn physics" → YES
            - "Can you teach me Python?" → YES  
            - "I'd like to study calculus" → YES
            
            Examples of messages WITHOUT learning topics:
            - "Hi, I am John" → NO
            - "Hello there" → NO
            - "How are you?" → NO
            
            Just respond with "YES" or "NO".
            """
            
            messages = [{"role": "user", "content": topic_check_prompt}]
            has_topic = ask_claude(messages, temperature=0.1, max_tokens=10).strip().upper()
            
            if has_topic == "NO":
                return state, {"bot": "Hello! What subject or skill would you like to learn?"}
            
            # Extract the actual topic
            extraction_prompt = f"""
            Extract just the learning topic from this message: "{user_input}"
            
            Examples:
            - "Hi, I want to learn physics" → "physics"  
            - "I'd like to study machine learning" → "machine learning"
            - "Can you help me with calculus?" → "calculus"
            - "I need to learn Python programming" → "Python programming"
            
            Return only the topic name, nothing else.
            """
            
            messages = [{"role": "user", "content": extraction_prompt}]
            topic = ask_claude(messages, temperature=0.1, max_tokens=20).strip()
            
            if not topic or len(topic) < 2:
                return state, {"bot": "Could you tell me what specific subject you'd like to learn?"}

            # Check if topic is too broad using AI
            broad_check_prompt = f"""
            Is the topic "{topic}" too broad for a structured course?

            A topic is considered "broad" if it's a general field that contains many subtopics that could be separate courses.

            Examples of BROAD topics:
            - "programming" (contains Python, Java, web dev, etc.)
            - "math" (contains algebra, calculus, geometry, etc.)
            - "business" (contains marketing, finance, management, etc.)
            - "science" (contains physics, chemistry, biology, etc.)

            Examples of SPECIFIC topics:
            - "Python programming"
            - "calculus"
            - "digital marketing"
            - "organic chemistry"

            Just respond with "BROAD" or "SPECIFIC".
            """

            messages = [{"role": "user", "content": broad_check_prompt}]
            breadth_check = ask_claude(messages, temperature=0.1, max_tokens=10).strip().upper()

            if breadth_check == "BROAD":
                # Generate specific suggestions for broad topics
                suggestion_prompt = f"""
                The user wants to learn "{topic}" which is quite broad. 
                Suggest 2-3 specific subtopics they could focus on instead.
                
                Format: "'{topic}' is quite broad. I can suggest specific areas like [subtopic 1], [subtopic 2], or [subtopic 3], or we can proceed with the general topic. What would you prefer?"
                
                Keep it under 40 words.
                """
                
                messages = [{"role": "user", "content": suggestion_prompt}]
                response = ask_claude(messages, temperature=0.3, max_tokens=100).strip()
                
                state["pending_topic"] = topic
                state["step"] = "topic_confirmation"
            else:
                state["topic"] = topic
                state["step"] = "difficulty"
                response = f"Got it - {topic}! What's your experience level? (Beginner/Intermediate/Advanced)"
            
            return state, {"bot": response}

        # Handle broad topic confirmation
        elif current_step == "topic_confirmation" and user_input:
            user_lower = user_input.lower()
            
            # Check if they want to stick with the broad topic
            if any(word in user_lower for word in ["stick", "proceed", "continue", "broad", "general", "yes", "fine", "ok", "okay"]):
                state["topic"] = state["pending_topic"]
                state["step"] = "difficulty"
                response = f"Perfect! What's your experience level with {state['topic']}? (Beginner/Intermediate/Advanced)"
            
            # Use Claude to determine if this is background info or a new topic choice
            else:
                intent_prompt = f"""
                The user was asked if they want to narrow down the broad topic "{state.get('pending_topic', '')}" or proceed with it.
                
                User response: "{user_input}"
                
                Is this response:
                A) Background/context information (like describing their situation, experience, or current status)
                B) A new specific topic they want to learn instead
                
                Just respond with "A" or "B".
                """
                
                messages = [{"role": "user", "content": intent_prompt}]
                intent = ask_claude(messages, temperature=0.1, max_tokens=10).strip().upper()
                
                if intent == "A":
                    # Background info - stick with original topic
                    state["topic"] = state["pending_topic"]
                    state["step"] = "difficulty"
                    response = f"Got it! What's your experience level with {state['topic']}? (Beginner/Intermediate/Advanced)"
                else:
                    # New topic choice - use user_input, not undefined 'topic'
                    state["topic"] = user_input.strip()  # ✅ Fixed: use user_input instead of topic
                    state["step"] = "difficulty"
                    
                    # Generate context-aware difficulty examples
                    difficulty_prompt = f"""
                    The user wants to learn "{user_input}". Provide a brief question asking about their experience level with helpful examples specific to this topic.
                    
                    Format: "Got it - {user_input}! What's your experience level?
                    
                    • Beginner: [specific example for this topic]
                    • Intermediate: [specific example for this topic]  
                    • Advanced: [specific example for this topic]"
                    
                    Examples of good difficulty descriptions:
                    For "Python programming":
                    - Beginner: Never coded before or just learning variables/loops
                    - Intermediate: Can write functions and work with libraries
                    - Advanced: Experience with frameworks and complex projects
                    
                    For "human geography":
                    - Beginner: Basic understanding of world regions
                    - Intermediate: Familiar with population and cultural patterns
                    - Advanced: Deep knowledge of spatial analysis and theory
                    
                    Keep the entire response under 60 words.
                    """
                    
                    messages = [{"role": "user", "content": difficulty_prompt}]
                    response = ask_claude(messages, temperature=0.3, max_tokens=150).strip()
            
            state.pop("pending_topic", None)
            return state, {"bot": response}
        
        # Difficulty/experience level  
        elif current_step == "difficulty" and user_input:
            state["difficulty"] = user_input.strip()
            state["step"] = "duration"
            return state, {"bot": "How much time can you dedicate? (e.g., '2 weeks', '1 hour daily for a month')"}
        
        # Duration and scope checking
        elif current_step == "duration" and user_input:
            duration_lower = user_input.lower()
            
            # Check for very short durations
            short_indicators = ["1 day", "one day", "few hours", "weekend", "tonight"]
            is_too_short = any(indicator in duration_lower for indicator in short_indicators)
            
            if is_too_short:
                state["pending_duration"] = user_input.strip()
                state["step"] = "duration_confirmation"
                response = f"That's quite short for {state.get('topic', 'this topic')}. I'd suggest at least 1-2 weeks. Proceed with {user_input} anyway?"
            else:
                state["duration"] = user_input.strip()
                state["step"] = "learning_style"
                response = "Choose your learning style:\nA) Videos and visual content\nB) Reading and text\nC) Hands-on projects\nD) Mix of all"
            
            return state, {"bot": response}
        
        # Handle short duration confirmation
        elif current_step == "duration_confirmation" and user_input:
            user_lower = user_input.lower()
            if any(word in user_lower for word in ["stick", "proceed", "continue", "yes", "only"]):
                state["duration"] = state["pending_duration"]
            else:
                state["duration"] = user_input.strip()
            
            state["step"] = "learning_style"
            state.pop("pending_duration", None)
            return state, {"bot": "Choose your learning style:\nA) Videos and visual content\nB) Reading and text\nC) Hands-on projects\nD) Mix of all"}
        
        # Learning style with structured options
        elif current_step == "learning_style" and user_input:
            user_choice = user_input.strip().upper()
            
            style_map = {
                "A": "Videos and visual content",
                "B": "Reading and text-based materials", 
                "C": "Hands-on practice and projects",
                "D": "Mix of all approaches"
            }
            
            if user_choice in style_map:
                state["learner_type"] = style_map[user_choice]
            else:
                # Try to map common responses
                user_lower = user_input.lower()
                if any(word in user_lower for word in ["video", "visual", "watch"]):
                    state["learner_type"] = "Videos and visual content"
                elif any(word in user_lower for word in ["read", "text", "book"]):
                    state["learner_type"] = "Reading and text-based materials"
                elif any(word in user_lower for word in ["hands", "practice", "project", "do"]):
                    state["learner_type"] = "Hands-on practice and projects"
                elif any(word in user_lower for word in ["mix", "all", "combination"]):
                    state["learner_type"] = "Mix of all approaches"
                else:
                    return state, {"bot": "Please choose A, B, C, or D from the options above."}
            
            state["step"] = "extra_info"
            return state, {"bot": "Any specific goals? (job hunting, certification, personal project, or just say 'general')"}
        
        # Additional information
        elif current_step == "extra_info" and user_input:
            state["extra_info"] = user_input.strip() if user_input.lower() not in ["general", "none", "no"] else ""
            state["step"] = "confirmation"
            
            summary = f"""Here's your course plan:

• **Topic:** {state.get('topic', '')}
• **Level:** {state.get('difficulty', '')}
• **Duration:** {state.get('duration', '')}
• **Style:** {state.get('learner_type', '')}
• **Goals:** {state.get('extra_info') or 'General learning'}

Ready to generate your course?"""
            
            return state, {
                "bot": summary,
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
                    "bot": "Here's your personalized course plan!",
                    "syllabus": syllabus,
                    "course_ready": True
                }
            elif any(word in user_lower for word in ["no", "modify", "change", "edit", "different"]):
                state["step"] = "modification"
                return state, {"bot": "What would you like to change? (topic, difficulty, duration, style, or goals)"}
            else:
                return state, {"bot": "Please say 'yes' to generate your course or 'modify' to make changes."}
        
        # Handle modifications
        elif current_step == "modification" and user_input:
            user_lower = user_input.lower()
            if "topic" in user_lower:
                state["step"] = "topic"
                return state, {"bot": "What would you like to learn instead?"}
            elif "difficulty" in user_lower or "level" in user_lower:
                state["step"] = "difficulty"
                return state, {"bot": f"What's your experience level with {state.get('topic', 'this topic')}? (Beginner/Intermediate/Advanced)"}
            elif "duration" in user_lower or "time" in user_lower:
                state["step"] = "duration"
                return state, {"bot": "How much time can you dedicate?"}
            elif "style" in user_lower:
                state["step"] = "learning_style"
                return state, {"bot": "Choose your learning style:\nA) Videos and visual content\nB) Reading and text\nC) Hands-on projects\nD) Mix of all"}
            elif "goal" in user_lower:
                state["step"] = "extra_info"
                return state, {"bot": "What are your specific goals?"}
            else:
                return state, {"bot": "Please specify: topic, difficulty, duration, style, or goals"}
        
        # Course generated
        elif current_step == "course_generated":
            return state, {"bot": "Your course is ready! Would you like to start learning?", "course_ready": True}
        
        # Fallback
        else:
            return state, {"bot": "Could you please rephrase that?"}
            
    except Exception as e:
        logger.error(f"Error in chatbot_step: {str(e)}")
        return state, {"bot": "Sorry, I encountered an error. Could you try again?"}


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
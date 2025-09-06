import os
import json
import logging
import traceback
import uvicorn
from datetime import datetime
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

class AdaptiveWeekRequest(BaseModel):
    week_info: dict
    course_context: dict
    
class WeekContentRequest(BaseModel):
    week_info: dict
    course_context: dict

class TutoringRequest(BaseModel):
    question: str
    week_info: dict
    course_context: dict

class WeekContentRequest(BaseModel):
    week_number: int
    course_data: dict

class LessonContentRequest(BaseModel):
    lesson_info: dict
    course_context: dict

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

# Global storage for course data and progressive content
course_storage = {}
COURSE_DATA_FILE = "progressive_course_data.json"

async def generate_next_week_content(completed_week_number: int, course_context: dict, quiz_results: dict) -> dict:
    """Generate content for the next week after successful quiz completion"""
    next_week_number = completed_week_number + 1
    course_topic = course_context.get('topic', 'General Studies')
    
    try:
        # Load existing course data
        course_data = load_course_data()
        
        # Check if next week already exists
        existing_weeks = course_data.get('weeks', [])
        if any(week.get('week_number') == next_week_number for week in existing_weeks):
            logger.info(f"Week {next_week_number} already exists, skipping generation")
            return course_data
        
        # Generate next week content based on previous week performance
        generator = SyllabusGenerator()
        
        # Analyze performance to determine content focus
        performance_percentage = quiz_results.get('percentage', 75)
        weak_areas = identify_weak_areas(quiz_results)
        
        # Generate new week content
        logger.info(f"Generating Week {next_week_number} content based on {performance_percentage}% performance")
        
        next_week_data = await generate_adaptive_week_content(
            week_number=next_week_number,
            course_topic=course_topic,
            performance_data=quiz_results,
            weak_areas=weak_areas,
            course_context=course_context
        )
        
        # Add the new week to course data
        course_data.setdefault('weeks', []).append(next_week_data)
        
        # Update navigation
        course_data['navigation'] = {
            'current_week': next_week_number,
            'total_weeks': len(course_data['weeks']),
            'course_status': 'in_progress'
        }
        
        # Pre-generate quiz for the new week
        try:
            logger.info(f"Pre-generating quiz for Week {next_week_number}")
            tutor = AITutor()
            quiz_data = tutor.create_quiz(next_week_data, course_context)
            
            # Store the pre-generated quiz
            course_data.setdefault('pre_generated_quizzes', {})[str(next_week_number)] = quiz_data
            logger.info(f"Successfully pre-generated quiz for Week {next_week_number}")
        except Exception as e:
            logger.error(f"Failed to pre-generate quiz for Week {next_week_number}: {str(e)}")
            # Continue without pre-generated quiz
        
        # Save updated course data
        save_course_data(course_data)
        
        logger.info(f"Successfully generated Week {next_week_number}: {next_week_data.get('title', 'Untitled')}")
        return course_data
        
    except Exception as e:
        logger.error(f"Error generating next week content: {str(e)}")
        raise

async def generate_adaptive_week_content(week_number: int, course_topic: str, performance_data: dict, 
                                       weak_areas: list, course_context: dict) -> dict:
    """Generate adaptive content for a new week based on previous performance"""
    
    performance_percentage = performance_data.get('percentage', 75)
    
    # Determine content difficulty and focus
    if performance_percentage >= 85:
        difficulty_level = "advanced"
        focus_type = "expansion"
    elif performance_percentage >= 70:
        difficulty_level = "standard"
        focus_type = "progression"
    else:
        difficulty_level = "supportive"
        focus_type = "reinforcement"
    
    prompt = f"""
Generate comprehensive content for Week {week_number} of a {course_topic} course.

**Previous Performance Analysis:**
- Week {week_number - 1} Quiz Score: {performance_percentage}%
- Weak Areas: {', '.join(weak_areas) if weak_areas else 'None identified'}
- Content Focus: {focus_type}
- Difficulty Level: {difficulty_level}

**Week {week_number} Content Requirements:**

1. **Week Title**: Create an engaging, specific title that builds on previous content

2. **Overview**: Brief paragraph explaining what students will learn this week

3. **Lesson Topics**: Generate 4 detailed lesson topics, each with:
   - Clear, descriptive title
   - Learning objectives (3-4 specific goals)
   - Key concepts to cover
   - Practical applications

4. **Additional Resources**: Suggest 3-4 supplementary materials or activities

**Adaptive Considerations:**
{f"- Focus on reinforcing concepts from weak areas: {', '.join(weak_areas)}" if weak_areas else ""}
{f"- Increase complexity and introduce advanced concepts" if difficulty_level == "advanced" else ""}
{f"- Provide extra support and practice opportunities" if difficulty_level == "supportive" else ""}

Generate engaging, educational content that appropriately challenges students while addressing their learning needs.

**Format your response as a structured outline with clear sections.**
"""

    try:
        messages = [{"role": "user", "content": prompt}]
        response = ask_claude(messages, temperature=0.3, max_tokens=2000)
        
        # Parse the response into structured data
        week_data = parse_week_content_response(response, week_number, difficulty_level, course_context)
        
        return week_data
        
    except Exception as e:
        logger.error(f"Error generating adaptive week content: {str(e)}")
        # Return a basic fallback structure
        return create_fallback_week_data(week_number, course_topic, difficulty_level)

def parse_week_content_response(response: str, week_number: int, difficulty_level: str, course_context: dict) -> dict:
    """Parse AI response into structured week data"""
    try:
        # Extract title
        title_match = response.split('\n')[0]
        title = title_match.replace('**', '').replace('#', '').strip() or f"Week {week_number}: Advanced Concepts"
        
        # Basic structure
        week_data = {
            "week_number": week_number,
            "title": title,
            "difficulty_level": difficulty_level,
            "overview": "This week builds on previous concepts with new challenging material.",
            "lesson_topics": [],
            "additional_resources": [],
            "created_at": datetime.now().isoformat(),
            "status": "ready"
        }
        
        # Extract lesson topics (simplified parsing)
        lines = response.split('\n')
        current_section = None
        lesson_count = 0
        
        for line in lines:
            line = line.strip()
            
            if 'lesson' in line.lower() and lesson_count < 4:
                lesson_count += 1
                week_data["lesson_topics"].append({
                    "title": line.replace('**', '').replace('-', '').strip() or f"Lesson {lesson_count}",
                    "type": "lesson",
                    "content": f"Detailed content for lesson {lesson_count} covering key concepts.",
                    "learning_objectives": [
                        f"Understand key concept {lesson_count}",
                        f"Apply learned principles in practical scenarios",
                        f"Analyze complex problems using new methods"
                    ]
                })
        
        # Ensure we have at least 4 lessons
        while len(week_data["lesson_topics"]) < 4:
            lesson_num = len(week_data["lesson_topics"]) + 1
            week_data["lesson_topics"].append({
                "title": f"Advanced Topic {lesson_num}",
                "type": "lesson",
                "content": f"Comprehensive coverage of advanced topic {lesson_num}.",
                "learning_objectives": [
                    f"Master advanced concept {lesson_num}",
                    "Apply knowledge to real-world scenarios",
                    "Develop critical thinking skills"
                ]
            })
        
        return week_data
        
    except Exception as e:
        logger.error(f"Error parsing week content response: {str(e)}")
        return create_fallback_week_data(week_number, course_context.get('topic', 'Studies'), difficulty_level)

def create_fallback_week_data(week_number: int, course_topic: str, difficulty_level: str) -> dict:
    """Create fallback week data if AI generation fails"""
    return {
        "week_number": week_number,
        "title": f"Week {week_number}: {course_topic} - Advanced Concepts",
        "difficulty_level": difficulty_level,
        "overview": f"This week covers advanced {course_topic} concepts building on previous learning.",
        "lesson_topics": [
            {
                "title": f"{course_topic} Fundamentals Review",
                "type": "lesson",
                "content": "Review and reinforce fundamental concepts.",
                "learning_objectives": ["Review key principles", "Strengthen understanding", "Prepare for advanced topics"]
            },
            {
                "title": f"Advanced {course_topic} Concepts",
                "type": "lesson", 
                "content": "Introduction to more complex topics and applications.",
                "learning_objectives": ["Learn advanced concepts", "Understand complex applications", "Develop problem-solving skills"]
            },
            {
                "title": f"Practical Applications",
                "type": "lesson",
                "content": "Real-world applications and case studies.",
                "learning_objectives": ["Apply knowledge practically", "Analyze real scenarios", "Develop implementation skills"]
            },
            {
                "title": f"Assessment Guide",
                "type": "lesson", 
                "content": "Preparation for assessment and skill evaluation.",
                "learning_objectives": ["Prepare for assessment", "Self-evaluate progress", "Identify areas for improvement"]
            }
        ],
        "additional_resources": [
            "Supplementary reading materials",
            "Practice exercises and examples", 
            "Additional learning resources"
        ],
        "created_at": datetime.now().isoformat(),
        "status": "ready"
    }

def identify_weak_areas(quiz_results: dict) -> list:
    """Identify areas where student struggled based on quiz results"""
    weak_areas = []
    
    if not quiz_results.get('feedback'):
        return weak_areas
    
    for question_feedback in quiz_results['feedback']:
        if not question_feedback.get('is_correct', True):
            # Extract topic/concept from question text
            question_text = question_feedback.get('question_text', '').lower()
            
            # Simple keyword extraction for common topics
            if 'calculate' in question_text or 'math' in question_text:
                weak_areas.append('Mathematical calculations')
            elif 'theory' in question_text or 'concept' in question_text:
                weak_areas.append('Theoretical understanding')
            elif 'apply' in question_text or 'practical' in question_text:
                weak_areas.append('Practical application')
            elif 'problem' in question_text:
                weak_areas.append('Problem solving')
    
    # Remove duplicates
    return list(set(weak_areas))

def load_course_data() -> dict:
    """Load course data from storage"""
    try:
        if os.path.exists(COURSE_DATA_FILE):
            with open(COURSE_DATA_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading course data: {str(e)}")
    
    return {"weeks": [], "navigation": {"current_week": 1, "total_weeks": 1}}

def save_course_data(course_data: dict):
    """Save course data to storage"""
    try:
        with open(COURSE_DATA_FILE, 'w') as f:
            json.dump(course_data, f, indent=2)
        logger.info(f"Course data saved to {COURSE_DATA_FILE}")
    except Exception as e:
        logger.error(f"Error saving course data: {str(e)}")

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
                
                # Generate context-aware difficulty examples for the broad topic too
                difficulty_prompt = f"""
                The user wants to learn "{state['pending_topic']}". Provide a brief question asking about their experience level with helpful examples specific to this topic.
                
                Format: "Perfect! What's your experience level with {state['pending_topic']}?
                
                • Beginner: [specific example for this topic]
                • Intermediate: [specific example for this topic]  
                • Advanced: [specific example for this topic]"
                
                Examples of good difficulty descriptions:
                For "cryptography":
                - Beginner: New to encryption concepts, unfamiliar with algorithms
                - Intermediate: Know basic encryption methods, some programming experience
                - Advanced: Familiar with advanced algorithms and cryptographic protocols
                
                Keep the entire response under 60 words.
                """
                
                messages = [{"role": "user", "content": difficulty_prompt}]
                response = ask_claude(messages, temperature=0.3, max_tokens=150).strip()
                
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
                    # New topic choice
                    state["topic"] = user_input.strip()
                    state["step"] = "difficulty"
                    
                    # Generate context-aware difficulty examples for the new specific topic
                    difficulty_prompt = f"""
                    The user wants to learn "{user_input}". Provide a brief question asking about their experience level with helpful examples specific to this topic.
                    
                    Format: "Got it - {user_input}! What's your experience level?
                    
                    • Beginner: [specific example for this topic]
                    • Intermediate: [specific example for this topic]  
                    • Advanced: [specific example for this topic]"
                    
                    Keep the entire response under 60 words.
                    """
                    
                    messages = [{"role": "user", "content": difficulty_prompt}]
                    response = ask_claude(messages, temperature=0.3, max_tokens=150).strip()
            
            state.pop("pending_topic", None)
            return state, {"bot": response}

        # Difficulty/experience level with question detection
        elif current_step == "difficulty" and user_input:
            user_lower = user_input.lower()
            
            # Check if user is asking a question about difficulty levels
            if any(phrase in user_lower for phrase in ["what is", "what's", "explain", "define", "help", "clarify", "don't understand"]):
                # They're asking for clarification - provide examples
                clarification_prompt = f"""
                The user is asking about difficulty levels for learning "{state.get('topic', 'this subject')}". 
                Provide clear, helpful examples of what each level means for this specific topic.
                
                Format: "Here's what each level means for {state.get('topic', 'this subject')}:
                
                • Beginner: [specific description]
                • Intermediate: [specific description]
                • Advanced: [specific description]
                
                Which level best describes you?"
                
                Keep response under 80 words.
                """
                
                messages = [{"role": "user", "content": clarification_prompt}]
                response = ask_claude(messages, temperature=0.3, max_tokens=200).strip()
                return state, {"bot": response}
            
            # Otherwise, treat as their difficulty level
            else:
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
        logger.error(f"Error in API initialize_course: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_week_content")
async def get_week_content(req: WeekContentRequest):
    """Get detailed content for a specific week"""
    try:
        course_data = req.course_data
        weeks = course_data.get("weeks", [])
        
        # Also check progressive course data for dynamically generated weeks
        progressive_data = load_course_data()
        progressive_weeks = progressive_data.get("weeks", [])
        
        # Combine static and progressive weeks
        all_weeks = weeks + [w for w in progressive_weeks if not any(sw.get('week_number') == w.get('week_number') for sw in weeks)]
        
        # Add debugging logs
        logger.info(f"Requested week number: {req.week_number}")
        logger.info(f"Total weeks in static course data: {len(weeks)}")
        logger.info(f"Total weeks in progressive data: {len(progressive_weeks)}")
        logger.info(f"Combined available week numbers: {[w.get('week_number') for w in all_weeks]}")

        week_content = None
        for week in all_weeks:
            if week.get("week_number") == req.week_number:
                week_content = week
                break
        
        if not week_content:
            # If week not found, check if it should be generated
            if req.week_number > 1:
                logger.info(f"Week {req.week_number} not found, may need to complete previous weeks first")
                raise HTTPException(status_code=404, detail=f"Week {req.week_number} is not available yet. Complete previous weeks to unlock it.")
            else:
                raise HTTPException(status_code=404, detail="Week not found")
        
        # Update navigation info
        navigation = course_data.get("navigation", {})
        navigation.update({
            "total_weeks": len(all_weeks),
            "available_weeks": len(all_weeks)
        })
        
        return {
            "success": True,
            "week_content": week_content,
            "navigation": navigation,
            "is_progressive": week_content.get("created_at") is not None  # Flag to indicate dynamically generated content
        }
    except Exception as e:
        logger.error(f"Error getting week content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_quiz")
async def create_quiz(req: QuizRequest):
    """Create a quiz for a specific week"""
    try:
        week_number = req.week_info.get('week_number')
        
        # Check for pre-generated quiz first
        progressive_data = load_course_data()
        pre_generated_quizzes = progressive_data.get('pre_generated_quizzes', {})
        
        if str(week_number) in pre_generated_quizzes:
            logger.info(f"Using pre-generated quiz for Week {week_number}")
            pre_generated_quiz = pre_generated_quizzes[str(week_number)]
            
            # Create quiz session with pre-generated content
            quiz_session = {
                "quiz": pre_generated_quiz,
                "week_info": req.week_info,
                "course_context": req.course_context,
                "start_time": datetime.now().isoformat(),
                "time_remaining": 30 * 60,  # 30 minutes in seconds
                "status": "active"
            }
            
            return {
                "success": True,
                "quiz_session": quiz_session,
                "pre_generated": True
            }
        else:
            # Generate quiz dynamically as usual
            logger.info(f"Generating new quiz for Week {week_number}")
            quiz_session = create_quiz_session(req.week_info, req.course_context)
            
            return {
                "success": True,
                "quiz_session": quiz_session,
                "pre_generated": False
            }
    except Exception as e:
        logger.error(f"Error creating quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/course_progress")
async def get_course_progress():
    """Get the current course progress and available weeks"""
    try:
        progressive_data = load_course_data()
        weeks = progressive_data.get("weeks", [])
        navigation = progressive_data.get("navigation", {"current_week": 1, "total_weeks": 1})
        
        return {
            "success": True,
            "total_weeks": len(weeks),
            "available_weeks": [w.get('week_number') for w in weeks],
            "navigation": navigation,
            "course_status": navigation.get("course_status", "in_progress")
        }
    except Exception as e:
        logger.error(f"Error getting course progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_quiz")
async def submit_quiz(req: QuizSubmissionRequest):
    try:
        logger.info(f"Submitting quiz with answers: {req.user_answers}")
        completed_quiz = submit_quiz_answers(req.quiz_session, req.user_answers)
        
        # Log the quiz results for debugging
        quiz_results = completed_quiz.get("results", {})
        percentage = quiz_results.get('percentage', 0)
        logger.info(f"Quiz graded - Score: {quiz_results.get('user_score', 0)}/{quiz_results.get('total_points', 0)} ({percentage}%)")

        # Get quiz context for adaptive learning
        quiz = req.quiz_session.get("quiz", {})
        current_week_number = quiz.get("week_number", 1)
        
        # Get course context - need to extract from request or session
        course_context = req.quiz_session.get("course_context", {})
        
        # For next week adaptation, we need the original next week plan
        # This should ideally come from the course data structure
        next_week_number = current_week_number + 1
        
        # Create a generic next week template if not provided
        # In a real implementation, this would come from the original syllabus
        next_week_template = {
            "week_number": next_week_number,
            "title": f"Week {next_week_number}: Advanced Topics",
            "topics": [
                f"Advanced concepts in {course_context.get('topic', 'the subject')}",
                f"Complex problem solving",
                f"Practical applications",
                f"Integration of concepts"
            ]
        }
        
        # Apply adaptive learning based on quiz performance
        logger.info(f"Adapting Week {next_week_number} based on {percentage}% performance")
        adapted_week = adjust_next_week_content(next_week_template, course_context, completed_quiz)
        
        # Trigger progressive content generation if quiz passed (70% or higher)
        if percentage >= 70:
            try:
                logger.info(f"Quiz passed with {percentage}%, generating next week content...")
                course_data = await generate_next_week_content(current_week_number, course_context, quiz_results)
                logger.info(f"Successfully generated content for week {next_week_number}")
                
                # Update the adapted_week with the newly generated content
                generated_weeks = course_data.get('weeks', [])
                for week in generated_weeks:
                    if week.get('week_number') == next_week_number:
                        adapted_week = week
                        break
                        
            except Exception as e:
                logger.error(f"Failed to generate progressive content: {str(e)}")
                # Continue with basic adaptation if progressive generation fails
        
        # Log the adaptation
        adaptation_type = "accelerated" if percentage >= 90 else "reinforced" if percentage < 70 else "balanced"
        logger.info(f"Week {next_week_number} {adaptation_type} - New title: {adapted_week.get('title', 'Unknown')}")

        return {
            "success": True,
            "quiz_results": quiz_results,
            "adapted_next_week": adapted_week,
            "adaptation_summary": {
                "current_week": current_week_number,
                "performance": percentage,
                "adaptation_type": adaptation_type,
                "next_week_difficulty": adapted_week.get("difficulty_level", "standard"),
                "next_quiz_difficulty": adapted_week.get("quiz_difficulty", "same")
            }
        }
    except Exception as e:
        logger.error(f"Error submitting quiz: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
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

@app.post("/get_lesson_content")
async def get_lesson_content(req: LessonContentRequest):
    """Get detailed content for a specific lesson point"""
    try:
        generator = SyllabusGenerator()
        lesson_content = generator.generate_lesson_content(req.lesson_info, req.course_context)
        
        return {
            "success": True,
            "lesson_content": lesson_content
        }
    except Exception as e:
        logger.error(f"Error getting lesson content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_adaptive_week")
async def generate_adaptive_week(req: WeekContentRequest):
    """Generate detailed content for an adapted week"""
    try:
        logger.info(f"Generating adaptive week content for: {req.week_info.get('title', 'Unknown')}")
        
        generator = SyllabusGenerator()
        detailed_week = generator.generate_week_content(req.week_info, req.course_context)
        
        return {
            "success": True,
            "week_content": detailed_week
        }
    except Exception as e:
        logger.error(f"Error generating adaptive week: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "AI Course System is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
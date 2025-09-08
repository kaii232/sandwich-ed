import re
import logging
from typing import Tuple, Optional
from datetime import datetime
from app.core.bedrock import ask_claude
from app.core.config import COURSE_DATA_FILE
from syllabus_generator import SyllabusGenerator, initialize_course_from_syllabus

logger = logging.getLogger(__name__)

# ---------- helper functions ----------
def get_conversation_context(state: dict) -> str:
    parts = []
    if state.get("topic"): parts.append(f"Topic: {state['topic']}")
    if state.get("difficulty"): parts.append(f"Difficulty: {state['difficulty']}")
    if state.get("duration"): parts.append(f"Duration: {state['duration']}")
    if state.get("learner_type"): parts.append(f"Learner type: {state['learner_type']}")
    if state.get("extra_info"): parts.append(f"Additional info: {state['extra_info']}")
    return " | ".join(parts) if parts else "Starting conversation"

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

DURATION_PRESETS = {
    "weekend": "2 days (weekend sprint)",
    "couple of weeks": "2 weeks",
    "few weeks": "3 weeks",
    "couple of months": "2 months",
    "few months": "3 months",
}

def parse_duration(user_text: str) -> dict:
    """
    Parse a wide range of duration formats into a canonical structure + phrase.
    Returns a dict:
      {
        "ok": bool,
        "canonical": str,          # e.g. "4 weeks", "1 hour/day for 4 weeks"
        "assumption_note": str,    # e.g. 'Interpreted "2" as 2 weeks.'
        # if ambiguous bare time like "3 hours":
        "ambiguous_time_only": {"qty": "3", "unit": "hours"} | None
      }
    """
    t = user_text.strip().lower()
    t = re.sub(r"\s+", " ", t)

    # natural language presets
    for k, v in DURATION_PRESETS.items():
        if k in t:
            return {"ok": True, "canonical": v, "assumption_note": f'Mapped "{k}" → {v}.', "ambiguous_time_only": None}

    # explicit "total" (e.g., "3 hours total", "90 min total")
    m_total = re.search(r"\b(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minutes)\b.*\btotal\b", t)
    if m_total:
        qty = m_total.group(1)
        unit = m_total.group(2)
        unit_norm = "hours" if unit.startswith("h") else "min"
        return {"ok": True, "canonical": f"{qty} {unit_norm} total", "assumption_note": "", "ambiguous_time_only": None}

    # common total-span forms like "2 weeks", "2 wk", "2w", "2 months", "3 mo", "10 days"
    m_span = re.search(r"\b(\d+(?:\.\d+)?)\s*(w(?:eeks?)?|wk?s?|m(?:onths?)?|mo?s?|d(?:ays?)?)\b", t)
    if m_span:
        num = m_span.group(1)
        unit = m_span.group(2)
        unit_norm = (
            "weeks" if unit.startswith(("w", "wk")) else
            "months" if unit.startswith(("m", "mo")) else
            "days"
        )
        return {"ok": True, "canonical": f"{num} {unit_norm}", "assumption_note": "", "ambiguous_time_only": None}

    # cadence + total, e.g., "1h/day for 4 weeks", "30min weekly for 2 months"
    per = re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minutes)\s*/?\s*(day|daily|week|weekly)", t)
    total = re.search(r"\bfor\s+(\d+(?:\.\d+)?)\s*(w(?:eeks?)?|wk?s?|m(?:onths?)?|mo?s?|d(?:ays?)?)\b", t)
    if per and total:
        qty = per.group(1); unit = per.group(2); cadence = per.group(3)
        total_n = total.group(1); total_u = total.group(2)
        # normalize units
        if unit.startswith("h"):
            per_part = f"{qty} hour/day" if cadence.startswith("d") else f"{qty} hour/week"
        else:
            per_part = f"{qty} min/day" if cadence.startswith("d") else f"{qty} min/week"
        total_unit = (
            "weeks" if total_u.startswith(("w", "wk")) else
            "months" if total_u.startswith(("m", "mo")) else
            "days"
        )
        return {"ok": True, "canonical": f"{per_part} for {total_n} {total_unit}", "assumption_note": "", "ambiguous_time_only": None}

    # cadence only (no total span): assume 4 weeks
    per_only = re.search(r"\b(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minutes)\b\s*/?\s*(day|daily|week|weekly)\b", t)
    if per_only:
        qty = per_only.group(1); unit = per_only.group(2); cadence = per_only.group(3)
        if unit.startswith("h"):
            per_part = f"{qty} hour/day" if cadence.startswith("d") else f"{qty} hour/week"
        else:
            per_part = f"{qty} min/day" if cadence.startswith("d") else f"{qty} min/week"
        return {"ok": True, "canonical": f"{per_part} for 4 weeks", "assumption_note": "Assumed a 4-week plan.", "ambiguous_time_only": None}

    # bare number like "2" — assume weeks
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return {"ok": True, "canonical": f"{t} weeks", "assumption_note": f'Interpreted "{t}" as weeks.', "ambiguous_time_only": None}

    # word-numbers like "two weeks"
    WORD_NUMS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    for word, val in WORD_NUMS.items():
        if re.search(rf"\b{word}\b.*\bweek", t):
            return {"ok": True, "canonical": f"{val} weeks", "assumption_note": "", "ambiguous_time_only": None}

    # bare hour/min (AMBIGUOUS): "3 hours", "30 min"
    bare_time = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minutes)", t)
    if bare_time:
        qty = bare_time.group(1)
        unit_norm = "hours" if bare_time.group(2).startswith("h") else "min"
        return {
            "ok": False,
            "canonical": "",
            "assumption_note": "",
            "ambiguous_time_only": {"qty": qty, "unit": unit_norm}
        }

    # daily phrasing without numbers: treat as unclear
    if "daily" in t or "per day" in t:
        # try salvage: "daily" with implied 1 hour
        return {"ok": False, "canonical": "", "assumption_note": "", "ambiguous_time_only": None}

    # unrecognized
    return {"ok": False, "canonical": "", "assumption_note": "", "ambiguous_time_only": None}


# ---------- main state machine ----------
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
            - "Math" → YES
            - "Language learning" → YES
            
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
                
                Format: '{topic}' is quite broad. I can suggest specific areas like subtopic 1, subtopic 2, or subtopic 3, or we can proceed with the general topic. What would you prefer?
                
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
            parsed = parse_duration(user_input)

            if not parsed["ok"]:
                # Ask for a clearer input, with examples tailored to your UX
                state["step"] = "duration"
                return state, {
                    "bot": "Could you specify your time commitment? Examples:\n• 4 weeks\n• 1 hour/day for 4 weeks\n• Weekend sprint\n• 2 months"
            }

            state["duration"] = parsed["canonical"]
            # If we made assumptions, gently confirm (then proceed to learning_style)
            if parsed["assumption_note"]:
                state["pending_duration"] = parsed["canonical"]
                state["step"] = "duration_confirmation"
                return state, {
                    "bot": f"{parsed['assumption_note']} Use **{parsed['canonical']}**?\n(Reply 'yes' to keep, or type a different duration.)"
                }

            # normal path (already clear)
            state["step"] = "learning_style"
            return state, {"bot": "Choose your learning style:\nA) Videos and visual content\nB) Reading and text\nC) Hands-on projects\nD) Mix of all"}

        
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
                # FREE-FORM MODIFICATION: regenerate now using this hint
                state["modification_hint"] = user_input.strip()
                syllabus = generate_course_plan(state, state["modification_hint"])
                state["step"] = "course_generated"
                return state, {
                    "bot": "Updated your course plan with your requested changes.",
                    "syllabus": syllabus,
                    "course_ready": True
                }
            
        # Course generated
        elif current_step == "course_generated" and user_input:
            user_lower = user_input.lower().strip()
            # If user types only 'regenerate', rerun with last known hint (if any)
            if user_lower in ["regenerate", "regen", "regenerate syllabus", "regenerate the syllabus"]:
                syllabus = generate_course_plan(state, state.get("modification_hint"))
                return state, {
                    "bot": "Regenerated your course plan.",
                    "syllabus": syllabus,
                    "course_ready": True
                }
            # Otherwise treat it as a new modification hint
            else:
                state["modification_hint"] = user_input
                syllabus = generate_course_plan(state, state["modification_hint"])
                return state, {
                    "bot": "Applied your changes and regenerated the course plan.",
                    "syllabus": syllabus,
                    "course_ready": True
                }
        
        # Fallback
        else:
            return state, {"bot": "Could you please rephrase that?"}
            
    except Exception as e:
        logger.error(f"Error in chatbot_step: {str(e)}")
        return state, {"bot": "Sorry, I encountered an error. Could you try again?"}


def generate_course_plan(state: dict, modification_hint: Optional[str] = None) -> str:
    """Generate a comprehensive course plan using Claude, optionally applying a modification hint."""
    hint_block = ""
    if modification_hint:
        hint_block = f"""

        🔧 **Apply the following requested adjustments strictly**:
{modification_hint}
- Reflect these changes consistently in overview, weekly breakdown, activities, assessments, resources, and final project.
- If there is any conflict with prior settings (topic/level/duration/style/goals), prefer the user's requested adjustments.
"""
    
    prompt = f"""You are Sandwich, an expert AI learning assistant. Create a detailed, personalized course syllabus based on this information:

📚 **Course Details:**
- **Topic:** {state.get('topic', 'General')}
- **Difficulty Level:** {state.get('difficulty', 'Not specified')}
- **Time Commitment:** {state.get('duration', 'Flexible')}
- **Learning Style:** {state.get('learner_type', 'Mixed approach')}
- **Specific Focus:** {state.get('extra_info', 'Comprehensive overview')}
{hint_block}

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

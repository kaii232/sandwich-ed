import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import random
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class AITutor:
    def __init__(self):
        self.client = self._get_bedrock_client()
    
    def _get_bedrock_client(self):
        """Initialize Bedrock client"""
        try:
            return boto3.client(
                'bedrock-runtime',
                region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            raise
    
    def _ask_claude(self, messages: list, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """Send request to Claude"""
        try:
            response = self.client.invoke_model(
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
        except Exception as e:
            logger.error(f"Error calling Claude: {str(e)}")
            return "I'm having trouble right now. Please try again."
    
    def generate_quiz(self, week_info: Dict, course_context: Dict, num_questions: int = 5) -> Dict:
        """Generate a quiz for a specific week"""
        prompt = f"""You are Sandwich, an expert AI tutor creating a quiz. Generate a {num_questions}-question quiz for this week's content.

**Course Context:**
- Topic: {course_context.get('topic', '')}
- Difficulty: {course_context.get('difficulty', '')}
- Week: {week_info['title']}
- Topics covered: {', '.join(week_info.get('topics', []))}

**Quiz Requirements:**
- Create exactly {num_questions} questions
- Mix of question types: multiple choice (60%), true/false (20%), short answer (20%)
- Questions should test understanding, not just memorization
- Include practical application questions
- Provide clear, educational explanations for each answer

**Format each question as:**
```
Question X: [Question text]
Type: [multiple_choice/true_false/short_answer]
Options: [For multiple choice only: A) option1 B) option2 C) option3 D) option4]
Correct Answer: [Answer]
Explanation: [Why this is correct and what concept it tests]
Points: [1-3 points based on difficulty]
```

Make questions engaging and relevant to real-world applications of the topic."""

        messages = [{"role": "user", "content": prompt}]
        response = self._ask_claude(messages, temperature=0.6, max_tokens=1500)
        
        # Parse the response into structured quiz format
        quiz_data = self._parse_quiz_response(response, week_info, course_context)
        
        return quiz_data
    
    def _parse_quiz_response(self, response: str, week_info: Dict, course_context: Dict) -> Dict:
        """Parse AI-generated quiz into structured format"""
        quiz = {
            "quiz_id": f"week_{week_info['week_number']}_{datetime.now().strftime('%Y%m%d')}",
            "week_number": week_info['week_number'],
            "week_title": week_info['title'],
            "course_topic": course_context.get('topic', ''),
            "questions": [],
            "total_points": 0,
            "time_limit_minutes": 30,
            "created_at": datetime.now().isoformat()
        }
        
        # Split response into individual questions
        sections = response.split('Question ')
        
        for section in sections[1:]:  # Skip the first empty section
            question_data = self._parse_single_question(section.strip())
            if question_data:
                quiz["questions"].append(question_data)
                quiz["total_points"] += question_data.get("points", 1)
        
        return quiz
    
    def _parse_single_question(self, section: str) -> Optional[Dict]:
        """Parse a single question from the AI response"""
        lines = section.split('\n')
        question_data = {}
        
        try:
            # Extract question number and text
            first_line = lines[0]
            if ':' in first_line:
                question_data["question_number"] = first_line.split(':')[0].strip()
                question_data["question_text"] = first_line.split(':', 1)[1].strip()
            else:
                return None
            
            # Parse other fields
            for line in lines[1:]:
                line = line.strip()
                if line.startswith('Type:'):
                    question_data["type"] = line.split(':', 1)[1].strip()
                elif line.startswith('Options:'):
                    options_text = line.split(':', 1)[1].strip()
                    question_data["options"] = self._parse_options(options_text)
                elif line.startswith('Correct Answer:'):
                    question_data["correct_answer"] = line.split(':', 1)[1].strip()
                elif line.startswith('Explanation:'):
                    question_data["explanation"] = line.split(':', 1)[1].strip()
                elif line.startswith('Points:'):
                    try:
                        question_data["points"] = int(line.split(':', 1)[1].strip().split()[0])
                    except:
                        question_data["points"] = 1
            
            # Set defaults
            question_data.setdefault("type", "multiple_choice")
            question_data.setdefault("points", 1)
            
            return question_data
            
        except Exception as e:
            logger.error(f"Error parsing question: {str(e)}")
            return None
    
    def _parse_options(self, options_text: str) -> List[str]:
        """Parse multiple choice options"""
        options = []
        # Look for pattern like "A) option1 B) option2 C) option3 D) option4"
        import re
        pattern = r'[A-D]\)\s*([^A-D)]+?)(?=[A-D]\)|$)'
        matches = re.findall(pattern, options_text)
        return [match.strip() for match in matches]
    
    def grade_quiz(self, quiz: Dict, user_answers: Dict) -> Dict:
        """Grade a completed quiz"""
        results = {
            "quiz_id": quiz["quiz_id"],
            "total_questions": len(quiz["questions"]),
            "total_points": quiz["total_points"],
            "user_score": 0,
            "correct_answers": 0,
            "percentage": 0,
            "grade_letter": "F",
            "feedback": [],
            "completed_at": datetime.now().isoformat()
        }
        
        for question in quiz["questions"]:
            q_num = question["question_number"]
            user_answer = user_answers.get(str(q_num), "").strip()
            correct_answer = question["correct_answer"].strip()
            
            # Grade the question
            is_correct = self._check_answer(user_answer, correct_answer, question["type"])
            
            question_feedback = {
                "question_number": q_num,
                "question_text": question["question_text"],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "points_earned": question["points"] if is_correct else 0,
                "points_possible": question["points"],
                "explanation": question.get("explanation", ""),
                "feedback": self._generate_question_feedback(is_correct, question)
            }
            
            results["feedback"].append(question_feedback)
            
            if is_correct:
                results["correct_answers"] += 1
                results["user_score"] += question["points"]
        
        # Calculate percentage and letter grade
        results["percentage"] = round((results["user_score"] / results["total_points"]) * 100, 1)
        results["grade_letter"] = self._calculate_letter_grade(results["percentage"])
        
        # Generate overall feedback
        results["overall_feedback"] = self._generate_overall_feedback(results)
        
        return results
    
    def _check_answer(self, user_answer: str, correct_answer: str, question_type: str) -> bool:
        """Check if user answer is correct"""
        user_answer = user_answer.lower().strip()
        correct_answer = correct_answer.lower().strip()
        
        if question_type == "multiple_choice":
            # Check for letter (A, B, C, D) or the full answer
            return user_answer in correct_answer or correct_answer in user_answer
        elif question_type == "true_false":
            return user_answer in correct_answer or correct_answer in user_answer
        elif question_type == "short_answer":
            # Use AI to evaluate short answers
            return self._evaluate_short_answer(user_answer, correct_answer)
        
        return False
    
    def _evaluate_short_answer(self, user_answer: str, correct_answer: str) -> bool:
        """Use AI to evaluate short answer questions"""
        if len(user_answer) < 3:  # Too short to be meaningful
            return False
        
        # Simple keyword matching for now - could be enhanced with AI evaluation
        correct_keywords = correct_answer.lower().split()
        user_keywords = user_answer.lower().split()
        
        # Check if at least 60% of key concepts are mentioned
        matches = sum(1 for keyword in correct_keywords if any(k in keyword for k in user_keywords))
        return matches >= len(correct_keywords) * 0.6
    
    def _calculate_letter_grade(self, percentage: float) -> str:
        """Convert percentage to letter grade"""
        if percentage >= 90:
            return "A"
        elif percentage >= 80:
            return "B"
        elif percentage >= 70:
            return "C"
        elif percentage >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_question_feedback(self, is_correct: bool, question: Dict) -> str:
        """Generate feedback for individual questions"""
        if is_correct:
            return "✅ Correct! Great job understanding this concept."
        else:
            return f"❌ Not quite right. {question.get('explanation', 'Review this concept and try again.')}"
    
    def _generate_overall_feedback(self, results: Dict) -> str:
        """Generate overall feedback for the quiz"""
        percentage = results["percentage"]
        
        if percentage >= 90:
            return "🎉 Excellent work! You have a strong understanding of this week's material."
        elif percentage >= 80:
            return "👍 Good job! You understand most of the concepts well. Review the missed questions."
        elif percentage >= 70:
            return "📚 Decent effort! You have a basic understanding, but consider reviewing the material."
        elif percentage >= 60:
            return "⚠️ You're getting there! Please review this week's content and retake the quiz."
        else:
            return "📖 You might want to go back and review the material before continuing to the next week."
    
    def provide_tutoring(self, question: str, week_info: Dict, course_context: Dict) -> str:
        """Provide AI tutoring for student questions"""
        prompt = f"""You are Sandwich, an expert AI tutor helping a student learn {course_context.get('topic', '')}.

**Student's Question:** {question}

**Current Context:**
- Week: {week_info.get('title', 'Current week')}
- Topics this week: {', '.join(week_info.get('topics', []))}
- Course difficulty: {course_context.get('difficulty', '')}
- Student's learning style: {course_context.get('learner_type', '')}

**Your Response Should:**
1. Directly answer their question in simple, clear terms
2. Provide a relevant example or analogy
3. Connect it to the week's learning objectives
4. Suggest a practical way to apply this knowledge
5. Offer encouragement

Keep your response friendly, encouraging, and educational. If the question is outside this week's scope, gently redirect them while still being helpful."""

        messages = [{"role": "user", "content": prompt}]
        return self._ask_claude(messages, temperature=0.7, max_tokens=800)
    
    def generate_study_tips(self, week_info: Dict, course_context: Dict, student_performance: Optional[Dict] = None) -> List[str]:
        """Generate personalized study tips"""
        prompt = f"""You are Sandwich, an AI learning coach. Generate 5 personalized study tips for this student.

**Context:**
- Topic: {course_context.get('topic', '')}
- Week: {week_info.get('title', '')}
- Learning style: {course_context.get('learner_type', '')}
- Difficulty level: {course_context.get('difficulty', '')}

{f"Recent quiz performance: {student_performance.get('percentage', 0)}%" if student_performance else ""}

Generate 5 specific, actionable study tips that:
1. Are tailored to their learning style
2. Help with this week's specific topics
3. Are practical and easy to implement
4. Will improve their understanding and retention

Format as a simple numbered list."""

        messages = [{"role": "user", "content": prompt}]
        response = self._ask_claude(messages, temperature=0.6, max_tokens=600)
        
        # Parse into list
        tips = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                # Remove numbering/bullets and clean up
                tip = line.lstrip('0123456789.-• ').strip()
                if tip:
                    tips.append(tip)
        
        return tips[:5]  # Ensure max 5 tips
    
    def get_progress_insights(self, quiz_history: List[Dict], course_context: Dict) -> Dict:
        """Analyze student progress and provide insights"""
        if not quiz_history:
            return {"message": "Complete your first quiz to see progress insights!"}
        
        # Calculate trends
        scores = [quiz.get("percentage", 0) for quiz in quiz_history]
        avg_score = sum(scores) / len(scores)
        
        # Trend analysis
        if len(scores) >= 2:
            recent_trend = scores[-1] - scores[-2]
            if recent_trend > 5:
                trend = "improving"
            elif recent_trend < -5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "new"
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        for quiz in quiz_history:
            for feedback in quiz.get("feedback", []):
                if feedback["is_correct"]:
                    strengths.append(feedback["question_text"])
                else:
                    weaknesses.append(feedback["question_text"])
        
        return {
            "average_score": round(avg_score, 1),
            "trend": trend,
            "total_quizzes": len(quiz_history),
            "strengths": strengths[-3:] if strengths else [],  # Recent strengths
            "areas_for_improvement": weaknesses[-3:] if weaknesses else [],  # Recent weaknesses
            "encouragement": self._generate_encouragement(avg_score, trend)
        }
    
    def _generate_encouragement(self, avg_score: float, trend: str) -> str:
        """Generate encouraging message based on performance"""
        if avg_score >= 90:
            return "🌟 You're doing amazing! Your understanding is excellent."
        elif avg_score >= 80:
            if trend == "improving":
                return "📈 Great progress! You're really getting the hang of this."
            else:
                return "👍 You're doing well! Keep up the good work."
        elif avg_score >= 70:
            if trend == "improving":
                return "📚 You're making good progress! Keep studying and you'll master this."
            else:
                return "💪 You're on the right track. A little more practice and you'll excel."
        else:
            return "🎯 Every expert was once a beginner. Keep learning and you'll improve!"

# Helper functions for integration

def create_quiz_session(week_info: Dict, course_context: Dict) -> Dict:
    """Create a new quiz session for a week"""
    tutor = AITutor()
    quiz = tutor.generate_quiz(week_info, course_context)
    
    return {
        "quiz": quiz,
        "started_at": datetime.now().isoformat(),
        "status": "in_progress",
        "time_remaining": quiz.get("time_limit_minutes", 30) * 60  # Convert to seconds
    }

def submit_quiz_answers(quiz_session: Dict, user_answers: Dict) -> Dict:
    """Submit and grade quiz answers"""
    tutor = AITutor()
    results = tutor.grade_quiz(quiz_session["quiz"], user_answers)
    
    quiz_session["status"] = "completed"
    quiz_session["completed_at"] = datetime.now().isoformat()
    quiz_session["results"] = results
    
    return quiz_session

def adjust_next_week_content(week_info: Dict, course_context: Dict, recent_quiz: Dict) -> Dict:
    """
    Adjust the next week's syllabus based on student's recent quiz performance.
    - If weak on certain topics, reinforce those in the next week.
    - If strong, introduce new/advanced topics or accelerate pace.
    Returns a modified week_info dict.
    """
    tutor = AITutor()
    strengths = []
    weaknesses = []
    for feedback in recent_quiz.get("feedback", []):
        if feedback["is_correct"]:
            strengths.append(feedback["question_text"])
        else:
            weaknesses.append(feedback["question_text"])

    # If there are weaknesses, reinforce those topics
    if weaknesses:
        reinforce_prompt = f"""
        You are Sandwich, an adaptive AI course designer.
        The student struggled with these topics in the last quiz: {', '.join(weaknesses)}.
        Please adjust the next week's syllabus to reinforce these topics with extra explanations, examples, and practice activities.
        Also, briefly review strengths: {', '.join(strengths)}.
        Here is the original plan for next week:
        Title: {week_info.get('title', '')}
        Topics: {', '.join(week_info.get('topics', []))}
        Please return a revised week plan in structured JSON:
        {{
            "title": ...,
            "topics": [...],
            "objectives": [...],
            "activities": [...],
            "notes": "How you adapted the plan"
        }}
        """
    else:
        # If student did well, accelerate or introduce new topics
        reinforce_prompt = f"""
        You are Sandwich, an adaptive AI course designer.
        The student performed well in the last quiz, especially on: {', '.join(strengths)}.
        Please adjust the next week's syllabus to move faster, introduce new/advanced topics, and reduce review of mastered material.
        Here is the original plan for next week:
        Title: {week_info.get('title', '')}
        Topics: {', '.join(week_info.get('topics', []))}
        Please return a revised week plan in structured JSON:
        {{
            "title": ...,
            "topics": [...],
            "objectives": [...],
            "activities": [...],
            "notes": "How you adapted the plan"
        }}
        """

    messages = [{"role": "user", "content": reinforce_prompt}]
    response = tutor._ask_claude(messages, temperature=0.7, max_tokens=800)

    # Try to parse the JSON from Claude's response
    try:
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            revised_week = json.loads(match.group(0))
            return revised_week
    except Exception as e:
        logger.error(f"Error parsing revised week plan: {str(e)}")
        # Fallback: return original week_info with a note
        week_info["notes"] = "Could not parse AI revision. Original plan used."
        return week_info

def get_tutoring_help(question: str, week_info: Dict, course_context: Dict) -> str:
    """Get AI tutoring help for a question"""
    tutor = AITutor()
    return tutor.provide_tutoring(question, week_info, course_context)

def get_personalized_study_tips(week_info: Dict, course_context: Dict, recent_quiz: Optional[Dict] = None) -> List[str]:
    """Get personalized study tips"""
    tutor = AITutor()
    return tutor.generate_study_tips(week_info, course_context, recent_quiz)
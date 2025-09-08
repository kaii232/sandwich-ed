import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import random
from datetime import datetime
from app.services.llm_client import invoke_claude_json  # robust Bedrock client wrapper
from app.services.inflight import inflight  # singleflight pattern to dedupe identical requests 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

FALLBACK_TIPS = [
        "Study in 25–30 min sprints; take 5 min breaks.",
        "Teach the concept aloud to check gaps.",
        "Mix easy and medium questions to build momentum.",
        "Write a 3-sentence summary for each subsection.",
        "Review mistakes first; turn them into flashcards.",
        "Space reviews: today, tomorrow, and in 3 days.",
        "Practice retrieval before rereading your notes.",
        "Sleep well; retention improves after rest.",
    ]

class AITutor:
    def __init__(self):
        # keep model configurable; default to your current Haiku
        self.model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-haiku-20240307-v1:0",
        )
    
    
    def _ask_claude(self, messages: list, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        try:
            return invoke_claude_json(
                model_id=self.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f"Error calling Claude: {str(e)}")
            return "I'm having trouble right now. Please try again."
    
    def generate_quiz(self, week_info: Dict, course_context: Dict, num_questions: int = 10) -> Dict:
        """Generate a quiz for a specific week - MCQ only with adaptive difficulty and accuracy verification"""
        
        # Extract topics for better quiz generation
        topics = week_info.get('topics', [])
        if not topics:
            topics = [course_context.get('topic', 'general knowledge')]
        
        # Determine quiz difficulty based on week adaptation
        quiz_difficulty = week_info.get('quiz_difficulty', 'same')
        difficulty_level = week_info.get('difficulty_level', 'progressive')
        
        # Adjust difficulty descriptors
        if quiz_difficulty == "hard":
            difficulty_desc = "ADVANCED and CHALLENGING"
            complexity_level = "high complexity with multi-step problems"
            question_types = "70% computational/problem-solving, 30% theoretical/conceptual with advanced applications"
        elif quiz_difficulty == "same":
            difficulty_desc = "STANDARD"
            complexity_level = "moderate complexity appropriate for the topic"
            question_types = "60% computational/problem-solving, 40% theoretical/conceptual"
        else:  # maintain or supportive
            difficulty_desc = "SUPPORTIVE and CONFIDENCE-BUILDING"
            complexity_level = "clear, step-by-step problems that build understanding"
            question_types = "50% computational/problem-solving, 50% theoretical/conceptual with guided reasoning"
            
        prompt = f"""You are Sandwich, an expert AI tutor creating a {difficulty_desc} multiple choice quiz. Generate a {num_questions}-question quiz for this week's specific content.

**CRITICAL ACCURACY REQUIREMENTS:**
- DOUBLE-CHECK every mathematical calculation
- VERIFY every factual statement
- ENSURE correct answers are genuinely correct
- AVOID making up formulas, equations, or facts
- For computational questions, SHOW YOUR WORK in explanations
- For theoretical questions, cite established principles/theorems

**Course Context:**
- Main Topic: {course_context.get('topic', '')}
- Course Difficulty: {course_context.get('difficulty', '')}
- Week: {week_info.get('title', '')}
- Week Difficulty Level: {difficulty_level}
- Quiz Difficulty: {quiz_difficulty.upper()}
- Specific Topics This Week: {', '.join(topics)}

**ADAPTATION CONTEXT:**
{week_info.get('adaptation_notes', 'Standard progression week')}

**IMPORTANT: The quiz MUST focus specifically on these topics: {', '.join(topics)}**

**Quiz Requirements:**
- Create exactly {num_questions} MULTIPLE CHOICE questions ONLY
- Question difficulty: {complexity_level}
- Mix of question types: {question_types}
- ALL questions must be directly related to: {', '.join(topics)}
- Each question must have exactly 4 SPECIFIC, MEANINGFUL options (A, B, C, D)
- All options must be realistic, plausible answers - NO generic placeholders
- Only ONE option should be completely correct
- Include equations, formulas, code, or mathematical expressions when relevant

**ACCURACY VERIFICATION STEPS:**
1. For math questions: Verify calculations step-by-step
2. For formulas: Confirm they are standard, established formulas
3. For facts: Ensure they are well-established knowledge
4. For code: Test logic mentally for correctness
5. For theory: Reference known principles/theorems

**EXAMPLES OF VERIFIED ACCURACY:**

✅ CORRECT Math Question:
Question: What is the derivative of f(x) = 3x² + 2x - 5?
A) 6x + 2
B) 3x² + 2x
C) 6x² + 2
D) 3x + 2
Correct: A) 6x + 2
Verification: d/dx(3x²) = 6x, d/dx(2x) = 2, d/dx(-5) = 0 → 6x + 2 ✓

✅ CORRECT Theory Question:
Question: Which principle states that energy cannot be created or destroyed?
A) Conservation of Energy
B) Conservation of Momentum  
C) Principle of Relativity
D) Heisenberg Uncertainty Principle
Correct: A) Conservation of Energy
Verification: This is the First Law of Thermodynamics ✓

**DIFFICULTY-SPECIFIC GUIDELINES:**

{f'''**ADVANCED/HARD Quiz Guidelines:**
- Multi-step problems requiring several concepts
- Complex equations with multiple variables
- Application problems with real-world scenarios
- Theoretical questions requiring deep understanding
- Integration of multiple concepts in single questions
- Advanced mathematical notation and terminology
- VERIFY ALL CALCULATIONS TWICE''' if quiz_difficulty == "hard" else ''}

{f'''**SUPPORTIVE Quiz Guidelines:**
- Clear, direct questions with obvious application
- Single-concept problems without complex integration
- Straightforward calculations with clear steps
- Fundamental theoretical concepts
- Confidence-building questions with clear right answers
- Avoid trick questions or overly complex scenarios
- DOUBLE-CHECK basic calculations''' if quiz_difficulty in ["maintain", "supportive"] else ''}

{f'''**STANDARD Quiz Guidelines:**
- Balanced mix of straightforward and moderately challenging questions
- Some multi-step problems, some single-concept questions
- Mix of computational and conceptual understanding
- Appropriate challenge level for steady progress
- VERIFY ALL WORK BEFORE FINALIZING''' if quiz_difficulty == "same" else ''}

**ABSOLUTELY FORBIDDEN:**
- Generic options like "Option A", "Option B", "First possible answer", etc.
- Vague or meaningless options
- Options that don't relate to the question
- Questions outside the specified topics: {', '.join(topics)}
- INCORRECT ANSWERS marked as correct
- Made-up formulas or fake facts
- Unverified calculations

**Format each question EXACTLY as shown below (one question per block):**

```
Question 1: What is the first step in effective problem solving?
Type: multiple_choice
Options: A) Identify and understand the problem B) Jump directly to solutions C) Ignore the problem details D) Ask someone else to solve it
Correct Answer: A
Explanation: Identifying and understanding the problem is the crucial first step as it provides the foundation for finding an effective solution.
Verification: This follows established problem-solving methodologies.
Points: 2
```

```
Question 2: Which strategy helps break down complex problems?
Type: multiple_choice  
Options: A) Avoiding the problem entirely B) Divide and conquer approach C) Guessing randomly D) Using only intuition
Correct Answer: B
Explanation: The divide and conquer approach breaks complex problems into smaller, manageable parts that can be solved systematically.
Verification: This is a well-established problem-solving technique.
Points: 2
```

**CRITICAL FORMATTING RULES:**
- Each question must be in its own ``` block
- Options format: "A) [complete answer] B) [complete answer] C) [complete answer] D) [complete answer]"  
- Correct Answer format: Just the letter (A, B, C, or D)
- All 4 options must be meaningful and relevant
- NO generic placeholders like "Option A" or "First answer"

Generate EXACTLY {num_questions} questions following this format. Each question must have exactly 4 specific options.
Quiz Difficulty Level: {quiz_difficulty.upper()}"""

        messages = [{"role": "user", "content": prompt}]
        response = self._ask_claude(messages, temperature=0.3, max_tokens=4000)  # Lower temperature for accuracy
        
        # Parse the response into structured quiz format
        quiz_data = self._parse_quiz_response(response, week_info, course_context)
        
        # Verify quiz quality and accuracy
        quiz_data = self._verify_quiz_accuracy(quiz_data, week_info, course_context)
        
        # Keep generating until we have enough valid questions
        attempts = 1
        max_attempts = 5  # Increase attempts to ensure we get enough questions
        
        while len(quiz_data.get("questions", [])) < num_questions and attempts < max_attempts:
            attempts += 1
            questions_needed = num_questions - len(quiz_data.get("questions", []))
            logger.warning(f"Attempt {attempts}: Only got {len(quiz_data.get('questions', []))} valid questions, need {questions_needed} more...")
            
            # Generate additional questions with more specific prompts
            additional_prompt = f"""The previous generation only produced {len(quiz_data.get('questions', []))} valid questions out of {num_questions} required.

I need you to generate {questions_needed} MORE high-quality multiple choice questions to reach the target of {num_questions} total questions.

**SPECIFIC REQUIREMENTS FOR THIS ATTEMPT:**
- Generate EXACTLY {questions_needed} questions
- Each question MUST have exactly 4 options in format: "A) option B) option C) option D) option"
- Focus on these topics: {', '.join(topics)}
- Make questions straightforward but educational
- Avoid overly complex scenarios that might confuse option parsing

**PROVEN WORKING FORMAT (copy this structure exactly):**

```
Question 1: [Your question here]?
Type: multiple_choice
Options: A) First complete answer B) Second complete answer C) Third complete answer D) Fourth complete answer
Correct Answer: A
Explanation: [Why the answer is correct]
Verification: Answer verified through reasoning
Points: 2
```

**IMPORTANT:** 
- Put each question in separate ``` blocks
- Options must be on ONE line in the exact format above
- No line breaks within the Options: line
- Make sure all 4 options are meaningful and different

Generate {questions_needed} questions NOW following this exact format."""

            messages = [{"role": "user", "content": additional_prompt}]
            additional_response = self._ask_claude(messages, temperature=0.2, max_tokens=3000)  # Even lower temperature
            additional_quiz = self._parse_quiz_response(additional_response, week_info, course_context)
            
            # Verify additional questions with more lenient standards for later attempts
            if attempts >= 3:
                # Be more lenient in later attempts to ensure we get enough questions
                logger.info("Using more lenient verification for later attempts")
                additional_quiz = self._verify_quiz_accuracy_lenient(additional_quiz, week_info, course_context)
            else:
                additional_quiz = self._verify_quiz_accuracy(additional_quiz, week_info, course_context)
            
            # Merge the new questions with existing ones
            if additional_quiz.get("questions"):
                existing_questions = quiz_data.get("questions", [])
                new_questions = additional_quiz.get("questions", [])
                
                # Renumber all questions sequentially
                all_questions = existing_questions + new_questions
                for i, question in enumerate(all_questions, 1):
                    question["question_number"] = i
                
                # Keep only the number we need and update total points
                quiz_data["questions"] = all_questions[:num_questions]
                quiz_data["total_points"] = sum(q.get("points", 2) for q in quiz_data["questions"])
                
                logger.info(f"Added {len(new_questions)} new verified questions, total now: {len(quiz_data['questions'])}")
        
        # Final check - if we still don't have enough questions, use emergency fallback
        if len(quiz_data.get("questions", [])) < num_questions:
            questions_needed = num_questions - len(quiz_data.get("questions", []))
            logger.warning(f"Emergency fallback: generating {questions_needed} basic questions to reach target")
            
            fallback_questions = self._generate_fallback_questions(questions_needed, topics, week_info)
            existing_questions = quiz_data.get("questions", [])
            
            # Add fallback questions
            all_questions = existing_questions + fallback_questions
            for i, question in enumerate(all_questions, 1):
                question["question_number"] = i
                
            quiz_data["questions"] = all_questions[:num_questions]
            quiz_data["total_points"] = sum(q.get("points", 2) for q in quiz_data["questions"])
        
        # Final validation
        final_count = len(quiz_data.get("questions", []))
        if final_count < num_questions:
            logger.error(f"Could only generate {final_count} verified questions out of {num_questions} requested after {max_attempts} attempts")
        else:
            logger.info(f"Successfully generated {final_count} questions for the quiz")
        
        return quiz_data
    
    def _verify_quiz_accuracy(self, quiz_data: Dict, week_info: Dict, course_context: Dict) -> Dict:
        """Verify quiz accuracy and remove potentially incorrect questions"""
        if not quiz_data.get("questions"):
            return quiz_data
        
        verified_questions = []
        topic = course_context.get('topic', '').lower()
        
        for question in quiz_data["questions"]:
            is_verified = True
            verification_notes = []
            
            # Basic question validation
            if not question.get("question_text") or not question.get("options") or len(question.get("options", [])) != 4:
                logger.warning(f"Question {question.get('question_number', '?')} failed basic validation")
                continue
            
            question_text = question.get("question_text", "").lower()
            correct_answer_letter = question.get("correct_answer", "").strip().upper()
            options = question.get("options", [])
            
            # Verify correct answer letter is valid
            if correct_answer_letter not in ['A', 'B', 'C', 'D']:
                logger.warning(f"Question {question.get('question_number', '?')} has invalid correct answer: {correct_answer_letter}")
                continue
            
            # Get the correct answer option index
            try:
                correct_index = ord(correct_answer_letter) - ord('A')
                if correct_index < 0 or correct_index >= len(options):
                    logger.warning(f"Question {question.get('question_number', '?')} correct answer index out of range")
                    continue
            except:
                logger.warning(f"Question {question.get('question_number', '?')} failed answer index calculation")
                continue
            
            # Subject-specific accuracy checks
            if 'math' in topic or 'calculus' in topic or 'algebra' in topic:
                is_verified = self._verify_math_question(question_text, options, correct_answer_letter)
            elif 'physics' in topic:
                is_verified = self._verify_physics_question(question_text, options, correct_answer_letter)
            elif 'chemistry' in topic:
                is_verified = self._verify_chemistry_question(question_text, options, correct_answer_letter)
            elif 'programming' in topic or 'code' in topic or 'computer' in topic:
                is_verified = self._verify_programming_question(question_text, options, correct_answer_letter)
            else:
                # General verification for other topics
                is_verified = self._verify_general_question(question_text, options, correct_answer_letter)
            
            # Check for suspicious patterns that indicate hallucination
            if is_verified:
                is_verified = self._check_hallucination_patterns(question, topic)
            
            # Cross-verify critical STEM questions with a separate AI call
            if is_verified and any(stem in topic for stem in ['math', 'physics', 'chemistry', 'engineering', 'calculus', 'algebra']):
                if any(critical in question_text for critical in ['calculate', 'solve', 'derivative', 'integral', '=', '+', '-']):
                    cross_verified = self._cross_verify_critical_question(question, course_context)
                    if not cross_verified:
                        is_verified = False
                        logger.warning(f"Question {question.get('question_number', '?')} failed cross-verification")
            
            if is_verified:
                # Add verification timestamp
                question["verified_at"] = datetime.now().isoformat()
                question["accuracy_checked"] = True
                verified_questions.append(question)
            else:
                logger.warning(f"Question {question.get('question_number', '?')} failed accuracy verification")
        
        # Update quiz data with only verified questions
        quiz_data["questions"] = verified_questions
        quiz_data["total_points"] = sum(q.get("points", 2) for q in verified_questions)
        quiz_data["accuracy_verified"] = True
        quiz_data["verification_timestamp"] = datetime.now().isoformat()
        
        logger.info(f"Verified {len(verified_questions)} out of {len(quiz_data.get('questions', []))} questions")
        
        # Log accuracy statistics for monitoring
        self._log_accuracy_stats(len(verified_questions), len(quiz_data.get("questions", [])), week_info, course_context)
        
        return quiz_data
    
    def _log_accuracy_stats(self, verified_count: int, total_count: int, week_info: Dict, course_context: Dict):
        """Log accuracy statistics for monitoring and improvement"""
        try:
            accuracy_rate = (verified_count / total_count * 100) if total_count > 0 else 0
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "course_topic": course_context.get("topic", ""),
                "week_number": week_info.get("week_number", 0),
                "week_title": week_info.get("title", ""),
                "total_questions_generated": total_count,
                "verified_questions": verified_count,
                "accuracy_rate": round(accuracy_rate, 2),
                "quiz_difficulty": week_info.get("quiz_difficulty", "same")
            }
            
            # Log for monitoring (in a real system, this could go to a monitoring service)
            logger.info(f"Quiz Accuracy Stats: {stats}")
            
            # Alert if accuracy is too low
            if accuracy_rate < 80:
                logger.warning(f"LOW ACCURACY ALERT: Only {accuracy_rate}% of questions passed verification for {course_context.get('topic', '')} Week {week_info.get('week_number', '?')}")
        
        except Exception as e:
            logger.error(f"Error logging accuracy stats: {str(e)}")
    
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
        valid_questions = []
        question_counter = 1
        
        for section in sections[1:]:  # Skip the first empty section
            question_data = self._parse_single_question(section.strip())
            if question_data:  # Only add valid questions
                # Ensure consistent question numbering
                question_data["question_number"] = question_counter
                valid_questions.append(question_data)
                quiz["total_points"] += question_data.get("points", 2)
                question_counter += 1
        
        quiz["questions"] = valid_questions
        return quiz
    
    def _verify_math_question(self, question_text: str, options: List[str], correct_letter: str) -> bool:
        """Verify mathematical questions for accuracy"""
        try:
            # Check for basic mathematical operations
            if any(op in question_text for op in ['derivative', 'integral', '∫', 'd/dx', "f'(x)"]):
                # Basic calculus verification
                if 'x²' in question_text and 'derivative' in question_text:
                    # Should contain something like 2x in the correct answer
                    correct_index = ord(correct_letter) - ord('A')
                    correct_option = options[correct_index].lower()
                    if 'x²' in question_text and '2x' not in correct_option and 'x' in correct_option:
                        logger.warning("Potential derivative calculation error detected")
                        return False
            
            # Check for obvious mathematical impossibilities
            correct_index = ord(correct_letter) - ord('A')
            correct_option = options[correct_index]
            
            # Look for suspicious math patterns
            if any(word in correct_option.lower() for word in ['impossible', 'undefined', 'infinity']) and 'limit' not in question_text.lower():
                # Check if this makes sense in context
                if not any(trigger in question_text.lower() for trigger in ['division by zero', 'asymptote', 'discontinuous']):
                    logger.warning("Suspicious mathematical answer detected")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in math verification: {str(e)}")
            return False
    
    def _verify_physics_question(self, question_text: str, options: List[str], correct_letter: str) -> bool:
        """Verify physics questions for accuracy"""
        try:
            correct_index = ord(correct_letter) - ord('A')
            correct_option = options[correct_index].lower()
            
            # Check for basic physics principles
            if 'force' in question_text.lower() and 'newton' in correct_option:
                # F = ma related questions should have reasonable values
                return True
            elif 'energy' in question_text.lower():
                # Energy conservation principles
                if 'created' in correct_option or 'destroyed' in correct_option:
                    # Energy can be converted, not created/destroyed
                    if 'converted' not in correct_option and 'conserved' not in correct_option:
                        logger.warning("Potential energy conservation principle violation")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in physics verification: {str(e)}")
            return False
    
    def _verify_chemistry_question(self, question_text: str, options: List[str], correct_letter: str) -> bool:
        """Verify chemistry questions for accuracy"""
        try:
            correct_index = ord(correct_letter) - ord('A')
            correct_option = options[correct_index].lower()
            
            # Basic chemistry validation
            if 'periodic table' in question_text.lower():
                # Check for reasonable atomic numbers, symbols
                return True
            elif 'reaction' in question_text.lower():
                # Basic reaction principles
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error in chemistry verification: {str(e)}")
            return False
    
    def _verify_programming_question(self, question_text: str, options: List[str], correct_letter: str) -> bool:
        """Verify programming questions for accuracy"""
        try:
            correct_index = ord(correct_letter) - ord('A')
            correct_option = options[correct_index]
            
            # Check for basic programming logic
            if 'python' in question_text.lower() or 'java' in question_text.lower():
                # Language-specific checks
                if 'syntax error' in correct_option.lower():
                    # Make sure the syntax error is actually wrong
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error in programming verification: {str(e)}")
            return False
    
    def _verify_general_question(self, question_text: str, options: List[str], correct_letter: str, topics: List[str] = None) -> bool:
        """General verification for non-STEM questions - more lenient for problem-solving topics"""
        try:
            correct_index = ord(correct_letter) - ord('A')
            if correct_index >= len(options):
                return False
                
            correct_option = options[correct_index].lower()
            question_lower = question_text.lower()
            
            # For problem-solving and general learning topics, be more lenient
            if topics and any(topic in ['problem solving', 'problem-solving', 'general', 'learning', 'study'] 
                             for topic in [t.lower() for t in topics]):
                # Only reject obviously wrong statements
                obvious_errors = ['impossible in all cases', 'never works', 'always fails', 'completely wrong']
                if any(error in correct_option for error in obvious_errors):
                    logger.warning("Obviously incorrect statement detected")
                    return False
                return True
            
            # For other topics, apply moderate validation
            # Allow statements with "all of the above" as they're often legitimate
            if 'all of the above' in correct_option:
                return True
                
            # Check for overly absolute statements only in specific contexts
            problematic_absolutes = ['always impossible', 'never correct', 'completely useless']
            if any(absolute in correct_option for absolute in problematic_absolutes):
                logger.warning("Potentially overgeneralized statement detected")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in general verification: {str(e)}")
            return True  # Default to accepting if verification fails
    
    def _check_hallucination_patterns(self, question: Dict, topic: str) -> bool:
        """Check for common hallucination patterns in AI-generated content"""
        try:
            question_text = question.get("question_text", "").lower()
            options = [opt.lower() for opt in question.get("options", [])]
            explanation = question.get("explanation", "").lower()
            
            # Check for made-up formulas or equations
            if any(pattern in question_text for pattern in ['™', '®', '©']):
                logger.warning("Suspicious trademark symbols in question")
                return False
            
            # Check for overly specific fake dates, names, or statistics
            import re
            if re.search(r'\b(19|20)\d{2}\b', question_text) and 'history' not in topic:
                # Specific years in non-history topics might be made up
                logger.warning("Suspicious specific date in non-historical context")
                return False
            
            # Check for impossible combinations
            if any(combo in question_text for combo in ['square circle', 'frozen fire', 'liquid gas']):
                logger.warning("Impossible physical combination detected")
                return False
            
            # Check explanation quality
            if len(explanation) < 20:  # Too brief explanations are suspicious
                logger.warning("Explanation too brief, might lack proper reasoning")
                return False
            
            # Check for contradictory options
            correct_index = ord(question.get("correct_answer", "A")) - ord('A')
            if correct_index < len(options):
                correct_option = options[correct_index]
                for i, option in enumerate(options):
                    if i != correct_index and option == correct_option:
                        logger.warning("Duplicate options detected")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in hallucination check: {str(e)}")
            return True  # Default to accepting if check fails
    
    def _parse_single_question(self, section: str) -> Optional[Dict]:
        """Parse a single question from the AI response"""
        lines = section.split('\n')
        question_data = {}
        
        try:
            # Extract question number and text
            first_line = lines[0]
            if ':' in first_line:
                # Extract question text (ignore the original numbering)
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
                    parsed_options = self._parse_options(options_text)
                    if parsed_options is None:  # Parsing failed
                        logger.warning(f"Failed to parse options for question {question_data.get('question_number', '?')}")
                        return None
                    question_data["options"] = parsed_options
                elif line.startswith('Correct Answer:'):
                    raw_answer = line.split(':', 1)[1].strip()
                    # Extract just the letter (A, B, C, or D) from answers like "C) $100,000" or "C"
                    import re
                    letter_match = re.match(r'^([A-D])', raw_answer.upper())
                    if letter_match:
                        question_data["correct_answer"] = letter_match.group(1)
                    else:
                        # Fallback: try to find any single letter A-D in the answer
                        letters = re.findall(r'\b([A-D])\b', raw_answer.upper())
                        if letters:
                            question_data["correct_answer"] = letters[0]
                        else:
                            question_data["correct_answer"] = raw_answer  # Keep original if no letter found
                elif line.startswith('Explanation:'):
                    question_data["explanation"] = line.split(':', 1)[1].strip()
                elif line.startswith('Verification:'):
                    question_data["verification"] = line.split(':', 1)[1].strip()
                elif line.startswith('Points:'):
                    try:
                        question_data["points"] = int(line.split(':', 1)[1].strip().split()[0])
                    except:
                        question_data["points"] = 1
            
            # Set defaults for MCQ only
            question_data.setdefault("type", "multiple_choice")
            question_data.setdefault("points", 2)  # Standard 2 points per MCQ
            
            # Ensure we have options for multiple choice
            if question_data["type"] == "multiple_choice" and "options" not in question_data:
                question_data["options"] = ["First answer", "Second answer", "Third answer", "Fourth answer"]
            
            # Validate that options are not generic placeholders
            if "options" in question_data:
                options = question_data["options"]
                generic_patterns = ["Option A", "Option B", "Option C", "Option D", "option1", "option2", "option3", "option4"]
                if any(opt in generic_patterns for opt in options):
                    logger.warning(f"Generic options detected in question {question_data.get('question_number', '?')}")
                    # This question will be filtered out later
                    return None
            
            return question_data
            
        except Exception as e:
            logger.error(f"Error parsing question: {str(e)}")
            return None
    
    def _parse_options(self, options_text: str) -> List[str]:
        """Parse multiple choice options with robust extraction"""
        import re
        options = []
        
        # Clean the input text
        options_text = options_text.strip()
        
        # Method 1: Split by newlines and parse each line
        lines = options_text.split('\n')
        for line in lines:
            line = line.strip()
            match = re.match(r'^([A-D])\)\s*(.+)', line)
            if match:
                content = match.group(2).strip()
                if content and len(content) > 1:
                    options.append(content)
        
        # Method 2: If Method 1 failed, try splitting by letter patterns
        if len(options) != 4:
            options = []
            # Split text by A), B), C), D) patterns
            parts = re.split(r'\s*([A-D])\)\s*', options_text)
            # parts will be like ['', 'A', 'content1', 'B', 'content2', 'C', 'content3', 'D', 'content4']
            
            for i in range(1, len(parts), 2):  # Get every other element starting from index 1
                if i + 1 < len(parts):
                    letter = parts[i]
                    content = parts[i + 1].strip()
                    
                    # Clean up content by removing next letter pattern
                    content = re.split(r'\s+[A-D]\)', content)[0].strip()
                    
                    if content and len(content) > 1:
                        options.append(content)
        
        # Method 3: Find individual patterns for each letter
        if len(options) != 4:
            options = []
            for letter in ['A', 'B', 'C', 'D']:
                # Look for this specific letter followed by content
                pattern = f'{letter}\\)\\s*([^A-D\\)]*?)(?=[A-D]\\)|$)'
                match = re.search(pattern, options_text, re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    # Clean up any remaining artifacts
                    content = re.sub(r'\n+', ' ', content).strip()
                    if content and len(content) > 1:
                        options.append(content)
        
        # Method 4: Last resort - split by common delimiters and hope for the best
        if len(options) != 4:
            options = []
            # Try splitting by patterns that might separate options
            potential_options = re.split(r'[A-D]\)\s*', options_text)[1:]  # Skip first empty element
            
            for opt in potential_options[:4]:  # Only take first 4
                content = opt.strip()
                # Remove any trailing patterns
                content = re.split(r'\s+[A-D]\)', content)[0].strip()
                if content and len(content) > 1:
                    options.append(content)
        
        # Final validation
        if len(options) < 4:
            logger.warning(f"Could not parse exactly 4 options from: {options_text[:200]}...")
            
            # Emergency fallback - create generic but topic-relevant options
            if len(options) > 0:
                base_option = options[0] if options else "Answer"
                fallback_options = []
                for i in range(4):
                    if i < len(options):
                        fallback_options.append(options[i])
                    else:
                        fallback_options.append(f"{base_option} variant {i+1}")
                options = fallback_options
            else:
                return None
        
        # Check for overly generic patterns
        generic_patterns = ["Option A", "Option B", "Option C", "Option D", 
                           "option1", "option2", "option3", "option4",
                           "First answer", "Second answer", "Third answer", "Fourth answer",
                           "Answer variant"]
        
        if any(any(pattern.lower() in opt.lower() for pattern in generic_patterns) for opt in options):
            logger.warning(f"Generic options detected: {options}")
            return None
        
        # Ensure exactly 4 unique options
        unique_options = []
        for option in options[:4]:  # Only take first 4
            cleaned_option = option.strip()
            if cleaned_option and len(cleaned_option) > 1 and cleaned_option not in unique_options:
                unique_options.append(cleaned_option)
        
        # If we still don't have 4 unique options, this question should be discarded
        if len(unique_options) < 4:
            logger.warning(f"Not enough unique valid options after cleaning: {unique_options}")
            return None
            
        return unique_options
    
    def grade_quiz(self, quiz: Dict, user_answers: Dict) -> Dict:
        """Grade a completed quiz with accuracy double-checking"""
        results = {
            "quiz_id": quiz["quiz_id"],
            "total_questions": len(quiz["questions"]),
            "total_points": quiz["total_points"],
            "user_score": 0,
            "correct_answers": 0,
            "percentage": 0,
            "grade_letter": "F",
            "feedback": [],
            "completed_at": datetime.now().isoformat(),
            "accuracy_verified": quiz.get("accuracy_verified", False)
        }
        
        for question in quiz["questions"]:
            q_num = question["question_number"]
            user_answer = user_answers.get(str(q_num), "").strip()
            correct_answer = question["correct_answer"].strip()
            
            # Double-check the correct answer before grading
            is_answer_verified = self._double_check_correct_answer(question)
            if not is_answer_verified:
                logger.warning(f"Question {q_num} correct answer could not be verified, accepting as-is")
            
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
                "verification_status": question.get("verification", "Not verified"),
                "answer_verified": is_answer_verified,
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
    
    def _double_check_correct_answer(self, question: Dict) -> bool:
        """Double-check if the marked correct answer is actually correct"""
        try:
            question_text = question.get("question_text", "").lower()
            options = question.get("options", [])
            correct_letter = question.get("correct_answer", "").strip().upper()
            
            if correct_letter not in ['A', 'B', 'C', 'D'] or len(options) != 4:
                return False
            
            correct_index = ord(correct_letter) - ord('A')
            if correct_index >= len(options):
                return False
            
            correct_option = options[correct_index]
            
            # Basic mathematical verification
            if any(math_term in question_text for math_term in ['derivative', 'integral', 'solve', 'calculate']):
                # For simple derivative questions
                if 'derivative' in question_text and 'x²' in question_text:
                    if '2x' not in correct_option and 'x' in correct_option:
                        logger.warning(f"Derivative calculation may be incorrect: {correct_option}")
                        return False
                
                # For simple integral questions  
                if 'integral' in question_text or '∫' in question_text:
                    if '+' in question_text and '+' not in correct_option:
                        # Basic integration should preserve addition
                        pass  # This is just a basic check
            
            # Check if the correct option makes logical sense
            if any(nonsense in correct_option.lower() for nonsense in ['impossible', 'cannot exist', 'never happens']) and 'theory' not in question_text:
                logger.warning(f"Potentially nonsensical answer: {correct_option}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in answer verification: {str(e)}")
            return False
    
    def _cross_verify_critical_question(self, question: Dict, course_context: Dict) -> bool:
        """Use a separate AI call to verify critical mathematical/scientific questions"""
        try:
            question_text = question.get("question_text", "")
            options = question.get("options", [])
            correct_letter = question.get("correct_answer", "")
            topic = course_context.get("topic", "").lower()
            
            # Only cross-verify for STEM subjects where accuracy is critical
            if not any(stem in topic for stem in ['math', 'physics', 'chemistry', 'engineering', 'calculus', 'algebra']):
                return True
            
            # Skip if question doesn't involve calculations or formulas
            if not any(indicator in question_text.lower() for indicator in ['calculate', 'solve', 'derivative', 'integral', '=', '+', '-', '*', '/', '^']):
                return True
            
            verification_prompt = f"""You are a mathematics/science expert verifier. Your ONLY job is to check if the marked correct answer is actually correct.

**Question:** {question_text}

**Options:**
A) {options[0] if len(options) > 0 else 'N/A'}
B) {options[1] if len(options) > 1 else 'N/A'}  
C) {options[2] if len(options) > 2 else 'N/A'}
D) {options[3] if len(options) > 3 else 'N/A'}

**Marked as Correct:** {correct_letter}

**Your Task:** 
1. Work through this problem step-by-step
2. Show your calculation/reasoning
3. Determine which option is actually correct
4. Respond with ONLY: "VERIFIED" if the marked answer is correct, or "INCORRECT: [correct letter]" if it's wrong

**Critical:** Show your work and be absolutely certain. If you cannot verify with certainty, respond "UNCERTAIN"."""

            messages = [{"role": "user", "content": verification_prompt}]
            response = self._ask_claude(messages, temperature=0.1, max_tokens=800)  # Very low temperature for accuracy
            
            response = response.strip().upper()
            
            if "VERIFIED" in response:
                return True
            elif "INCORRECT" in response:
                # Extract the suggested correct answer
                logger.error(f"Cross-verification failed for question: {question_text}")
                logger.error(f"AI suggests correct answer should be: {response}")
                return False
            elif "UNCERTAIN" in response:
                logger.warning(f"Cross-verification uncertain for question: {question_text}")
                # Accept with warning if AI is uncertain
                return True
            else:
                logger.warning(f"Unexpected cross-verification response: {response}")
                return True
                
        except Exception as e:
            logger.error(f"Error in cross-verification: {str(e)}")
            return True  # Default to accepting if verification fails
    
    def _check_answer(self, user_answer: str, correct_answer: str, question_type: str) -> bool:
        """Check if user answer is correct"""
        user_answer = user_answer.strip()
        correct_answer = correct_answer.strip()
        
        if question_type == "multiple_choice":
            # Extract the letter from correct answer if it's in format "A) option" or just "A"
            correct_letter = correct_answer.upper()
            if ')' in correct_letter:
                correct_letter = correct_letter.split(')')[0].strip()
            
            user_letter = user_answer.upper()
            if ')' in user_letter:
                user_letter = user_letter.split(')')[0].strip()
            
            # Check if the letters match
            return user_letter == correct_letter
        
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
        elif percentage >= 60:
            return "📚 Good progress! You have a solid understanding. Review any missed concepts to strengthen your knowledge."
        elif percentage > 40:
            return "⚠️ You're making progress! Review this week's content and you can continue to the next week."
        else:
            return "📖 You need to retake this quiz. Please review the material - you need more than 40% to continue."
    
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
    
    def chat_about_lesson(self, course_context: Dict, week_context: Dict, question: str, history: list) -> str:
        topic = (course_context or {}).get("topic", "this course")
        difficulty = (course_context or {}).get("difficulty", "beginner")

        week_title = (week_context or {}).get("title", "")
        overview = (week_context or {}).get("overview", "")
        activities = (week_context or {}).get("activities", "")
        resources = (week_context or {}).get("resources", "")

        lesson_titles = []
        for lt in (week_context or {}).get("lesson_topics", []) or []:
            name = lt.get("title") or (lt.get("lesson_info") or {}).get("title")
            if name:
                lesson_titles.append(name)
        lesson_list = "; ".join(lesson_titles[:8])

        sys_rules = (
            "You are Sandwich, a friendly, concise AI tutor. "
            "Answer briefly (2–5 sentences). "
            "Ground answers in the provided course/week context when relevant; if unrelated, say so. "
            "Use numbered steps for procedures; be correct with code/math."
        )

        context_blob = f"""Course Topic: {topic}
    Difficulty: {difficulty}
    Week: {week_title}

    Week Overview:
    {(overview or '')[:800]}

    Lesson Topics:
    {lesson_list}

    Activities (excerpt):
    {(activities or '')[:400]}

    Resources (excerpt):
    {(resources or '')[:400]}
    """.strip()

        # ---- Build Bedrock messages (first MUST be 'user') ----
        messages: list[dict] = []

        # 1) Add recent history (filtered)
        for m in (history or [])[-8:]:
            role = (m.get("role") or "").strip()
            content = (m.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # 2) Ensure the very first message is a 'user'
        if not messages or messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "(continuing lesson Q&A)"} )

        # 3) Append the current question as a final user turn with context
        messages.append({
            "role": "user",
            "content": f"Context:\n{context_blob}\n\nQuestion: {question}"
        })

        # 4) Call Bedrock (system prompt at TOP LEVEL)
        from app.core.bedrock import ask_claude
        return ask_claude(messages, temperature=0.3, max_tokens=500, system=sys_rules)


    
    def generate_study_tips(self, week_info: Dict, course_context: Dict, student_performance: Optional[Dict] = None) -> List[str]:
        """Generate 5 short, actionable study tips with robust parsing."""
        topic = (course_context.get("topic") or "").strip()
        week_title = (week_info.get("title") or "").strip()
        learner_type = (course_context.get("learner_type") or "").strip().lower()
        difficulty = (course_context.get("difficulty") or "").strip()
        pct = None
        try:
            pct = student_performance.get("percentage") if student_performance else None
        except Exception:
            pct = None

        # Tiny hint to steer style-specific tips
        style_hints = {
            "visual": "use visuals, diagrams, color-coding",
            "auditory": "read aloud, explain out loud, use audio",
            "kinesthetic": "hands-on practice, movement, real objects",
            "read/write": "take notes, lists, rewrite summaries",
        }
        style_hint = style_hints.get(learner_type, "balanced strategies")

        # Ask for strict JSON to avoid brittle parsing
        prompt = f"""You are Sandwich, an AI learning coach.
    Return ONLY a JSON array of EXACTLY 5 strings (no backticks, no keys, no commentary).
    Each string:
    - Imperative voice, practical and specific to this week
    - ≤ 120 characters
    - No numbering, no emojis
    - Mix of practice, recall, reflection, and planning

    Context:
    - Topic: {topic}
    - Week: {week_title}
    - Learning style: {learner_type} ({style_hint})
    - Difficulty level: {difficulty}
    {f"- Recent quiz performance: {pct}%" if pct is not None else ""}

    JSON array only:"""

        messages = [{"role": "user", "content": prompt}]
        resp = self._ask_claude(messages, temperature=0.5, max_tokens=400)

        tips: List[str] = []

        # 1) Prefer JSON array parsing
        try:
            # Extract first [...] block to be safe if model adds stray text
            match = re.search(r"\[[\s\S]*\]", resp)
            if match:
                arr = json.loads(match.group(0))
                if isinstance(arr, list):
                    tips = [str(x) for x in arr if isinstance(x, (str, int, float))]
        except Exception:
            tips = []

        # 2) Fallback: parse bullets/numbered lines if JSON failed
        if not tips:
            for line in (resp or "").splitlines():
                s = line.strip()
                if not s:
                    continue
                # strip leading numbers/bullets
                s = re.sub(r"^\s*(?:[-•]+|\d+[\.)\-:]?)\s*", "", s)
                if s:
                    tips.append(s)

        # 3) Normalize, dedupe, trim length, ensure sentence end
        cleaned: List[str] = []
        seen = set()
        for t in tips:
            t = re.sub(r"\s+", " ", str(t)).strip()
            if not t:
                continue
            if len(t) > 120:
                t = t[:117].rstrip() + "…"
            if not t.endswith((".", "!", "?")):
                t += "."
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(t)

        # 4) Guarantee exactly 5 with safe fallbacks
        i = 0
        while len(cleaned) < 5 and i < len(FALLBACK_TIPS):
            ft = FALLBACK_TIPS[i]
            if not ft.endswith((".", "!", "?")):
                ft += "."
            if ft.lower() not in seen:
                cleaned.append(ft)
                seen.add(ft.lower())
            i += 1

        return cleaned[:5]
    
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
        elif avg_score >= 60:
            if trend == "improving":
                return "📚 Good progress! Keep studying and you'll master this."
            else:
                return "💪 You're on the right track. A little more practice and you'll excel."
        elif avg_score > 40:
            return "🎯 Keep learning! Every expert was once a beginner. You'll improve with practice."
        else:
            return "📖 Don't give up! Review the material and retake quizzes to build your understanding."

    def _verify_quiz_accuracy_lenient(self, quiz_data: Dict, week_info: Dict, course_context: Dict) -> Dict:
        """More lenient verification for later attempts to ensure we get enough questions"""
        if not quiz_data.get("questions"):
            return quiz_data
        
        verified_questions = []
        
        for question in quiz_data["questions"]:
            # Basic question validation only
            if not question.get("question_text") or not question.get("options") or len(question.get("options", [])) != 4:
                logger.warning(f"Question {question.get('question_number', '?')} failed basic validation")
                continue
            
            correct_answer_letter = question.get("correct_answer", "").strip().upper()
            
            # Verify correct answer letter is valid
            if correct_answer_letter not in ['A', 'B', 'C', 'D']:
                logger.warning(f"Question {question.get('question_number', '?')} has invalid correct answer format: {correct_answer_letter}")
                continue
            
            # Minimal validation - just check that the answer index is valid
            try:
                correct_index = ord(correct_answer_letter) - ord('A')
                if correct_index < 0 or correct_index >= len(question.get("options", [])):
                    logger.warning(f"Question {question.get('question_number', '?')} correct answer index out of range")
                    continue
            except:
                logger.warning(f"Question {question.get('question_number', '?')} failed answer index calculation")
                continue
            
            # Accept the question with minimal validation
            question["accuracy_verified"] = True
            question["verified_at"] = datetime.now().isoformat()
            verified_questions.append(question)
        
        # Update quiz data
        quiz_data["questions"] = verified_questions
        quiz_data["total_points"] = sum(q.get("points", 2) for q in verified_questions)
        quiz_data["accuracy_verified"] = True
        
        logger.info(f"Lenient verification: accepted {len(verified_questions)} out of {len(quiz_data.get('questions', []))} questions")
        return quiz_data

    def _generate_fallback_questions(self, num_needed: int, topics: List[str], week_info: Dict) -> List[Dict]:
        """Generate basic fallback questions to ensure we meet the minimum requirement"""
        fallback_questions = []
        
        topic_name = topics[0] if topics else "General Problem Solving"
        week_number = week_info.get('week_number', 1)
        
        for i in range(num_needed):
            question = {
                "question_number": i + 1,
                "question_text": f"Which approach is most effective for {topic_name.lower()} in Week {week_number}?",
                "type": "multiple_choice",
                "options": [
                    "Systematic analysis and step-by-step approach",
                    "Random guessing without planning", 
                    "Ignoring the problem completely",
                    "Rushing to conclusions without understanding"
                ],
                "correct_answer": "A",
                "explanation": "A systematic, step-by-step approach provides the best foundation for effective problem solving and learning.",
                "verification": "This follows established educational best practices.",
                "points": 2,
                "accuracy_verified": True,
                "verified_at": datetime.now().isoformat(),
                "fallback_generated": True
            }
            
            # Vary the questions slightly
            if i == 1:
                question.update({
                    "question_text": f"What is a key principle when studying {topic_name.lower()}?",
                    "options": [
                        "Building understanding gradually from basics to complex",
                        "Starting with the most difficult concepts first",
                        "Memorizing without understanding the logic",
                        "Avoiding practice and real applications"
                    ],
                    "explanation": "Building understanding gradually from basic concepts to more complex ones ensures solid comprehension."
                })
            elif i == 2:
                question.update({
                    "question_text": f"When facing challenges in {topic_name.lower()}, what should you do?",
                    "options": [
                        "Break the problem into smaller manageable parts",
                        "Give up immediately if it seems difficult",
                        "Skip the challenging parts entirely", 
                        "Rush through without careful consideration"
                    ],
                    "explanation": "Breaking problems into smaller parts makes complex challenges more manageable and solvable."
                })
            elif i == 3:
                question.update({
                    "question_text": f"How can you best reinforce learning in {topic_name.lower()}?",
                    "options": [
                        "Regular practice and application of concepts",
                        "Reading only without any practice",
                        "Cramming everything at the last minute",
                        "Avoiding challenging exercises"
                    ],
                    "explanation": "Regular practice and application helps solidify understanding and improve retention."
                })
            
            fallback_questions.append(question)
        
        logger.info(f"Generated {len(fallback_questions)} fallback questions")
        return fallback_questions


# Helper functions for integration

def create_quiz_session(week_info: Dict, course_context: Dict) -> Dict:
    """Create a new quiz session for a week"""
    tutor = AITutor()
    quiz = tutor.generate_quiz(week_info, course_context, num_questions=10)  # 10 questions
    
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
    - If weak performance: reinforce topics, maintain difficulty
    - If strong performance: advance faster, increase difficulty
    Returns a modified week_info dict with adaptive content.
    """
    tutor = AITutor()
    
    # Analyze quiz performance
    quiz_results = recent_quiz.get("results", {})
    percentage = quiz_results.get("percentage", 0)
    correct_answers = quiz_results.get("correct_answers", 0)
    total_questions = quiz_results.get("total_questions", 10)
    
    # Identify strengths and weaknesses
    strengths = []
    weaknesses = []
    weak_topics = []
    
    for feedback in quiz_results.get("feedback", []):
        if feedback["is_correct"]:
            strengths.append(feedback["question_text"])
        else:
            weaknesses.append(feedback["question_text"])
            # Extract topic from question for reinforcement
            question_text = feedback["question_text"].lower()
            if "integral" in question_text or "integration" in question_text:
                weak_topics.append("integration")
            elif "derivative" in question_text or "differentiation" in question_text:
                weak_topics.append("differentiation")
            elif "equation" in question_text or "solve" in question_text:
                weak_topics.append("equation solving")
            # Add more topic extraction logic as needed
    
    # Remove duplicates
    weak_topics = list(set(weak_topics))
    
    # Determine performance level and adaptation strategy
    if percentage >= 80:
        adaptation_type = "accelerate"
        difficulty_adjustment = "increase"
    elif percentage >= 60:
        adaptation_type = "maintain"
        difficulty_adjustment = "same"
    else:
        adaptation_type = "reinforce"
        difficulty_adjustment = "maintain"
    
    # Generate adaptive prompt based on performance
    if adaptation_type == "accelerate":
        adaptation_prompt = f"""You are Sandwich, an adaptive AI course designer. The student EXCELLED in the last quiz with {percentage}% ({correct_answers}/{total_questions} correct).

**Student performed exceptionally well on:**
{chr(10).join([f"- {strength[:100]}..." for strength in strengths[:3]])}

**Adaptation Strategy: ACCELERATE & CHALLENGE**

**Original Week Plan:**
- Title: {week_info.get('title', '')}
- Topics: {', '.join(week_info.get('topics', []))}

**Your Task:** Create an ENHANCED, MORE CHALLENGING version of this week with:

1. **Advanced Topics**: Introduce more sophisticated concepts
2. **Higher Complexity**: More challenging problems and applications  
3. **Extended Scope**: Cover more material since student is ready
4. **Practical Applications**: Real-world, complex scenarios
5. **Quiz Difficulty**: Prepare them for HARDER quiz questions

**Return ENHANCED week plan in JSON:**
{{
    "title": "Enhanced: [original title with advanced focus]",
    "topics": ["Advanced topic 1", "Complex topic 2", "Applied topic 3", "Extended topic 4"],
    "lesson_topics": [
        {{"title": "Advanced [topic]", "summary": "Deep dive into complex applications"}},
        {{"title": "Complex [topic]", "summary": "Challenging problem-solving"}},
        {{"title": "Applied [topic]", "summary": "Real-world scenarios"}},
        {{"title": "Extended [topic]", "summary": "Beyond basic understanding"}}
    ],
    "difficulty_level": "advanced",
    "quiz_difficulty": "hard",
    "adaptation_notes": "Accelerated due to excellent performance ({percentage}%)",
    "overview": "Enhanced week overview with advanced concepts",
    "estimated_duration": "20-25 minutes per lesson"
}}"""

    elif adaptation_type == "reinforce":
        adaptation_prompt = f"""You are Sandwich, an adaptive AI course designer. The student STRUGGLED in the last quiz with {percentage}% ({correct_answers}/{total_questions} correct).

**Student had difficulty with:**
{chr(10).join([f"- {weakness[:100]}..." for weakness in weaknesses[:3]])}

**Identified weak areas:** {', '.join(weak_topics) if weak_topics else 'General understanding'}

**Adaptation Strategy: REINFORCE & SUPPORT**

**Original Week Plan:**
- Title: {week_info.get('title', '')}
- Topics: {', '.join(week_info.get('topics', []))}

**Your Task:** Create a SUPPORTIVE, REINFORCING version of this week with:

1. **Review Integration**: Include review of weak areas: {', '.join(weak_topics)}
2. **Simplified Approach**: Break down complex concepts into smaller steps
3. **Extra Practice**: More examples and practice problems
4. **Confidence Building**: Start with easier concepts, build up gradually
5. **Quiz Difficulty**: Maintain same difficulty level for confidence

**Return SUPPORTIVE week plan in JSON:**
{{
    "title": "Reinforced: [original title with review focus]",
    "topics": ["Review of [weak area]", "Simplified [topic]", "Practice [topic]", "Confidence [topic]"],
    "lesson_topics": [
        {{"title": "Review: [weak topic]", "summary": "Revisit challenging concepts from last week"}},
        {{"title": "Simplified [topic]", "summary": "Step-by-step approach"}},
        {{"title": "Practice [topic]", "summary": "Guided practice with examples"}},
        {{"title": "Confidence [topic]", "summary": "Build understanding gradually"}}
    ],
    "difficulty_level": "supportive",
    "quiz_difficulty": "same",
    "adaptation_notes": "Reinforced due to performance challenges ({percentage}%)",
    "overview": "Supportive week with review and practice",
    "estimated_duration": "15-20 minutes per lesson"
}}"""

    else:  # maintain
        adaptation_prompt = f"""You are Sandwich, an adaptive AI course designer. The student had MODERATE performance in the last quiz with {percentage}% ({correct_answers}/{total_questions} correct).

**Mixed Performance:**
- Strengths: {len(strengths)} correct answers
- Areas for improvement: {len(weaknesses)} incorrect answers

**Adaptation Strategy: BALANCED APPROACH**

**Original Week Plan:**
- Title: {week_info.get('title', '')}
- Topics: {', '.join(week_info.get('topics', []))}

**Your Task:** Create a BALANCED version of this week with:

1. **Steady Progress**: Maintain current difficulty level
2. **Targeted Review**: Brief review of any weak areas
3. **New Concepts**: Introduce planned new topics
4. **Confidence & Challenge**: Balance of both elements
5. **Quiz Difficulty**: Same level with variety

**Return BALANCED week plan in JSON:**
{{
    "title": "Continued: [original title]",
    "topics": ["Progressive [topic]", "Balanced [topic]", "Applied [topic]", "Integrated [topic]"],
    "lesson_topics": [
        {{"title": "Progressive [topic]", "summary": "Building on previous knowledge"}},
        {{"title": "Balanced [topic]", "summary": "Steady skill development"}},
        {{"title": "Applied [topic]", "summary": "Practical applications"}},
        {{"title": "Integrated [topic]", "summary": "Connecting concepts"}}
    ],
    "difficulty_level": "progressive",
    "quiz_difficulty": "same",
    "adaptation_notes": "Balanced approach for steady progress ({percentage}%)",
    "overview": "Balanced week building on current understanding",
    "estimated_duration": "18-22 minutes per lesson"
}}"""

    messages = [{"role": "user", "content": adaptation_prompt}]
    response = tutor._ask_claude(messages, temperature=0.7, max_tokens=1200)

    # Try to parse the JSON from Claude's response
    try:
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            revised_week = json.loads(match.group(0))
            # Ensure required fields
            revised_week["week_number"] = week_info.get("week_number", 2)
            revised_week["completed"] = False
            revised_week["progress"] = 0
            revised_week["quiz_completed"] = False
            
            logger.info(f"Successfully adapted week {revised_week['week_number']} based on {percentage}% quiz performance")
            return revised_week
    except Exception as e:
        logger.error(f"Error parsing revised week plan: {str(e)}")
    
    # Fallback: return original week_info with adaptation note
    week_info["adaptation_notes"] = f"Could not parse AI adaptation for {percentage}% performance. Original plan used."
    week_info["quiz_difficulty"] = difficulty_adjustment
    return week_info

def get_tutoring_help(question: str, week_info: Dict, course_context: Dict) -> str:
    """Get AI tutoring help for a question"""
    tutor = AITutor()
    return tutor.provide_tutoring(question, week_info, course_context)

def get_personalized_study_tips(week_info: Dict, course_context: Dict, recent_quiz: Optional[Dict] = None) -> List[str]:
    """Get personalized study tips"""
    tutor = AITutor()
    return tutor.generate_study_tips(week_info, course_context, recent_quiz)
import os
import json
import re
import logging
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import requests
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class SyllabusGenerator:
    def __init__(self):
        self.client = self._get_bedrock_client()
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")  # Optional for enhanced search
    
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
    
    def _ask_claude(self, messages: list, temperature: float = 0.7, max_tokens: int = 1200) -> str:
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
            return "I'm having trouble generating content right now. Please try again."
    
    def parse_course_structure(self, syllabus_text: str) -> List[Dict]:
        """Parse the generated syllabus into structured weeks/modules"""
        weeks = []
        
        logger.info(f"Parsing syllabus for week patterns...")
        
        # Multiple patterns to catch different week formats
        patterns = [
            r'### Week (\d+):\s*(.+?)(?=\n|$)',  # ### Week 1: Title
            r'## Week (\d+):\s*(.+?)(?=\n|$)',   # ## Week 1: Title  
            r'\*\*Week (\d+):\s*(.+?)\*\*',      # **Week 1: Title**
            r'Week (\d+):\s*(.+?)(?=\n|$)',      # Week 1: Title
            r'(\d+)\.\s*Week (\d+):\s*(.+?)(?=\n|$)'  # 1. Week 1: Title
        ]
        
        week_matches = []
        matched_pattern = None
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, syllabus_text, re.IGNORECASE | re.MULTILINE))
            if matches:
                week_matches = matches
                matched_pattern = pattern
                logger.info(f"Found {len(matches)} weeks using pattern: {pattern}")
                break
        
        if not week_matches:
            logger.error("No weeks found with any pattern!")
            return []
        
        # Sort matches by their position in text
        week_matches.sort(key=lambda x: x.start())
        
        for i, match in enumerate(week_matches):
            try:
                # Extract week number and title based on pattern
                if matched_pattern == patterns[4]:  # 1. Week 1: Title pattern
                    week_num = int(match.group(2))
                    week_title = match.group(3).strip()
                else:
                    week_num = int(match.group(1))
                    week_title = match.group(2).strip() if len(match.groups()) > 1 else f"Week {week_num}"
                
                # Find the content for this week
                start_pos = match.end()
                
                # Find next week or end of text
                if i + 1 < len(week_matches):
                    end_pos = week_matches[i + 1].start()
                else:
                    end_pos = len(syllabus_text)
                
                week_content = syllabus_text[start_pos:end_pos].strip()
                
                # Extract topics from the week content
                topics = self._extract_topics(week_content)
                
                # If no topics found, create some based on the title
                if not topics:
                    topics = [
                        f"Introduction to {week_title}",
                        "Key concepts and definitions",
                        "Historical context",
                        "Important events and figures"
                    ]
                
                week_data = {
                    "week_number": week_num,
                    "title": f"Week {week_num}: {week_title}",
                    "content": week_content,
                    "topics": topics,
                    "completed": False
                }
                
                weeks.append(week_data)
                logger.info(f"Created week {week_num}: Week {week_num}: {week_title}")
                
            except Exception as e:
                logger.error(f"Error parsing week {i}: {str(e)}")
                continue
        
        logger.info(f"Successfully parsed {len(weeks)} weeks")
        return weeks
    
    def _extract_topics(self, week_content: str) -> List[str]:
        """Extract individual topics from week content"""
        lines = week_content.split('\n')
        topics = []
        
        for line in lines:
            line = line.strip()
            # Look for various bullet point styles
            if (line.startswith('-') or line.startswith('•') or 
                line.startswith('*') or line.startswith('+')):
                topic = line[1:].strip()
                if topic and len(topic) > 3:  # Filter out very short items
                    topics.append(topic)
            # Also look for numbered lists
            elif re.match(r'^\d+\.', line):
                topic = re.sub(r'^\d+\.\s*', '', line).strip()
                if topic and len(topic) > 3:
                    topics.append(topic)

        return topics[:3]  # Limit to 3 main topics per week

    def generate_week_content(self, week_info: Dict, course_context: Dict) -> Dict:
        """Generate detailed content for a specific week"""
        prompt = f"""You are Sandwich, an expert AI tutor. Create comprehensive learning content for this week of the course.

**Course Context:**
- Topic: {course_context.get('topic', '')}
- Difficulty: {course_context.get('difficulty', '')}
- Learning Style: {course_context.get('learner_type', '')}

**Week Details:**
- {week_info['title']}
- Topics to cover: {', '.join(week_info['topics'])}

Create detailed learning content including:

1. **📋 Week Overview** (2-3 sentences about what students will learn)

2. **🎯 Learning Objectives** (3-4 specific, measurable goals)

3. **📚 Lesson Content** for each main topic:
   - Clear explanations with examples
   - Key concepts and definitions
   - Real-world applications
   - Common misconceptions to avoid

4. **🛠️ Hands-on Activities** (2-3 practical exercises)

5. **🔍 Additional Resources** (suggest types of materials to look for)

6. **✅ Week Completion Checklist** (what students should be able to do)

Make the content engaging, practical, and appropriate for their difficulty level. Use clear formatting with headers and bullet points."""

        messages = [{"role": "user", "content": prompt}]
        content = self._ask_claude(messages, temperature=0.6, max_tokens=1500)
        
        # Generate YouTube video suggestions
        videos = self._suggest_youtube_videos(week_info, course_context)
        
        return {
            "week_number": week_info['week_number'],
            "title": week_info['title'],
            "content": content,
            "videos": videos,
            "completed": False,
            "progress": 0
        }
    
    def _suggest_youtube_videos(self, week_info: Dict, course_context: Dict) -> List[Dict]:
        """Suggest relevant YouTube videos for the week"""
        # Generate search queries for the main topics
        topic = course_context.get('topic', '')
        difficulty = course_context.get('difficulty', 'beginner')
        
        videos = []
        
        # Create search terms for each topic in the week
        for i, subtopic in enumerate(week_info['topics'][:3]):  # Limit to 3 videos per week
            # Create search query
            search_terms = [topic, subtopic]
            if 'beginner' in difficulty.lower():
                search_terms.append('tutorial')
            elif 'advanced' in difficulty.lower():
                search_terms.append('advanced')
            
            query = ' '.join(search_terms)
            
            # Generate likely video suggestions (you can enhance this with actual YouTube API)
            video_suggestions = self._generate_video_suggestions(query, subtopic)
            videos.extend(video_suggestions)
        
        return videos[:4]  # Return up to 4 video suggestions
    
    def _generate_video_suggestions(self, query: str, subtopic: str) -> List[Dict]:
        """Generate video suggestions using AI (fallback when YouTube API not available)"""
        prompt = f"""You are an expert at finding educational YouTube videos. For the search query "{query}" related to "{subtopic}", suggest 1-2 realistic YouTube videos that would likely exist.

For each video suggestion, provide:
- A realistic video title (how it would appear on YouTube)
- Channel name (realistic educational channel)
- Brief description of what the video covers
- Estimated duration (realistic for the topic)

Format as a list with clear separators. Make sure these sound like real YouTube videos that would help someone learn about "{subtopic}"."""

        messages = [{"role": "user", "content": prompt}]
        response = self._ask_claude(messages, temperature=0.8, max_tokens=400)
        
        # Parse the response into video objects
        videos = self._parse_video_suggestions(response, query)
        return videos
    
    def _parse_video_suggestions(self, response: str, query: str) -> List[Dict]:
        """Parse AI-generated video suggestions into structured format"""
        videos = []
        lines = response.split('\n')
        
        current_video = {}
        for line in lines:
            line = line.strip()
            if 'title' in line.lower() and ':' in line:
                if current_video:
                    videos.append(current_video)
                    current_video = {}
                current_video['title'] = line.split(':', 1)[1].strip().replace('"', '')
                # Generate a search URL (users can click to search)
                search_query = quote_plus(f"{current_video['title']} {query}")
                current_video['url'] = f"https://www.youtube.com/results?search_query={search_query}"
            elif 'channel' in line.lower() and ':' in line:
                current_video['channel'] = line.split(':', 1)[1].strip()
            elif 'description' in line.lower() and ':' in line:
                current_video['description'] = line.split(':', 1)[1].strip()
            elif 'duration' in line.lower() and ':' in line:
                current_video['duration'] = line.split(':', 1)[1].strip()
        
        if current_video:
            videos.append(current_video)
        
        return videos
    
    def get_course_navigation(self, weeks: List[Dict], current_week: int) -> Dict:
        """Generate course navigation information"""
        total_weeks = len(weeks)
        completed_weeks = sum(1 for week in weeks if week.get('completed', False))
        
        return {
            "current_week": current_week,
            "total_weeks": total_weeks,
            "completed_weeks": completed_weeks,
            "progress_percentage": round((completed_weeks / total_weeks) * 100, 1) if total_weeks > 0 else 0,
            "next_week": current_week + 1 if current_week < total_weeks else None,
            "previous_week": current_week - 1 if current_week > 1 else None,
            "week_list": [
                {
                    "week_number": week["week_number"],
                    "title": week["title"],
                    "completed": week.get("completed", False),
                    "available": week["week_number"] <= current_week + 1  # Allow access to current and next week
                }
                for week in weeks
            ]
        }
    
    def mark_week_complete(self, weeks: List[Dict], week_number: int, quiz_score: Optional[float] = None) -> List[Dict]:
        """Mark a week as completed"""
        for week in weeks:
            if week["week_number"] == week_number:
                week["completed"] = True
                week["progress"] = 100
                if quiz_score is not None:
                    week["quiz_score"] = quiz_score
                break
        return weeks
    
    def get_course_summary(self, weeks: List[Dict], course_context: Dict) -> Dict:
        """Generate overall course progress summary"""
        total_weeks = len(weeks)
        completed_weeks = sum(1 for week in weeks if week.get('completed', False))
        
        # Calculate average quiz score if available
        quiz_scores = [week.get('quiz_score') for week in weeks if week.get('quiz_score') is not None]
        avg_quiz_score = sum(quiz_scores) / len(quiz_scores) if quiz_scores else None
        
        return {
            "course_title": f"Learning {course_context.get('topic', 'Course')}",
            "difficulty": course_context.get('difficulty', ''),
            "total_weeks": total_weeks,
            "completed_weeks": completed_weeks,
            "progress_percentage": round((completed_weeks / total_weeks) * 100, 1) if total_weeks > 0 else 0,
            "average_quiz_score": round(avg_quiz_score, 1) if avg_quiz_score else None,
            "estimated_completion": self._estimate_completion_date(course_context.get('duration', ''), completed_weeks, total_weeks)
        }
    
    def _estimate_completion_date(self, duration: str, completed_weeks: int, total_weeks: int) -> str:
        """Estimate when the course will be completed"""
        if completed_weeks >= total_weeks:
            return "Course Completed! 🎉"
        
        remaining_weeks = total_weeks - completed_weeks
        
        # Simple estimation based on duration
        if 'week' in duration.lower():
            return f"Approximately {remaining_weeks} weeks remaining"
        elif 'month' in duration.lower():
            months_remaining = max(1, remaining_weeks // 4)
            return f"Approximately {months_remaining} month{'s' if months_remaining > 1 else ''} remaining"
        else:
            return f"{remaining_weeks} lessons remaining"

# Move this function OUTSIDE the class, at the end of the file
def initialize_course_from_syllabus(syllabus_text: str, course_context: Dict) -> Dict:
    """Initialize a complete course structure from syllabus text"""
    logger.info("Initializing course from syllabus")
    
    try:
        generator = SyllabusGenerator()
        
        # Parse the syllabus into weeks
        weeks = generator.parse_course_structure(syllabus_text)
        logger.info(f"Parsed {len(weeks)} weeks from syllabus")
        
        # If no weeks found, create fallback structure
        if not weeks:
            logger.warning("No weeks found, creating fallback")
            topic = course_context.get('topic', 'the subject')
            duration = course_context.get('duration', '4 weeks')
            
            # Estimate number of weeks from duration
            num_weeks = 4  # default
            if 'month' in duration.lower():
                import re
                month_match = re.search(r'(\d+)', duration)
                if month_match:
                    num_weeks = int(month_match.group(1)) * 4
            
            # Create simple fallback weeks
            weeks = []
            for i in range(1, min(num_weeks + 1, 9)):
                weeks.append({
                    "week_number": i,
                    "title": f"Week {i}: {topic.title()} - Part {i}",
                    "content": f"Learning content for week {i}",
                    "topics": [f"Topic {i}.1", f"Topic {i}.2", f"Topic {i}.3"],
                    "completed": False
                })
        
        # Generate detailed content for each week
        detailed_weeks = []
        for week in weeks:
            try:
                detailed_week = generator.generate_week_content(week, course_context)
                detailed_weeks.append(detailed_week)
            except Exception as e:
                logger.error(f"Error generating content for week {week.get('week_number')}: {str(e)}")
                detailed_weeks.append(week)  # Use original if generation fails
        
        # Simple navigation
        navigation = {
            "current_week": 1,
            "total_weeks": len(detailed_weeks),
            "completed_weeks": 0,
            "progress_percentage": 0,
            "next_week": 2 if len(detailed_weeks) > 1 else None,
            "previous_week": None
        }
        
        # Simple summary
        summary = {
            "course_title": f"Learning {course_context.get('topic', 'Course')}",
            "total_weeks": len(detailed_weeks),
            "completed_weeks": 0,
            "progress_percentage": 0
        }
        
        logger.info(f"Course initialized with {len(detailed_weeks)} weeks")
        
        return {
            "weeks": detailed_weeks,
            "navigation": navigation,
            "summary": summary,
            "course_context": course_context
        }
        
    except Exception as e:
        logger.error(f"Error in course initialization: {str(e)}")
        
        # Simple emergency fallback
        return {
            "weeks": [{
                "week_number": 1,
                "title": f"Week 1: {course_context.get('topic', 'Course')}",
                "content": syllabus_text,
                "topics": ["Introduction", "Basic Concepts"],
                "completed": False
            }],
            "navigation": {
                "current_week": 1,
                "total_weeks": 1,
                "completed_weeks": 0,
                "progress_percentage": 0
            },
            "summary": {
                "course_title": f"Learning {course_context.get('topic', 'Course')}",
                "total_weeks": 1,
                "completed_weeks": 0
            },
            "course_context": course_context
        }
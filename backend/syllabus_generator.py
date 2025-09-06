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
        
        # Add debugging
        logger.info(f"Parsing syllabus text: {syllabus_text[:500]}...")
        
        # Updated regex patterns to catch different formats
        patterns = [
            r'\*\*Week (\d+):(.*?)\*\*',  # **Week 1: Title**
            r'\*\*Week (\d+):(.*?)$',     # **Week 1: Title (end of line)
            r'Week (\d+):(.*?)$',         # Week 1: Title (without **)
            r'(\d+)\.\s*Week (\d+):(.*?)$', # 1. Week 1: Title
            r'# Week (\d+):(.*?)$',       # # Week 1: Title (markdown header)
            r'## Week (\d+):(.*?)$'       # ## Week 1: Title (markdown header)
        ]
        
        for pattern in patterns:
            week_matches = list(re.finditer(pattern, syllabus_text, re.IGNORECASE | re.MULTILINE))
            if week_matches:
                logger.info(f"Found {len(week_matches)} weeks using pattern: {pattern}")
                break
        else:
            logger.warning("No weeks found with any pattern. Trying broader search...")
            # Fallback: look for any mention of weeks
            week_matches = list(re.finditer(r'week\s+(\d+)', syllabus_text, re.IGNORECASE))
            logger.info(f"Fallback found {len(week_matches)} week mentions")
        
        if not week_matches:
            logger.error("No weeks found in syllabus text!")
            return []
        
        for i, match in enumerate(week_matches):
            try:
                if len(match.groups()) >= 2:
                    week_num = int(match.group(1))
                    week_title = f"Week {week_num}: {match.group(2).strip()}"
                else:
                    week_num = int(match.group(1))
                    week_title = f"Week {week_num}"
                
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
                
                # If no topics found, create generic ones
                if not topics:
                    topics = [f"Introduction to {week_title}", f"Core concepts", f"Practice exercises"]
                
                week_data = {
                    "week_number": week_num,
                    "title": week_title,
                    "content": week_content,
                    "topics": topics,
                    "completed": False
                }
                
                weeks.append(week_data)
                logger.info(f"Created week {week_num}: {week_title}")
                
            except Exception as e:
                logger.error(f"Error parsing week {i}: {str(e)}")
                continue
        
        logger.info(f"Successfully parsed {len(weeks)} weeks")
        return weeks
    
    def _extract_topics(self, week_content: str) -> List[str]:
        """Extract individual topics from week content"""
        # Look for bullet points or dashes
        lines = week_content.split('\n')
        topics = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                topic = line[1:].strip()
                if topic and len(topic) > 5:  # Filter out very short items
                    topics.append(topic)
        
        return topics[:5]  # Limit to 5 main topics per week
    
    def generate_week_content(self, week_info: Dict, course_context: Dict) -> Dict:
        """Generate detailed content for a specific week with expandable lessons"""
        
        # Generate week overview and objectives first
        overview_prompt = f"""You are Sandwich, an expert AI tutor. Create a week overview and learning objectives for this course week.

    **Course Context:**
    - Topic: {course_context.get('topic', '')}
    - Difficulty: {course_context.get('difficulty', '')}
    - Learning Style: {course_context.get('learner_type', '')}

    **Week Details:**
    - {week_info['title']}
    - Topics to cover: {', '.join(week_info['topics'])}

    Create ONLY:

    1. **📋 Week Overview** (2-3 sentences about what students will learn this week)

    2. **🎯 Learning Objectives** (3-4 specific, measurable goals students will achieve)

    Keep it concise and engaging. This will be the first thing students see."""

        messages = [{"role": "user", "content": overview_prompt}]
        overview_content = self._ask_claude(messages, temperature=0.6, max_tokens=400)
        
        # Generate lesson topics (for sidebar)
        lesson_topics = self._generate_lesson_topics(week_info, course_context)
        
        # Generate activities and resources
        activities_prompt = f"""You are Sandwich, an expert AI tutor. Create hands-on activities for this week.

    **Course Context:**
    - Topic: {course_context.get('topic', '')}
    - Week: {week_info['title']}

    Create:

    🛠️ Hands-on Activities
    Create 3-4 practical, engaging exercises that reinforce the week's learning objectives.

    Make activities appropriate for {course_context.get('difficulty', 'beginner')} level."""

        messages = [{"role": "user", "content": activities_prompt}]
        activities_content = self._ask_claude(messages, temperature=0.6, max_tokens=600)
        
        # Generate additional resources
        resources_prompt = f"""You are Sandwich, an expert AI tutor. Suggest additional resources for this week.

    **Course Context:**
    - Topic: {course_context.get('topic', '')}
    - Week: {week_info['title']}

    🔍 Additional Resources
    Suggest specific types of materials students can explore for deeper understanding:
    - Recommended readings
    - Online tools and websites  
    - Practice exercises
    - Community forums or groups

    Make suggestions appropriate for {course_context.get('difficulty', 'beginner')} level."""

        messages = [{"role": "user", "content": resources_prompt}]
        resources_content = self._ask_claude(messages, temperature=0.6, max_tokens=600)
        
        return {
            "week_number": week_info['week_number'],
            "title": week_info['title'],
            "overview": overview_content,
            "lesson_topics": lesson_topics,  # ✅ This is what frontend expects
            "activities": activities_content,
            "resources": resources_content,
            "completed": False,
            "progress": 0,
            "quiz_completed": False,
            "videos": self._get_youtube_videos(week_info.get('title', ''), course_context, 3)
        }

    def _generate_lesson_topics(self, week_info: Dict, course_context: Dict) -> List[Dict]:
        """Generate lesson topics for sidebar"""
        lessons = []
        
        # Create 3-4 main lesson points from the topics
        lesson_topics = week_info['topics'][:4]  # Max 4 lessons per week
        
        for i, topic in enumerate(lesson_topics):
            # Post-process topic names to avoid quiz-like naming for lessons
            processed_topic = self._process_lesson_title(topic)
            
            lesson = {
                "id": f"lesson_{i+1}",
                "title": processed_topic,
                "summary": f"Learn about {processed_topic.lower()}",
                "expandable": True,
                "loaded": False,
                "completed": False,
                "lesson_info": {
                    "title": processed_topic,
                    "week_title": week_info['title'],
                    "lesson_number": i+1
                }
            }
            lessons.append(lesson)
        
        return lessons

    def _process_lesson_title(self, title: str) -> str:
        """Process lesson titles to avoid quiz-like naming"""
        title_lower = title.lower()
        
        # Replace assessment/quiz-related terms for lessons
        if any(term in title_lower for term in ['final assessment', 'final exam', 'assessment', 'evaluation']):
            # Replace with more appropriate lesson titles
            if 'final' in title_lower:
                return "Course Review & Summary"
            elif 'assessment' in title_lower:
                return "Key Concepts Review"
            elif 'evaluation' in title_lower:
                return "Learning Consolidation"
        
        # Replace other quiz-like terms
        replacements = {
            'quiz': 'Practice',
            'test': 'Review',
            'exam': 'Summary',
            'evaluation': 'Analysis'
        }
        
        processed_title = title
        for old_term, new_term in replacements.items():
            if old_term in title_lower:
                processed_title = processed_title.replace(old_term.title(), new_term)
                processed_title = processed_title.replace(old_term.lower(), new_term.lower())
                processed_title = processed_title.replace(old_term.upper(), new_term.upper())
        
        return processed_title

    def generate_lesson_content(self, lesson_info: Dict, course_context: Dict) -> Dict:
        """Generate detailed content for a specific lesson point"""
        
        content_prompt = f"""You are Sandwich, an expert AI tutor in {course_context.get('topic', 'this subject')}. 

Generate comprehensive content for this specific lesson point:

**Lesson Point:** {lesson_info.get('title', '')}

**Context:**
- Course: {course_context.get('topic', '')}
- Difficulty: {course_context.get('difficulty', 'beginner')}
- Week: {lesson_info.get('week_title', '')}

Create detailed content including:

1. **Detailed Explanation** (3-4 paragraphs explaining the concept clearly)
2. **Key Points** (4-5 bullet points of essential information)  
3. **Real-World Examples** (2-3 practical examples)
4. **Common Mistakes** (2-3 things students often get wrong)
5. **Quick Tips** (2-3 helpful tips for understanding/remembering)

Make it engaging and appropriate for {course_context.get('difficulty', 'beginner')} level students."""

        messages = [{"role": "user", "content": content_prompt}]
        detailed_content = self._ask_claude(messages, temperature=0.6, max_tokens=1000)
        
        return {
            "title": lesson_info.get('title', ''),
            "content": detailed_content,
            "videos": self._get_youtube_videos(lesson_info.get('title', ''), course_context),
            "duration_estimate": "15-20 minutes",
            "difficulty": course_context.get('difficulty', 'beginner')
        }

    def _get_youtube_videos(self, lesson_title: str, course_context: Dict, max_videos: int = 2) -> List[Dict]:
        """Get YouTube videos using API or AI suggestions"""
        
        if self.youtube_api_key:
            return self._search_youtube_api(lesson_title, course_context, max_videos)
        else:
            return self._generate_video_suggestions_ai(lesson_title, course_context, max_videos)

    def _search_youtube_api(self, lesson_title: str, course_context: Dict, max_videos: int) -> List[Dict]:
        """Search YouTube using the actual YouTube Data API"""
        try:
            # Build search query
            topic = course_context.get('topic', '')
            difficulty = course_context.get('difficulty', '')
            
            search_terms = [topic, lesson_title]
            if 'beginner' in difficulty.lower():
                search_terms.append('tutorial basics')
            elif 'advanced' in difficulty.lower():
                search_terms.append('advanced')
                
            query = ' '.join(search_terms)
            
            # YouTube API request
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': max_videos,
                'order': 'relevance',
                'videoDuration': 'medium',  # 4-20 minutes
                'key': self.youtube_api_key
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            videos = []
            if 'items' in data:
                for item in data['items']:
                    videos.append({
                        'title': item['snippet']['title'],
                        'channel': item['snippet']['channelTitle'],
                        'description': item['snippet']['description'][:150] + '...',
                        'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                        'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                        'published': item['snippet']['publishedAt'][:10]
                    })
            
            return videos
            
        except Exception as e:
            logger.error(f"YouTube API error: {str(e)}")
            return self._generate_video_suggestions_ai(lesson_title, course_context, max_videos)

    def _generate_video_suggestions_ai(self, lesson_title: str, course_context: Dict, max_videos: int) -> List[Dict]:
        """Generate realistic YouTube video suggestions using AI"""
        
        prompt = f"""You are an expert at finding educational YouTube videos. For the lesson "{lesson_title}" in {course_context.get('topic', '')}, suggest {max_videos} REAL YouTube videos that actually exist and would be helpful.

For each video, provide:
- **Title:** [Exact video title as it appears on YouTube]
- **Channel:** [Actual channel name - use well-known educational channels]
- **URL:** [Actual YouTube URL if you know it, or realistic search URL]
- **Description:** [Brief description of video content]
- **Duration:** [Realistic duration]

Use channels like: Khan Academy, Crash Course, 3Blue1Brown, Professor Leonard, StatQuest, etc. for educational content.

Format each video clearly separated."""

        messages = [{"role": "user", "content": prompt}]
        response = self._ask_claude(messages, temperature=0.7, max_tokens=400)
        
        return self._parse_video_suggestions(response, lesson_title, course_context)

    def _parse_video_suggestions(self, response: str, lesson_title: str, course_context: Dict) -> List[Dict]:
        """Parse AI-generated video suggestions into structured format"""
        videos = []
        video_blocks = response.split('\n\n')
        
        for block in video_blocks:
            if not block.strip():
                continue
                
            video = {}
            lines = block.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('**Title:**'):
                    video['title'] = line.replace('**Title:**', '').strip()
                elif line.startswith('**Channel:**'):
                    video['channel'] = line.replace('**Channel:**', '').strip()
                elif line.startswith('**URL:**'):
                    url = line.replace('**URL:**', '').strip()
                    if url.startswith('http'):
                        video['url'] = url
                    else:
                        # Create search URL if no direct URL provided
                        search_query = quote_plus(f"{video.get('title', lesson_title)} {course_context.get('topic', '')}")
                        video['url'] = f"https://www.youtube.com/results?search_query={search_query}"
                elif line.startswith('**Description:**'):
                    video['description'] = line.replace('**Description:**', '').strip()
                elif line.startswith('**Duration:**'):
                    video['duration'] = line.replace('**Duration:**', '').strip()
            
            if video.get('title'):
                videos.append(video)
                
            if len(videos) >= 2:  # Limit to 2 videos
                break
        
        return videos

    def _suggest_youtube_videos(self, week_info: Dict, course_context: Dict) -> List[Dict]:
        """Suggest relevant YouTube videos for the week (legacy method)"""
        # This method exists for backward compatibility
        return self._get_youtube_videos(week_info.get('title', ''), course_context, 3)
    
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
                    "available": week["week_number"] <= current_week + 1
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


# Standalone helper function
def initialize_course_from_syllabus(syllabus_text: str, course_context: Dict) -> Dict:
    """Initialize a complete course structure from syllabus text"""
    logger.info(f"Initializing course from syllabus (length: {len(syllabus_text)})")
    
    generator = SyllabusGenerator()
    
    # Parse the syllabus into weeks
    weeks = generator.parse_course_structure(syllabus_text)
    logger.info(f"Parsed {len(weeks)} weeks from syllabus")
    
    if not weeks:
        logger.warning("No weeks found, creating fallback structure")
        # Create a fallback single week if parsing fails
        weeks = [{
            "week_number": 1,
            "title": "Week 1: Course Introduction",
            "content": syllabus_text[:1000] + "..." if len(syllabus_text) > 1000 else syllabus_text,
            "topics": [f"Introduction to {course_context.get('topic', 'the subject')}", "Core concepts", "Getting started"],
            "completed": False
        }]
    
    # Generate detailed content for each week
    detailed_weeks = []
    for week in weeks:
        logger.info(f"Generating detailed content for week {week['week_number']}")
        detailed_week = generator.generate_week_content(week, course_context)
        detailed_weeks.append(detailed_week)
    
    # Get course navigation
    navigation = generator.get_course_navigation(detailed_weeks, 1)
    
    # Get course summary
    summary = generator.get_course_summary(detailed_weeks, course_context)
    
    logger.info(f"Course initialization complete with {len(detailed_weeks)} weeks")
    
    return {
        "weeks": detailed_weeks,
        "navigation": navigation,
        "summary": summary,
        "course_context": course_context
    }
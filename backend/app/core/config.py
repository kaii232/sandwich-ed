import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Debug logging
logger = logging.getLogger(__name__)
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Debug output
print(f"🔍 DEBUG - AWS_ACCESS_KEY_ID loaded: {AWS_ACCESS_KEY_ID[:10] if AWS_ACCESS_KEY_ID else 'None'}...")
print(f"🔍 DEBUG - AWS_SECRET_ACCESS_KEY loaded: {'Yes' if AWS_SECRET_ACCESS_KEY else 'No'}")
print(f"🔍 DEBUG - AWS_REGION: {AWS_REGION}")

ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*").split(",")
COURSE_DATA_FILE = os.getenv("COURSE_DATA_FILE", "progressive_course_data.json")
WELLBEING_DATA_FILE = os.getenv("WELLBEING_DATA_FILE", "wellbeing_checks.json")

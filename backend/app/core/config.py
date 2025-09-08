import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*").split(",")
COURSE_DATA_FILE = os.getenv("COURSE_DATA_FILE", "progressive_course_data.json")
WELLBEING_DATA_FILE = os.getenv("WELLBEING_DATA_FILE", "wellbeing_checks.json")

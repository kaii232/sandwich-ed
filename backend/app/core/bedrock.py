import json
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from .config import AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

log = logging.getLogger(__name__)

def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

_client = get_bedrock_client()

def ask_claude(messages: list, temperature: float = 0.7, max_tokens: int = 800, system: str | None = None) -> str:
    try:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,  # ONLY user/assistant roles here
        }
        if system:
            body["system"] = system  # <-- top-level system, per Anthropic Messages API

        resp = _client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(body)
        )
        data = json.loads(resp["body"].read())
        return data["content"][0]["text"].strip()
    except (ClientError, BotoCoreError) as e:
        log.error(f"AWS Bedrock error: {e}")
        return "I'm having trouble connecting to my AI service. Please try again in a moment."
    except Exception as e:
        log.error(f"Unexpected error in ask_claude: {e}")
        return "I encountered an unexpected error. Please try again."

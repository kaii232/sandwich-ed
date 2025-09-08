import os, json, time, random
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from threading import BoundedSemaphore
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Limit concurrent InvokeModel calls (tune via env)
_MAX_CONCURRENCY = int(os.getenv("BEDROCK_MAX_CONCURRENCY", "2"))
_GATE = BoundedSemaphore(_MAX_CONCURRENCY)

_cfg = Config(
    retries={"max_attempts": 10, "mode": "adaptive"},
    connect_timeout=3,
    read_timeout=60,
)

_client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1")),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=_cfg,
    # Credentials: loaded from .env file
)

def _sleep_backoff(attempt: int, base: float = 0.6, cap: float = 8.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1)))
    time.sleep(random.uniform(0, delay))  # full jitter

def invoke_claude_json(
    *,
    model_id: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.5,
    max_tokens: int = 600,
    top_p: float = 0.9,
    max_attempts: int = 8,
) -> str:
    """Robust InvokeModel with retries, returns plain text."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
    }

    with _GATE:  # concurrency guard
        for attempt in range(1, max_attempts + 1):
            try:
                resp = _client.invoke_model(
                    modelId=model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )
                payload = json.loads(resp["body"].read())
                # Bedrock Claude returns content blocks
                if "content" in payload:
                    parts = payload["content"]
                    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                    return text.strip()
                # Fallbacks if shape changes
                return (
                    payload.get("output_text")
                    or payload.get("completion")
                    or ""
                ).strip()
            except (ClientError, BotoCoreError) as e:
                code = getattr(e, "response", {}).get("Error", {}).get("Code")
                status = getattr(e, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
                retriable = code in {"ThrottlingException", "TooManyRequestsException"} or status in {429, 500, 502, 503, 504}
                if attempt < max_attempts and retriable:
                    _sleep_backoff(attempt)
                    continue
                raise

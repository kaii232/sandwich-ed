import json, os, re
from datetime import datetime, timezone
from typing import Dict, Any
from app.core.config import WELLBEING_DATA_FILE

CRISIS_TERMS = [
    r"\bsuicid", r"\bkill myself\b", r"\bharm myself\b", r"\bend my life\b",
    r"\bno reason to live\b", r"\bself[-\s]?harm\b"
]

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load() -> list[Dict[str, Any]]:
    if os.path.exists(WELLBEING_DATA_FILE):
        try:
            with open(WELLBEING_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save(rows: list[Dict[str, Any]]) -> None:
    with open(WELLBEING_DATA_FILE, "w") as f:
        json.dump(rows, f, indent=2)

def score_check(mood: int, phq2: list[int] | None, gad2: list[int] | None, free_text: str | None):
    phq = sum(phq2 or [])
    gad = sum(gad2 or [])
    text = (free_text or "").lower().strip()

    crisis = any(re.search(pat, text) for pat in CRISIS_TERMS)
    # Basic stratification (conservative)
    if crisis:
        risk = "urgent"
        msg = ("I'm concerned about your safety. If you’re in danger or thinking about harming yourself, "
               "please contact local emergency services immediately and reach out to a trusted person or a crisis helpline.")
        show = True
    elif phq >= 5 or gad >= 5 or mood <= 1:
        risk = "elevated"
        msg = ("Thanks for sharing. It looks like things are heavy right now. "
               "Consider taking a short break, and if you can, talk to someone you trust. "
               "If the feelings persist, seeking professional support can help.")
        show = True
    elif phq >= 3 or gad >= 3 or mood == 2:
        risk = "watch"
        msg = ("Noted. Let's keep an eye on how you're feeling. "
               "We can lighten your learning plan for a bit and add more gentle practice.")
        show = False
    else:
        risk = "low"
        msg = ("Great—thanks for checking in. We’ll keep the current learning pace. "
               "Remember you can pause or switch to lighter activities anytime.")
        show = False

    return phq, gad, risk, msg, show

def record_check(payload: dict) -> dict:
    mood = int(payload.get("mood", 3))
    phq2 = payload.get("phq2") or []
    gad2 = payload.get("gad2") or []
    free_text = payload.get("free_text") or ""

    phq_total, gad_total, risk, message, show_resources = score_check(mood, phq2, gad2, free_text)
    row = {
        "timestamp": _now_iso(),
        "mood": mood,
        "phq2_total": phq_total,
        "gad2_total": gad_total,
        "risk": risk,
        "free_text_present": bool(free_text.strip())
    }
    rows = _load()
    rows.append(row)
    _save(rows)

    return {
        "timestamp": row["timestamp"],
        "mood": mood,
        "phq2_total": phq_total,
        "gad2_total": gad_total,
        "risk": risk,
        "message": message,
        "show_resources": show_resources
    }

def last_check() -> dict | None:
    rows = _load()
    return rows[-1] if rows else None

"""Phase 3: Input and output guardrails.

Input guardrails: Block prompt injection, jailbreak attempts, harmful content.
Output guardrails: Filter PII, hallucinations, off-topic responses.
"""

import re
from app.utils.logger import get_logger

logger = get_logger("guardrails")

# ============ Input Guardrails ============

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(everything|all|your)\s+(instructions|rules|guidelines)",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if|though)\s+you",
    r"pretend\s+(you\s+are|to\s+be)",
    r"new\s+instruction[s]?:",
    r"system\s*prompt\s*:",
    r"<\s*system\s*>",
    r"jailbreak",
    r"DAN\s+mode",
]

HARMFUL_PATTERNS = [
    r"how\s+to\s+(make|build|create)\s+(a\s+)?(bomb|weapon|explosive)",
    r"how\s+to\s+(hack|break\s+into)",
    r"generate\s+(fake|forged)\s+(id|document|passport)",
]

COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
COMPILED_HARMFUL = [re.compile(p, re.IGNORECASE) for p in HARMFUL_PATTERNS]


async def check_input(message: str) -> tuple[bool, str]:
    """Check user input for injection attempts and harmful content.

    Returns (is_blocked, reason).
    """
    # Check prompt injection
    for pattern in COMPILED_INJECTION:
        if pattern.search(message):
            logger.warning(f"Injection detected: {message[:100]}")
            return True, "prompt_injection"

    # Check harmful content
    for pattern in COMPILED_HARMFUL:
        if pattern.search(message):
            logger.warning(f"Harmful content detected: {message[:100]}")
            return True, "harmful_content"

    # Check message length (DoS prevention)
    if len(message) > 4000:
        return True, "message_too_long"

    return False, ""


# ============ Output Guardrails ============

PII_PATTERNS = {
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "phone": re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "card_number": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    # Requires "account"/"a/c"/"acct" context so we don't redact order IDs,
    # tracking numbers, or long random digits that aren't bank accounts.
    "account_number": re.compile(
        r"\b(?:a/?c|acct|account)(?:\s*(?:no\.?|number|#))?[:\s]*\d{9,18}\b",
        re.IGNORECASE,
    ),
}

SECTOR_BLOCKED_PHRASES = {
    "medical": [
        "you should take",
        "i diagnose",
        "i recommend taking",
        "your diagnosis is",
        "you have (a |the )?disease",
    ],
    "banking": [
        "your password is",
        "your otp is",
        "your pin is",
        "invest in",
        "guaranteed returns",
    ],
}


async def check_output(response: str, sector: str) -> tuple[str, bool]:
    """Filter the LLM response for PII and sector-specific violations.

    Returns (filtered_response, was_filtered).
    """
    filtered = response
    was_filtered = False

    # Mask PII
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(filtered):
            filtered = pattern.sub(f"[{pii_type.upper()}_REDACTED]", filtered)
            was_filtered = True
            logger.warning(f"PII filtered: {pii_type}")

    # Check sector-specific blocked phrases
    blocked = SECTOR_BLOCKED_PHRASES.get(sector, [])
    for phrase in blocked:
        if re.search(phrase, filtered, re.IGNORECASE):
            logger.warning(f"Blocked phrase in {sector}: {phrase}")
            filtered = (
                "I'm sorry, I can't provide that type of information. "
                "Please consult with a qualified professional for specific advice."
            )
            was_filtered = True
            break

    return filtered, was_filtered

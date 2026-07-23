"""Phase 2: Intent classification using the base LLM.

The LLM reads the user message and classifies it into a known intent
for the given sector. No separate model needed — the same Gemma/Qwen
model handles this via a structured prompt.
"""

import json
from app.services.llm_client import llm_client
from app.models.schemas import IntentResult
from app.utils.logger import get_logger

logger = get_logger("intent")

# Intent definitions per sector
SECTOR_INTENTS = {
    "retail": [
        {"intent": "order_tracking", "description": "User wants to track an order or check delivery status"},
        {"intent": "refund_request", "description": "User wants a refund for an order"},
        {"intent": "return_request", "description": "User wants to return a product"},
        {"intent": "product_inquiry", "description": "User asks about a product's features, price, or availability"},
        {"intent": "payment_issue", "description": "User has a payment or billing problem"},
        {"intent": "complaint", "description": "User is unhappy and wants to file a complaint"},
        {"intent": "general_query", "description": "General question that doesn't fit other intents"},
    ],
    "education": [
        {"intent": "course_info", "description": "User asks about courses, programs, or curriculum"},
        {"intent": "admission_process", "description": "User asks about how to apply or admission steps"},
        {"intent": "fee_inquiry", "description": "User asks about fees, payment plans, or scholarships"},
        {"intent": "exam_schedule", "description": "User asks about exam dates, results, or preparation"},
        {"intent": "placement_query", "description": "User asks about job placement or career support"},
        {"intent": "campus_facilities", "description": "User asks about hostel, library, or campus amenities"},
        {"intent": "general_query", "description": "General question that doesn't fit other intents"},
    ],
    "medical": [
        {"intent": "book_appointment", "description": "User wants to book a doctor appointment"},
        {"intent": "doctor_availability", "description": "User asks which doctors are available"},
        {"intent": "report_collection", "description": "User asks about test results or report status"},
        {"intent": "department_info", "description": "User asks about hospital departments or services"},
        {"intent": "visiting_hours", "description": "User asks about hospital visiting hours or rules"},
        {"intent": "health_package", "description": "User asks about health checkup packages"},
        {"intent": "emergency", "description": "User describes an urgent medical situation"},
        {"intent": "general_query", "description": "General question that doesn't fit other intents"},
    ],
    "real_estate": [
        {"intent": "property_search", "description": "User wants to find properties matching criteria"},
        {"intent": "site_visit", "description": "User wants to schedule a property visit"},
        {"intent": "emi_calculation", "description": "User wants EMI or loan estimates"},
        {"intent": "document_checklist", "description": "User asks about required documents for purchase"},
        {"intent": "locality_info", "description": "User asks about a neighborhood or area"},
        {"intent": "builder_info", "description": "User asks about a builder's reputation or projects"},
        {"intent": "general_query", "description": "General question that doesn't fit other intents"},
    ],
    "banking": [
        {"intent": "account_inquiry", "description": "User asks about their account balance or details"},
        {"intent": "loan_eligibility", "description": "User wants to check loan eligibility or apply"},
        {"intent": "emi_calculation", "description": "User wants EMI calculations for a loan"},
        {"intent": "credit_card", "description": "User has credit card related queries"},
        {"intent": "kyc_status", "description": "User asks about KYC verification status"},
        {"intent": "transaction_dispute", "description": "User disputes a transaction or reports fraud"},
        {"intent": "fd_rates", "description": "User asks about fixed deposit interest rates"},
        {"intent": "branch_locator", "description": "User wants to find a branch or ATM"},
        {"intent": "general_query", "description": "General question that doesn't fit other intents"},
    ],
    "tourism": [
        {"intent": "itinerary_planning", "description": "User wants help planning a trip itinerary"},
        {"intent": "hotel_recommendation", "description": "User wants hotel or accommodation suggestions"},
        {"intent": "transport_info", "description": "User asks about flights, trains, or local transport"},
        {"intent": "visa_guidance", "description": "User asks about visa requirements or process"},
        {"intent": "travel_package", "description": "User asks about pre-made travel packages"},
        {"intent": "local_attractions", "description": "User asks about things to do or see at a destination"},
        {"intent": "budget_estimate", "description": "User wants cost estimates for a trip"},
        {"intent": "general_query", "description": "General question that doesn't fit other intents"},
    ],
}

CLASSIFICATION_PROMPT = """You are an intent classifier. Given a user message and a list of possible intents, classify the message into the most appropriate intent.

INTENTS:
{intents_list}

USER MESSAGE: "{message}"

Respond ONLY with a JSON object in this exact format, nothing else:
{{"intent": "<intent_name>", "confidence": <0.0-1.0>, "params": {{}}}}

If the user mentions specific entities (order ID, date, doctor name, location, amount), extract them into the "params" dict.

Examples:
- "Where is my order #12345?" -> {{"intent": "order_tracking", "confidence": 0.95, "params": {{"order_id": "12345"}}}}
- "I want to book an appointment with Dr. Sharma" -> {{"intent": "book_appointment", "confidence": 0.92, "params": {{"doctor_name": "Dr. Sharma"}}}}
"""


async def classify_intent(message: str, sector: str) -> IntentResult:
    """Classify user message into a sector-specific intent."""

    intents = SECTOR_INTENTS.get(sector, SECTOR_INTENTS["retail"])
    intents_text = "\n".join(
        f"- {i['intent']}: {i['description']}" for i in intents
    )

    prompt = CLASSIFICATION_PROMPT.format(
        intents_list=intents_text,
        message=message,
    )

    raw = ""
    try:
        result = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,  # Low temp for consistent classification
        )

        raw = result["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        intent_result = IntentResult(
            intent=parsed.get("intent", "general_query"),
            confidence=min(max(parsed.get("confidence", 0.5), 0.0), 1.0),
            sector=sector,
            params=parsed.get("params", {}),
        )
        logger.info(
            f"intent={intent_result.intent} conf={intent_result.confidence} sector={sector}",
            extra={
                "sector": sector,
                "user_message": message,
                "intent": intent_result.intent,
                "confidence": intent_result.confidence,
                "params": intent_result.params,
            },
        )
        return intent_result

    # Classification is advisory — never let it take the request down. A dead
    # LLM (auth error, timeout) must fall through to the guarded generation
    # call in the chat router, which escalates properly instead of 500-ing.
    except Exception as e:
        logger.warning(
            f"Intent classification failed: {type(e).__name__}: {e}, raw: {raw[:100]}",
            extra={
                "sector": sector,
                "user_message": message,
                "raw_llm_output": raw,
                "error": str(e),
            },
        )
        return IntentResult(
            intent="general_query",
            confidence=0.3,
            sector=sector,
            params={},
        )


def get_intents_for_sector(sector: str) -> list[dict]:
    """Return available intents for a sector."""
    return SECTOR_INTENTS.get(sector, [])

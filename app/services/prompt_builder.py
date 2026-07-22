"""Phase 2: Prompt builder.

Assembles the final prompt from:
1. System prompt (sector persona)
2. Domain context (intent-specific instructions)
3. Memory (conversation history)
4. RAG context (retrieved documents)
"""

from app.prompts.base_system import get_system_prompt
from app.models.schemas import IntentResult
from app.services.rag_retriever import RAGResult
from app.utils.logger import get_logger

logger = get_logger("prompt")

# Prepended to every persona so replies are consistently short and direct.
BREVITY_RULE = (
    "RESPONSE STYLE:\n"
    "- Reply in ONE to THREE short sentences. Under 60 words.\n"
    "- Skip greetings, apologies, and filler like 'I understand'.\n"
    "- Answer the user's question directly; ask ONE follow-up if needed.\n"
    "- No bullet lists unless the user asks for one."
)


def build_prompt(
    sector: str,
    intent: IntentResult | None = None,
    rag_context: RAGResult | None = None,
    memory: list[dict] | None = None,
) -> str:
    """Build the complete system prompt for the LLM.

    Combines all context sources into one coherent system prompt.
    The conversation history (memory) goes into the messages array,
    not into the system prompt itself.
    """

    parts = []

    # 0. Global brevity rule — enforced across every persona.
    parts.append(BREVITY_RULE)

    # 1. Base sector system prompt
    parts.append(get_system_prompt(sector))

    # 2. Intent-specific instructions
    if intent and intent.intent != "general_query":
        intent_instruction = _get_intent_instruction(sector, intent)
        if intent_instruction:
            parts.append(f"\nCURRENT TASK: {intent_instruction}")

        # Add extracted parameters
        if intent.params:
            params_str = ", ".join(f"{k}: {v}" for k, v in intent.params.items())
            parts.append(f"EXTRACTED INFO: {params_str}")

    # 3. RAG context
    if rag_context and rag_context.chunks:
        context_text = "\n---\n".join(rag_context.chunks[:3])  # Max 3 chunks
        parts.append(
            f"\nRELEVANT INFORMATION FROM KNOWLEDGE BASE:\n{context_text}\n"
            "Use the above information to answer the user's question. "
            "If the information doesn't fully answer the question, say so."
        )

    # 4. Conversation context hint
    if memory and len(memory) > 0:
        turn_count = len(memory) // 2
        parts.append(
            f"\nCONVERSATION CONTEXT: This is turn {turn_count + 1} of an ongoing conversation. "
            "Refer to previous context when relevant but don't repeat yourself."
        )

    return "\n\n".join(parts)


def _get_intent_instruction(sector: str, intent: IntentResult) -> str:
    """Get specific instructions for handling a detected intent."""

    INTENT_INSTRUCTIONS = {
        "retail": {
            "order_tracking": "The customer wants to track an order. Ask for order ID if not provided, then give a status update.",
            "refund_request": "The customer wants a refund. Confirm the order details, explain the 5-7 business day refund timeline, and ask for preferred refund method.",
            "return_request": "The customer wants to return a product. Confirm the order, check if within 15-day return window, and explain the return pickup process.",
            "product_inquiry": "The customer is asking about a product. Provide details about features, pricing, and availability.",
            "payment_issue": "The customer has a payment problem. Ask for transaction details and offer troubleshooting steps.",
            "complaint": "The customer is unhappy. Acknowledge their frustration sincerely, apologize, and offer a concrete resolution.",
        },
        "medical": {
            "book_appointment": "Help the patient book an appointment. Ask for preferred department/doctor, date, and time slot.",
            "doctor_availability": "Provide doctor schedule information. List available slots for the requested department.",
            "report_collection": "The patient wants their test reports. Ask for the test date and patient ID, then provide collection instructions.",
            "emergency": "THIS IS URGENT. Immediately provide the emergency helpline number and direct to the nearest ER. Do not ask unnecessary questions.",
            "health_package": "Provide information about available health checkup packages with pricing and what's included.",
        },
        "banking": {
            "loan_eligibility": "Help the customer check loan eligibility. Ask for loan type, amount, income, and employment details.",
            "emi_calculation": "Calculate EMI for the customer. Ask for loan amount, tenure, and use 8.5% default interest rate.",
            "transaction_dispute": "The customer is disputing a transaction. Collect transaction date, amount, merchant name. Provide the dispute resolution timeline (7-10 working days).",
            "credit_card": "Handle credit card query. Could be about application, billing, rewards, or blocking a lost card.",
        },
        "education": {
            "course_info": "Provide detailed information about the requested course or program.",
            "admission_process": "Walk the student through the admission process step by step.",
            "fee_inquiry": "Provide fee structure and available payment plans or scholarships.",
        },
        "real_estate": {
            "property_search": "Help find properties. Ask for budget, location preference, and property type.",
            "site_visit": "Schedule a property visit. Collect name, phone, preferred date/time.",
            "emi_calculation": "Calculate home loan EMI. Ask for property value, down payment, and preferred tenure.",
        },
        "tourism": {
            "itinerary_planning": "Help plan a trip. Ask for destination, duration, budget, and travel style.",
            "hotel_recommendation": "Suggest hotels. Ask for destination, budget range, and preferences (luxury/budget/family).",
            "visa_guidance": "Provide visa requirements. Ask for destination country and passport nationality.",
        },
    }

    sector_intents = INTENT_INSTRUCTIONS.get(sector, {})
    return sector_intents.get(intent.intent, "")

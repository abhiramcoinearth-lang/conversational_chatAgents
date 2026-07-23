import time
from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services.llm_client import llm_client
from app.utils.helpers import generate_session_id, sanitize_input
from app.utils.logger import get_logger

from app.services.intent_classifier import classify_intent
from app.services.rag_retriever import rag_retriever
from app.services.prompt_builder import build_prompt, BREVITY_RULE
from app.services.memory_manager import memory_manager
from app.services.guardrails import check_input, check_output
from app.services.escalation import should_escalate, get_escalation_message
from app.services.translator import to_english, from_english
from app.services.queue_manager import queue_manager
from app.models.db_session import save_conversation_log

logger = get_logger("chat")
router = APIRouter(prefix="/api", tags=["chat"])


async def _finalize(
    *,
    start_time: float,
    session_id: str,
    sector: str,
    tenant_id: str | None,
    src_lang: str,
    user_lang: str,
    user_message_original: str,
    user_message: str,
    bot_reply: str,
    bot_reply_translated: str,
    intent_result=None,
    rag_context=None,
    result: dict | None = None,
    escalated: bool = False,
    write_memory: bool = True,
) -> ChatResponse:
    """Log + persist + build the response. Called from every chat exit path."""
    latency = round((time.time() - start_time) * 1000, 2)
    tokens = (result or {}).get("tokens_used", 0)
    rag_chunks_count = rag_context.total_chunks if rag_context else 0
    intent_str = intent_result.intent if intent_result else None
    confidence = intent_result.confidence if intent_result else None

    if write_memory and bot_reply:
        await memory_manager.add_turn(session_id, user_message, bot_reply)

    display_out = bot_reply_translated or bot_reply
    logger.info(
        f"[{session_id}] in={user_message[:120]} | out={display_out[:120]} | "
        f"latency={latency}ms tokens={tokens} escalated={escalated}",
        extra={
            "session_id": session_id,
            "sector": sector,
            "tenant_id": tenant_id,
            "src_lang": src_lang,
            "tgt_lang": user_lang,
            "input_original": user_message_original,
            "input": user_message,
            "output": bot_reply,
            "output_translated": bot_reply_translated,
            "intent": intent_str,
            "confidence": confidence,
            "latency_ms": latency,
            "tokens_used": tokens,
            "rag_chunks": rag_chunks_count,
            "escalated": escalated,
        },
    )

    await save_conversation_log(
        session_id=session_id,
        tenant_id=tenant_id,
        sector=sector,
        user_message=user_message,
        bot_reply=bot_reply or bot_reply_translated,
        intent=intent_str,
        confidence=confidence,
        latency_ms=latency,
        tokens_used=tokens,
        rag_chunks=rag_chunks_count,
        escalated=escalated,
    )

    return ChatResponse(
        reply=bot_reply_translated or bot_reply,
        session_id=session_id,
        intent=intent_str,
        confidence=confidence,
        sources=rag_context.sources if rag_context and rag_context.chunks else None,
        escalated=escalated,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()

    user_message_original = sanitize_input(request.message)
    session_id = request.session_id or generate_session_id()
    sector = request.sector
    src_lang = request.src_lang
    user_lang = request.lang
    tenant_id = request.tenant_id

    # Translate input ONLY when the user explicitly picked a specific non-English
    # source language. "auto" means "let the LLM handle whatever the user typed"
    # — Gemini is multilingual and doesn't need English pre-translation.
    if src_lang.upper() in ("ENGLISH", "AUTO"):
        user_message = user_message_original
    else:
        user_message = await to_english(user_message_original, src_lang=src_lang)

    logger.info(
        f"[{session_id}] sector={sector} src={src_lang} tgt={user_lang} msg={user_message[:80]}..."
    )

    # Input guardrails
    blocked, reason = await check_input(user_message)
    if blocked:
        logger.warning(f"[{session_id}] Input blocked: {reason}")
        reply_en = "I'm sorry, I can't process that request. Please rephrase your question."
        reply_translated = await from_english(reply_en, user_lang)
        return await _finalize(
            start_time=start_time, session_id=session_id, sector=sector,
            tenant_id=tenant_id, src_lang=src_lang, user_lang=user_lang,
            user_message_original=user_message_original, user_message=user_message,
            bot_reply=reply_en, bot_reply_translated=reply_translated,
            escalated=True, write_memory=False,
        )

    is_custom = sector.startswith("custom_")
    intent_result = None

    # Session history
    history = await memory_manager.get_history(session_id)

    # RAG runs for BOTH built-in sectors AND custom personas
    rag_context = await rag_retriever.retrieve(user_message, sector)

    if is_custom:
        from app.routers.persona import personas
        persona = personas.get(sector)
        if not persona:
            raise HTTPException(404, "Custom persona not found")
        # Brevity rule first, then persona prompt, then RAG context (if any).
        parts = [BREVITY_RULE, persona["prompt"]]
        if rag_context and rag_context.chunks:
            ctx_text = "\n---\n".join(rag_context.chunks[:3])
            parts.append(
                f"\nRELEVANT INFORMATION FROM KNOWLEDGE BASE:\n{ctx_text}\n"
                "Use the above information to answer the user's question."
            )
        system_prompt = "\n\n".join(parts)
    else:
        intent_result = await classify_intent(user_message, sector)
        logger.info(f"[{session_id}] intent={intent_result.intent} conf={intent_result.confidence}")
        system_prompt = build_prompt(
            sector=sector, intent=intent_result,
            rag_context=rag_context, memory=history,
        )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # LLM generation — guarded by concurrency semaphore
    slot_ok = await queue_manager.acquire(session_id, timeout=30.0)
    if not slot_ok:
        reply_en = "The service is busy right now. Please try again in a moment."
        reply_translated = await from_english(reply_en, user_lang)
        return await _finalize(
            start_time=start_time, session_id=session_id, sector=sector,
            tenant_id=tenant_id, src_lang=src_lang, user_lang=user_lang,
            user_message_original=user_message_original, user_message=user_message,
            bot_reply=reply_en, bot_reply_translated=reply_translated,
            intent_result=intent_result, rag_context=rag_context,
            escalated=True, write_memory=False,
        )

    try:
        try:
            result = await llm_client.chat_completion(
                messages=messages, max_tokens=220, temperature=0.7,
            )
            bot_reply = result["text"]
        except Exception as e:
            logger.error(f"[{session_id}] LLM error: {e}")
            if should_escalate(error=e):
                reply_en = "Technical difficulties. Connecting you with a human agent."
                reply_translated = await from_english(reply_en, user_lang)
                return await _finalize(
                    start_time=start_time, session_id=session_id, sector=sector,
                    tenant_id=tenant_id, src_lang=src_lang, user_lang=user_lang,
                    user_message_original=user_message_original, user_message=user_message,
                    bot_reply=reply_en, bot_reply_translated=reply_translated,
                    intent_result=intent_result, rag_context=rag_context,
                    escalated=True, write_memory=False,
                )
            raise HTTPException(status_code=503, detail="LLM service unavailable")
    finally:
        queue_manager.release(session_id)

    # Intent-based escalation for built-in sectors
    if not is_custom and intent_result and should_escalate(intent=intent_result):
        reply_en = get_escalation_message(sector)
        reply_translated = await from_english(reply_en, user_lang)
        return await _finalize(
            start_time=start_time, session_id=session_id, sector=sector,
            tenant_id=tenant_id, src_lang=src_lang, user_lang=user_lang,
            user_message_original=user_message_original, user_message=user_message,
            bot_reply=reply_en, bot_reply_translated=reply_translated,
            intent_result=intent_result, rag_context=rag_context, result=result,
            escalated=True, write_memory=False,
        )

    # Output guardrails on the English reply
    bot_reply, was_filtered = await check_output(bot_reply, sector if not is_custom else "custom")
    if was_filtered:
        logger.warning(f"[{session_id}] Output filtered")

    bot_reply_translated = await from_english(bot_reply, user_lang)

    return await _finalize(
        start_time=start_time, session_id=session_id, sector=sector,
        tenant_id=tenant_id, src_lang=src_lang, user_lang=user_lang,
        user_message_original=user_message_original, user_message=user_message,
        bot_reply=bot_reply, bot_reply_translated=bot_reply_translated,
        intent_result=intent_result, rag_context=rag_context, result=result,
        escalated=False,
    )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    await memory_manager.clear(session_id)
    return {"status": "cleared", "session_id": session_id}

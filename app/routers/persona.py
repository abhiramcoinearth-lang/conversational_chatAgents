import json
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.schemas import ChatRequest, ChatResponse
from app.services.llm_client import llm_client
from app.utils.logger import get_logger

logger = get_logger("persona")
router = APIRouter(prefix="/api/persona", tags=["persona"])

personas: dict[str, dict] = {}


class PersonaCreate(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=2000)
    name: str = Field(default="", max_length=100)


class PersonaResponse(BaseModel):
    persona_id: str
    name: str
    agent_name: str
    company: str
    description: str
    services: list[dict]
    prompt: str


EXTRACT_PROMPT = """You are a JSON extractor. Given a system prompt for a conversational AI agent, extract the following fields.

SYSTEM PROMPT:
\"\"\"
{prompt}
\"\"\"

Respond ONLY with a valid JSON object, nothing else:
{{
  "agent_name": "<name of the agent persona>",
  "company": "<company or organization name>",
  "description": "<one line description, max 100 chars>",
  "services": ["<service 1>", "<service 2>", "<service 3>", "<service 4>", "<service 5>", "<service 6>"],
  "highlight_services": [0, 3]
}}

Rules:
- Extract 4-8 services that this agent can handle
- highlight_services are indices of the 2 most important services
- If agent_name is not mentioned, create a suitable name
- If company is not mentioned, use "AI Assistant"
"""


@router.post("/create", response_model=PersonaResponse)
async def create_persona(data: PersonaCreate):
    prompt_text = data.prompt.strip()

    extract_prompt = EXTRACT_PROMPT.format(prompt=prompt_text)

    try:
        result = await llm_client.chat_completion(
            messages=[{"role": "user", "content": extract_prompt}],
            max_tokens=500,
            temperature=0.1,
        )

        raw = result["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        extracted = json.loads(raw)

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Extraction failed: {e}")
        extracted = {
            "agent_name": data.name or "Assistant",
            "company": "AI Assistant",
            "description": "Custom AI assistant",
            "services": ["General Query", "Help", "Support"],
            "highlight_services": [0],
        }

    persona_id = f"custom_{uuid.uuid4().hex[:8]}"

    highlights = extracted.get("highlight_services", [0])
    services = []
    for i, svc in enumerate(extracted.get("services", [])):
        services.append({
            "t": svc,
            "h": 1 if i in highlights else 0,
        })

    persona = {
        "persona_id": persona_id,
        "name": data.name or extracted.get("company", "Custom Agent"),
        "agent_name": extracted.get("agent_name", "Assistant"),
        "company": extracted.get("company", "AI Assistant"),
        "description": extracted.get("description", "Custom AI assistant"),
        "services": services,
        "prompt": prompt_text,
    }

    personas[persona_id] = persona
    logger.info(f"Persona created: {persona_id} agent={persona['agent_name']} company={persona['company']}")

    return PersonaResponse(**persona)


@router.get("/list")
async def list_personas():
    return {"personas": list(personas.values()), "total": len(personas)}


@router.get("/{persona_id}")
async def get_persona(persona_id: str):
    if persona_id not in personas:
        raise HTTPException(404, "Persona not found")
    return personas[persona_id]


@router.delete("/{persona_id}")
async def delete_persona(persona_id: str):
    if persona_id not in personas:
        raise HTTPException(404, "Persona not found")
    del personas[persona_id]
    return {"status": "deleted", "persona_id": persona_id}


class PersonaChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    src_lang: str = Field(default="auto")
    lang: str = Field(default="ENGLISH")


@router.post("/{persona_id}/chat", response_model=ChatResponse)
async def persona_chat(persona_id: str, data: PersonaChatRequest):
    """Chat directly with a custom persona.

    Simpler alternative to POST /api/chat for websites embedding a specific
    persona — the sector is implicit from the URL, so callers only send the
    message and (optionally) session/language fields.
    """
    if persona_id not in personas:
        raise HTTPException(404, "Persona not found")

    from app.routers.chat import chat as chat_handler

    return await chat_handler(ChatRequest(
        message=data.message,
        session_id=data.session_id,
        sector=persona_id,
        tenant_id=data.tenant_id,
        src_lang=data.src_lang,
        lang=data.lang,
    ))

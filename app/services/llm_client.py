"""Google Gemini LLM client.

Uses the native REST API (generateContent). The client keeps the same
public shape as before (chat_completion / generate / health_check) so the
rest of the pipeline — translator, RAG, guardrails, memory — needs no
changes.
"""

import time
import httpx
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("llm")


class LLMClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.gemini_base_url.rstrip("/")
        self.model = self.settings.gemini_model
        self.api_key = self.settings.gemini_api_key

    # ---------- internal helpers ----------

    def _headers(self) -> dict:
        # x-goog-api-key keeps the key out of URLs (and out of logs).
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def _to_gemini_payload(self, messages: list[dict], max_tokens: int, temperature: float) -> dict:
        """Convert OpenAI-style messages into a Gemini generateContent payload."""
        system_texts = []
        contents = []
        for m in messages:
            role = m.get("role")
            text = m.get("content", "")
            if not text:
                continue
            if role == "system":
                system_texts.append(text)
            elif role in ("user", "assistant"):
                contents.append({
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": text}],
                })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_texts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_texts)}]}
        return payload

    def _parse_response(self, data: dict) -> tuple[str, int]:
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError):
            logger.warning(f"Unexpected Gemini response shape: {str(data)[:300]}")
            text = ""
        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        return text, tokens

    # ---------- public API ----------

    async def chat_completion(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict:
        start = time.time()
        payload = self._to_gemini_payload(messages, max_tokens, temperature)

        system_msg = next((m for m in messages if m.get("role") == "system"), {})
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        url = f"{self.base_url}/models/{self.model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            logger.error(
                f"Gemini generateContent failed after {latency}ms: {e}",
                extra={
                    "provider": "gemini",
                    "model": self.model,
                    "messages_count": len(messages),
                    "latency_ms": latency,
                    "error": str(e),
                },
            )
            raise

        latency = round((time.time() - start) * 1000, 2)
        text, tokens = self._parse_response(data)

        logger.info(
            f"Gemini {self.model} ok messages={len(messages)} "
            f"latency={latency}ms tokens={tokens} out={text[:120]}",
            extra={
                "provider": "gemini",
                "model": self.model,
                "messages_count": len(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system_prompt_preview": system_msg.get("content", "")[:200],
                "user_message": last_user.get("content", ""),
                "output": text,
                "tokens_used": tokens,
                "latency_ms": latency,
            },
        )
        return {"text": text, "tokens_used": tokens, "latency_ms": latency}

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop: list[str] | None = None,
    ) -> dict:
        """Legacy single-shot completion — routes through chat_completion."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat_completion(
            messages, max_tokens=max_tokens, temperature=temperature
        )

    async def health_check(self) -> bool:
        """Ping /models to verify API key + reachability."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models", headers=self._headers()
                )
                return resp.status_code == 200
        except Exception:
            return False


llm_client = LLMClient()

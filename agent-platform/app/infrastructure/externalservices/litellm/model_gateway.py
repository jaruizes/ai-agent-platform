from typing import Any

import httpx
from opentelemetry import trace

from app.domain.execution import ExecutionPlan
from app.infrastructure.config.settings import Settings


tracer = trace.get_tracer(__name__)


class LiteLLMModelGateway:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.litellm_base_url,
            timeout=settings.model_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_profile: str,
        temperature: float = 0.2,
    ) -> str:
        body = await self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_profile=model_profile,
            temperature=temperature,
        )
        return body["choices"][0]["message"]["content"]

    async def execute(self, plan: ExecutionPlan) -> dict[str, Any]:
        body = await self._chat(
            system_prompt=plan.system_prompt,
            user_prompt=plan.user_prompt,
            model_profile=plan.model_profile,
            temperature=0.2,
        )
        content = body["choices"][0]["message"]["content"]

        return {
            "type": "agent-response" if plan.strategy in {"AGENT", "AGENT_TOOL_LLM"} else "direct-llm-response",
            "summary": content,
            "data": {
                "model": body.get("model", plan.model_profile),
                "modelProfile": plan.model_profile,
                "usage": body.get("usage", {}),
            },
            "artifacts": [],
        }

    async def _chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_profile: str,
        temperature: float,
    ) -> dict[str, Any]:
        with tracer.start_as_current_span("model_gateway.chat_completion") as span:
            span.set_attribute("gen_ai.system", "litellm")
            span.set_attribute("gen_ai.request.model", model_profile)

            response = await self._client.post(
                "/v1/chat/completions",
                json={
                    "model": model_profile,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = response.text[:4000]
                raise RuntimeError(
                    f"LiteLLM request failed with HTTP {response.status_code}: {body}"
                ) from exc
            return response.json()

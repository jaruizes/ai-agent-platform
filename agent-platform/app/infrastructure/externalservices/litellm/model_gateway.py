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

    async def execute(self, plan: ExecutionPlan) -> dict[str, Any]:
        with tracer.start_as_current_span("model_gateway.chat_completion") as span:
            span.set_attribute("gen_ai.system", "litellm")
            span.set_attribute("gen_ai.request.model", self._settings.default_model)

            response = await self._client.post(
                "/v1/chat/completions",
                json={
                    "model": self._settings.default_model,
                    "messages": [
                        {"role": "system", "content": plan.system_prompt},
                        {"role": "user", "content": plan.user_prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]

            return {
                "type": "direct-llm-response",
                "summary": content,
                "data": {
                    "model": body.get("model", self._settings.default_model),
                    "usage": body.get("usage", {}),
                },
                "artifacts": [],
            }

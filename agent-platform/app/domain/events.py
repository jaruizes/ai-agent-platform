from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


EVENT_SOURCE = {"type": "platform", "name": "ai-agent-platform"}


def _base(
    *,
    message_type: str,
    execution_id: UUID,
    correlation_id: str,
    causation_id: str | None,
    command_name: str | None,
) -> dict[str, Any]:
    return {
        "specVersion": "1.0",
        "messageId": str(uuid4()),
        "messageType": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlationId": correlation_id,
        "causationId": causation_id,
        "source": EVENT_SOURCE,
        "data": {
            "execution": {
                "executionId": str(execution_id),
                "command": {"name": command_name},
            }
        },
    }


def lifecycle_event(
    *,
    execution_id: UUID,
    correlation_id: str,
    causation_id: str | None,
    command_name: str | None,
    status: str,
    event_type: str,
    sequence: int,
    detail: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = _base(
        message_type="execution.lifecycle",
        execution_id=execution_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        command_name=command_name,
    )
    payload = event["data"]["execution"]
    payload["status"] = status
    payload["event"] = {
        "type": event_type,
        "sequence": sequence,
        "detail": detail or {},
    }
    if error:
        payload["error"] = error
    return event


def result_event(
    *,
    execution_id: UUID,
    correlation_id: str,
    causation_id: str | None,
    command_name: str | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    event = _base(
        message_type="execution.result",
        execution_id=execution_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        command_name=command_name,
    )
    payload = event["data"]["execution"]
    payload["status"] = "COMPLETED"
    payload["result"] = result
    return event

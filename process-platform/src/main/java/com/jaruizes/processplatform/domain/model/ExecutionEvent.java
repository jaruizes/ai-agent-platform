package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Canonical event emitted by Agent Platform.
 *
 * The payload is intentionally forward compatible: lifecycle, result and
 * orchestration events share the same envelope while their optional fields differ.
 */
public record ExecutionEvent(
        String specVersion,
        String messageId,
        String messageType,
        Instant timestamp,
        String correlationId,
        String causationId,
        Source source,
        ExecutionData execution) {

    public record Source(String type, String name, String instance) {}

    public record ExecutionData(
            UUID executionId,
            CommandRef command,
            String status,
            EventDetail event,
            Map<String, Object> result,
            Map<String, Object> error) {}

    public record CommandRef(String name) {}

    public record EventDetail(
            String type,
            Long sequence,
            Map<String, Object> detail) {}

    public boolean isTerminal() {
        return "execution.result".equals(messageType)
                || ("execution.lifecycle".equals(messageType)
                    && execution != null
                    && ("FAILED".equals(execution.status())
                        || "CANCELLED".equals(execution.status())));
    }

    public boolean isCompleted() {
        return "execution.result".equals(messageType)
                && execution != null
                && "COMPLETED".equals(execution.status());
    }
}

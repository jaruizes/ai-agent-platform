package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Canonical event emitted by Agent Platform.
 *
 * The envelope mirrors Agent Platform exactly: data.execution is shared by
 * lifecycle, result and orchestration event families.
 */
public record ExecutionEvent(
        String specVersion,
        String messageId,
        String messageType,
        Instant timestamp,
        String correlationId,
        String causationId,
        Source source,
        Data data) {

    public record Source(String type, String name, String instance) {}

    public record Data(ExecutionData execution) {}

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

    public ExecutionData execution() {
        return data == null ? null : data.execution();
    }

    public boolean isTerminal() {
        return "execution.result".equals(messageType)
                || ("execution.lifecycle".equals(messageType)
                    && execution() != null
                    && ("FAILED".equals(execution().status())
                        || "CANCELLED".equals(execution().status())));
    }

    public boolean isCompleted() {
        return "execution.result".equals(messageType)
                && execution() != null
                && "COMPLETED".equals(execution().status());
    }
}

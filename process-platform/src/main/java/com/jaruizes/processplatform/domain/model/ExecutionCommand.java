package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Canonical public command understood by Agent Platform.
 *
 * This model deliberately mirrors the platform contract instead of exposing
 * Planner, Agent, LangGraph, MCP or any other Agent Platform implementation detail.
 */
public record ExecutionCommand(
        String specVersion,
        String messageId,
        String messageType,
        Instant timestamp,
        String correlationId,
        String causationId,
        Source source,
        String tenantId,
        Data data) {

    public static final String SPEC_VERSION = "1.0";
    public static final String MESSAGE_TYPE = "execution.command";

    public record Source(String type, String name, String instance) {}

    public record Data(Execution execution) {}

    public record Execution(
            UUID executionId,
            UUID sessionId,
            Command command) {}

    public record Command(
            String name,
            String intent,
            Map<String, Object> input,
            Map<String, Object> context,
            List<String> instructions,
            Map<String, Object> metadata) {}
}

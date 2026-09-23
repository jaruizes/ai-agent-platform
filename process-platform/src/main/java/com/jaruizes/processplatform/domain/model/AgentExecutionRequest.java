package com.jaruizes.processplatform.domain.model;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Process-agnostic request used by Process Platform business code when it wants
 * to delegate an open-ended activity to Agent Platform.
 */
public record AgentExecutionRequest(
        String name,
        String intent,
        Map<String, Object> input,
        Map<String, Object> context,
        List<String> instructions,
        Map<String, Object> metadata,
        UUID sessionId,
        String correlationId,
        String causationId,
        String tenantId) {}

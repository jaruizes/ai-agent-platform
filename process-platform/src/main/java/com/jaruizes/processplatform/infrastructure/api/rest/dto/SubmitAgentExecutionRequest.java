package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record SubmitAgentExecutionRequest(
        String name,
        @NotBlank String intent,
        Map<String, Object> input,
        Map<String, Object> context,
        List<String> instructions,
        Map<String, Object> metadata,
        UUID sessionId,
        String correlationId,
        String causationId,
        String tenantId) {}

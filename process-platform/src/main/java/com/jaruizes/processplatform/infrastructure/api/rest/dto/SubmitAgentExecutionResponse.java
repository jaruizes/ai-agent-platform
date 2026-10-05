package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import java.util.UUID;

public record SubmitAgentExecutionResponse(
        UUID executionId,
        String messageId,
        String correlationId,
        String status) {}

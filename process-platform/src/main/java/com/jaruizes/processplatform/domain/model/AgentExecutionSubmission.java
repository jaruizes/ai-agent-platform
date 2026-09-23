package com.jaruizes.processplatform.domain.model;

import java.util.UUID;

public record AgentExecutionSubmission(
        UUID executionId,
        String messageId,
        String correlationId) {}

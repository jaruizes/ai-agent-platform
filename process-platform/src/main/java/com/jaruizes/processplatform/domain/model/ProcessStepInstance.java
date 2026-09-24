package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record ProcessStepInstance(
        UUID id,
        UUID processInstanceId,
        UUID stepDefinitionId,
        String stepKey,
        ProcessStepType type,
        ProcessStepStatus status,
        Map<String,Object> input,
        Map<String,Object> output,
        Map<String,Object> error,
        UUID delegatedExecutionId,
        int attemptCount,
        Instant availableAt,
        Instant deadlineAt,
        Instant startedAt,
        Instant completedAt,
        Instant updatedAt) {}

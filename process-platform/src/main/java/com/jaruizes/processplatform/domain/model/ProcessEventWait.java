package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record ProcessEventWait(
        UUID id,
        UUID processInstanceId,
        String stepKey,
        String eventType,
        String correlationId,
        ProcessEventWaitStatus status,
        Map<String,Object> payload,
        Instant createdAt,
        Instant consumedAt) {}

package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record HumanTask(
        UUID id,
        UUID processInstanceId,
        String stepKey,
        String title,
        String description,
        Map<String,Object> payload,
        HumanTaskStatus status,
        String decision,
        Map<String,Object> result,
        Instant createdAt,
        Instant completedAt) {}

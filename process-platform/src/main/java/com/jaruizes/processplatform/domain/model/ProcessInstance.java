package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProcessInstance(
        UUID id,
        UUID definitionId,
        String definitionKey,
        int definitionVersion,
        ProcessInstanceStatus status,
        String correlationId,
        Map<String,Object> input,
        Map<String,Object> context,
        List<ProcessStepInstance> steps,
        Instant createdAt,
        Instant updatedAt,
        Instant completedAt) {

    public ProcessInstance {
        input = input == null ? Map.of() : Map.copyOf(input);
        context = context == null ? Map.of() : Map.copyOf(context);
        steps = steps == null ? List.of() : List.copyOf(steps);
    }
}

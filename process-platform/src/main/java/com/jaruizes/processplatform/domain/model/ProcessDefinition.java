package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProcessDefinition(
        UUID id,
        String definitionKey,
        String name,
        String description,
        int version,
        ProcessDefinitionStatus status,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema,
        List<ProcessStepDefinition> steps,
        Instant createdAt,
        Instant updatedAt,
        Instant activatedAt) {

    public ProcessDefinition {
        inputSchema = inputSchema == null ? Map.of() : Map.copyOf(inputSchema);
        outputSchema = outputSchema == null ? Map.of() : Map.copyOf(outputSchema);
        steps = steps == null ? List.of() : List.copyOf(steps);
    }
}

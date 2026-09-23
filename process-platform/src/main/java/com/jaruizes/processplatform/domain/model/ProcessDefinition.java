package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Collections;
import java.util.LinkedHashMap;
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
        inputSchema = inputSchema == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(inputSchema));
        outputSchema = outputSchema == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(outputSchema));
        steps = steps == null ? List.of() : List.copyOf(steps);
    }
}

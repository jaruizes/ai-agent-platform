package com.jaruizes.processplatform.domain.model;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProcessStepDefinition(
        UUID id,
        String stepKey,
        String name,
        String description,
        ProcessStepType type,
        List<String> dependsOn,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema,
        Map<String,Object> configuration) {

    public ProcessStepDefinition {
        dependsOn = dependsOn == null ? List.of() : List.copyOf(dependsOn);
        inputSchema = inputSchema == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(inputSchema));
        outputSchema = outputSchema == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(outputSchema));
        configuration = configuration == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(configuration));
    }
}

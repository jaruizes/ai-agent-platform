package com.jaruizes.processplatform.domain.model;

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
        inputSchema = inputSchema == null ? Map.of() : Map.copyOf(inputSchema);
        outputSchema = outputSchema == null ? Map.of() : Map.copyOf(outputSchema);
        configuration = configuration == null ? Map.of() : Map.copyOf(configuration);
    }
}

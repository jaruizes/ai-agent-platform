package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import com.jaruizes.processplatform.domain.model.ProcessStepType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.Map;

public record ProcessStepDefinitionRequest(
        @NotBlank String stepKey,
        @NotBlank String name,
        String description,
        @NotNull ProcessStepType type,
        List<String> dependsOn,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema,
        Map<String,Object> configuration) {}

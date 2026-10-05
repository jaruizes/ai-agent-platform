package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

import java.util.List;
import java.util.Map;

public record CreateProcessDefinitionRequest(
        @NotBlank String definitionKey,
        @NotBlank String name,
        String description,
        @Min(1) int version,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema,
        List<@Valid ProcessStepDefinitionRequest> steps) {}

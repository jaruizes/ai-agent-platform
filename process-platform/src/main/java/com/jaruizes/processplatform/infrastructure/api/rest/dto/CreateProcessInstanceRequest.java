package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.Map;

public record CreateProcessInstanceRequest(
        @NotBlank String definitionKey,
        Integer version,
        String correlationId,
        Map<String,Object> input,
        Map<String,Object> context) {}

package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.Map;

public record SignalProcessEventRequest(
        @NotBlank String eventType,
        @NotBlank String correlationId,
        Map<String,Object> payload) {}

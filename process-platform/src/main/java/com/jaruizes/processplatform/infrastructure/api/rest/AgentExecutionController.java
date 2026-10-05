package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.AgentPlatformIntegrationService;
import com.jaruizes.processplatform.domain.model.AgentExecutionRequest;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.SubmitAgentExecutionRequest;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.SubmitAgentExecutionResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/v1/agent-executions")
public class AgentExecutionController {

    private final AgentPlatformIntegrationService service;

    public AgentExecutionController(AgentPlatformIntegrationService service) {
        this.service = service;
    }

    /**
     * Diagnostic/application integration endpoint for M9.1.
     * It returns after NATS accepted the command; it never waits for Agent Platform.
     */
    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public SubmitAgentExecutionResponse submit(
            @Valid @RequestBody SubmitAgentExecutionRequest request) {
        var submission = service.submit(new AgentExecutionRequest(
                request.name(),
                request.intent(),
                request.input(),
                request.context(),
                request.instructions(),
                request.metadata(),
                request.sessionId(),
                request.correlationId(),
                request.causationId(),
                request.tenantId()
        ));
        return new SubmitAgentExecutionResponse(
                submission.executionId(),
                submission.messageId(),
                submission.correlationId(),
                "SUBMITTED"
        );
    }
}

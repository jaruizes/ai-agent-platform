package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.AgentExecutionRequest;
import com.jaruizes.processplatform.domain.model.AgentExecutionSubmission;
import com.jaruizes.processplatform.domain.model.ExecutionCommand;
import com.jaruizes.processplatform.domain.model.ExecutionEvent;
import com.jaruizes.processplatform.domain.ports.AgentPlatformCommandPort;
import com.jaruizes.processplatform.domain.ports.ExecutionEventPublisherPort;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Application boundary between deterministic process code and Agent Platform.
 *
 * M9.1 owns only the canonical asynchronous integration. It does not define
 * ProcessDefinition, ProcessInstance or process scheduling semantics yet.
 */
@Service
public class AgentPlatformIntegrationService {

    private final AgentPlatformCommandPort commandPort;
    private final ExecutionEventPublisherPort eventPublisher;

    public AgentPlatformIntegrationService(
            AgentPlatformCommandPort commandPort,
            ExecutionEventPublisherPort eventPublisher) {
        this.commandPort = commandPort;
        this.eventPublisher = eventPublisher;
    }

    public AgentExecutionSubmission submit(AgentExecutionRequest request) {
        if (request == null || request.intent() == null || request.intent().isBlank()) {
            throw new IllegalArgumentException("Execution intent is required");
        }

        var executionId = UUID.randomUUID();
        var messageId = UUID.randomUUID().toString();
        var correlationId = hasText(request.correlationId())
                ? request.correlationId()
                : UUID.randomUUID().toString();

        var command = new ExecutionCommand(
                ExecutionCommand.SPEC_VERSION,
                messageId,
                ExecutionCommand.MESSAGE_TYPE,
                Instant.now(),
                correlationId,
                emptyToNull(request.causationId()),
                new ExecutionCommand.Source(
                        "process-platform",
                        "process-platform",
                        null
                ),
                emptyToNull(request.tenantId()),
                new ExecutionCommand.Data(
                        new ExecutionCommand.Execution(
                                executionId,
                                request.sessionId(),
                                new ExecutionCommand.Command(
                                        emptyToNull(request.name()),
                                        request.intent(),
                                        safeMap(request.input()),
                                        safeMap(request.context()),
                                        request.instructions() == null ? List.of() : List.copyOf(request.instructions()),
                                        safeMap(request.metadata())
                                )
                        )
                )
        );

        commandPort.submit(command);
        return new AgentExecutionSubmission(executionId, messageId, correlationId);
    }

    /**
     * Called by the inbound Agent Platform event adapter.
     * No transport-specific semantics leak beyond this method.
     */
    public void handle(ExecutionEvent event) {
        if (event == null || event.execution() == null || event.execution().executionId() == null) {
            throw new IllegalArgumentException("Invalid Agent Platform execution event");
        }
        eventPublisher.publish(event);
    }

    private static Map<String, Object> safeMap(Map<String, Object> value) {
        return value == null ? Map.of() : Map.copyOf(value);
    }

    private static String emptyToNull(String value) {
        return hasText(value) ? value : null;
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}

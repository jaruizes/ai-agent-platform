package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.AgentExecutionRequest;
import com.jaruizes.processplatform.domain.model.ExecutionCommand;
import com.jaruizes.processplatform.domain.model.ExecutionEvent;
import com.jaruizes.processplatform.domain.ports.AgentPlatformCommandPort;
import com.jaruizes.processplatform.domain.ports.ExecutionEventPublisherPort;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class AgentPlatformIntegrationServiceTest {

    @Test
    void submitsCanonicalExecutionCommandWithoutAgentPlatformInternals() {
        var commandRef = new AtomicReference<ExecutionCommand>();
        AgentPlatformCommandPort commandPort = commandRef::set;
        ExecutionEventPublisherPort eventPort = ignored -> {};
        var service = new AgentPlatformIntegrationService(commandPort, eventPort);

        var request = new AgentExecutionRequest(
                "security-analysis",
                "Analyse the security risks",
                Map.of("proposalId", "P-1"),
                Map.of("language", "es"),
                List.of("Return structured findings"),
                Map.of("processStepId", "security"),
                null,
                "corr-1",
                "cause-1",
                null
        );

        var submission = service.submit(request);
        var command = commandRef.get();

        assertThat(submission.executionId()).isEqualTo(command.data().execution().executionId());
        assertThat(command.specVersion()).isEqualTo("1.0");
        assertThat(command.messageType()).isEqualTo("execution.command");
        assertThat(command.correlationId()).isEqualTo("corr-1");
        assertThat(command.causationId()).isEqualTo("cause-1");
        assertThat(command.source().type()).isEqualTo("process-platform");
        assertThat(command.data().execution().command().intent())
                .isEqualTo("Analyse the security risks");
        assertThat(command.data().execution().command().metadata())
                .containsEntry("processStepId", "security");
    }

    @Test
    void forwardsCanonicalExecutionEventsToInternalPort() {
        var eventRef = new AtomicReference<ExecutionEvent>();
        var service = new AgentPlatformIntegrationService(
                ignored -> {},
                eventRef::set
        );
        var executionId = UUID.randomUUID();
        var event = new ExecutionEvent(
                "1.0",
                UUID.randomUUID().toString(),
                "execution.result",
                Instant.now(),
                "corr",
                "cause",
                new ExecutionEvent.Source("platform", "ai-agent-platform", null),
                new ExecutionEvent.ExecutionData(
                        executionId,
                        new ExecutionEvent.CommandRef("security-analysis"),
                        "COMPLETED",
                        null,
                        Map.of("summary", "done"),
                        null
                )
        );

        service.handle(event);

        assertThat(eventRef.get()).isEqualTo(event);
        assertThat(eventRef.get().isTerminal()).isTrue();
        assertThat(eventRef.get().isCompleted()).isTrue();
    }
}

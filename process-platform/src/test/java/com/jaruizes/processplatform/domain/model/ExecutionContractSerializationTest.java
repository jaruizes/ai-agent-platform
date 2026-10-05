package com.jaruizes.processplatform.domain.model;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class ExecutionContractSerializationTest {

    private final ObjectMapper mapper = new ObjectMapper()
            .registerModule(new JavaTimeModule());

    @Test
    void commandMatchesAgentPlatformCamelCaseContract() throws Exception {
        var executionId = UUID.randomUUID();
        var command = new ExecutionCommand(
                "1.0",
                "message-1",
                "execution.command",
                Instant.parse("2026-09-23T12:00:00Z"),
                "corr-1",
                null,
                new ExecutionCommand.Source("process-platform", "process-platform", null),
                null,
                new ExecutionCommand.Data(new ExecutionCommand.Execution(
                        executionId,
                        null,
                        new ExecutionCommand.Command(
                                "demo",
                                "Return a concise confirmation",
                                Map.of(),
                                Map.of(),
                                List.of("Be concise"),
                                Map.of()
                        )
                ))
        );

        var json = mapper.readTree(mapper.writeValueAsBytes(command));

        assertThat(json.path("specVersion").asText()).isEqualTo("1.0");
        assertThat(json.path("messageType").asText()).isEqualTo("execution.command");
        assertThat(json.path("data").path("execution").path("executionId").asText())
                .isEqualTo(executionId.toString());
        assertThat(json.path("data").path("execution").path("command").path("intent").asText())
                .isEqualTo("Return a concise confirmation");
    }

    @Test
    void readsLifecycleAndResultEventsFromAgentPlatform() throws Exception {
        var executionId = UUID.randomUUID();
        var lifecycleJson = """
                {
                  "specVersion":"1.0",
                  "messageId":"m1",
                  "messageType":"execution.lifecycle",
                  "timestamp":"2026-09-23T12:00:00Z",
                  "correlationId":"corr",
                  "causationId":"cmd",
                  "source":{"type":"platform","name":"ai-agent-platform"},
                  "data":{"execution":{
                    "executionId":"%s",
                    "command":{"name":"demo"},
                    "status":"RUNNING",
                    "event":{"type":"EXECUTION_STARTED","sequence":2,"detail":{}}
                  }}
                }
                """.formatted(executionId);

        var event = mapper.readValue(lifecycleJson, ExecutionEvent.class);

        assertThat(event.execution().executionId()).isEqualTo(executionId);
        assertThat(event.execution().event().type()).isEqualTo("EXECUTION_STARTED");
        assertThat(event.isTerminal()).isFalse();
    }
}

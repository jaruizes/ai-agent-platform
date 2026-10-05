package com.jaruizes.processplatform.infrastructure.messaging.nats;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jaruizes.processplatform.domain.model.ExecutionCommand;
import com.jaruizes.processplatform.domain.ports.AgentPlatformCommandPort;
import io.nats.client.Connection;
import io.nats.client.JetStream;
import io.nats.client.api.PublishAck;
import io.nats.client.impl.Headers;
import org.springframework.stereotype.Component;

@Component
public class NatsAgentPlatformCommandAdapter implements AgentPlatformCommandPort {

    private final AgentPlatformNatsProperties properties;
    private final ObjectMapper objectMapper;
    private final JetStream jetStream;

    public NatsAgentPlatformCommandAdapter(
            AgentPlatformNatsProperties properties,
            ObjectMapper objectMapper,
            Connection connection) throws Exception {
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.jetStream = connection.jetStream();
    }

    @Override
    public void submit(ExecutionCommand command) {
        try {
            var payload = objectMapper.writeValueAsBytes(command);
            if (payload.length > properties.maxCommandBytes()) {
                throw new IllegalArgumentException(
                        "ExecutionCommand is too large for NATS: %d bytes (limit %d). "
                                .formatted(payload.length, properties.maxCommandBytes())
                                + "Externalize large/binary resources and send references instead."
                );
            }

            var headers = new Headers();
            headers.add("Nats-Msg-Id", command.messageId());
            PublishAck ack = jetStream.publish(
                    properties.commandSubject(),
                    headers,
                    payload
            );
            if (ack == null) {
                throw new IllegalStateException("NATS did not acknowledge ExecutionCommand");
            }
        } catch (RuntimeException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalStateException(
                    "Could not publish ExecutionCommand to Agent Platform",
                    exception
            );
        }
    }
}

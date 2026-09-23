package com.jaruizes.processplatform.infrastructure.messaging.nats;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jaruizes.processplatform.business.AgentPlatformIntegrationService;
import com.jaruizes.processplatform.domain.model.ExecutionEvent;
import io.nats.client.Connection;
import io.nats.client.JetStreamSubscription;
import io.nats.client.PullSubscribeOptions;
import jakarta.annotation.PreDestroy;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Durable inbound adapter for every standard Agent Platform execution event:
 * lifecycle, orchestration and result.
 */
@Component
public class NatsAgentPlatformEventConsumer {

    private final ObjectMapper objectMapper;
    private final AgentPlatformIntegrationService service;
    private final JetStreamSubscription subscription;
    private final ExecutorService consumer;
    private volatile boolean running = true;

    public NatsAgentPlatformEventConsumer(
            AgentPlatformNatsProperties properties,
            ObjectMapper objectMapper,
            Connection connection,
            AgentPlatformIntegrationService service) throws Exception {
        this.objectMapper = objectMapper;
        this.service = service;

        var options = PullSubscribeOptions.builder()
                .durable(properties.eventsDurable())
                .build();

        this.subscription = connection.jetStream().subscribe(
                properties.eventsSubject(),
                options
        );
        this.consumer = Executors.newSingleThreadExecutor(
                Thread.ofVirtual()
                        .name("agent-platform-events-", 0)
                        .factory()
        );
        this.consumer.submit(this::consumeLoop);
    }

    private void consumeLoop() {
        while (running && !Thread.currentThread().isInterrupted()) {
            try {
                for (var message : subscription.fetch(50, Duration.ofSeconds(1))) {
                    try {
                        var event = objectMapper.readValue(
                                message.getData(),
                                ExecutionEvent.class
                        );
                        service.handle(event);
                        message.ack();
                    } catch (Exception processingError) {
                        message.nak();
                    }
                }
            } catch (Exception connectionError) {
                if (!running) return;
                try {
                    Thread.sleep(500);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }
    }

    @PreDestroy
    void close() {
        running = false;
        consumer.shutdownNow();
        try {
            subscription.unsubscribe();
        } catch (Exception ignored) {
            // best-effort shutdown
        }
    }
}

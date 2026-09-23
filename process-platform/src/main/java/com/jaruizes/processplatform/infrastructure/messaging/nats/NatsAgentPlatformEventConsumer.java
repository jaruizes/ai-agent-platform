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
 *
 * Subscription creation is retried because Process Platform is an independent
 * deployable and may start before Agent Platform has created PLATFORM_EVENTS.
 */
@Component
public class NatsAgentPlatformEventConsumer {

    private final AgentPlatformNatsProperties properties;
    private final ObjectMapper objectMapper;
    private final Connection connection;
    private final AgentPlatformIntegrationService service;
    private final ExecutorService consumer;
    private volatile JetStreamSubscription subscription;
    private volatile boolean running = true;

    public NatsAgentPlatformEventConsumer(
            AgentPlatformNatsProperties properties,
            ObjectMapper objectMapper,
            Connection connection,
            AgentPlatformIntegrationService service) {
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.connection = connection;
        this.service = service;
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
                var currentSubscription = ensureSubscription();
                for (var message : currentSubscription.fetch(50, Duration.ofSeconds(1))) {
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
                subscription = null;
                if (!running) return;
                sleepBeforeRetry();
            }
        }
    }

    private JetStreamSubscription ensureSubscription() throws Exception {
        var current = subscription;
        if (current != null) return current;

        var options = PullSubscribeOptions.builder()
                .durable(properties.eventsDurable())
                .build();
        current = connection.jetStream().subscribe(
                properties.eventsSubject(),
                options
        );
        subscription = current;
        return current;
    }

    private static void sleepBeforeRetry() {
        try {
            Thread.sleep(1000);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    @PreDestroy
    void close() {
        running = false;
        consumer.shutdownNow();
        var current = subscription;
        if (current != null) {
            try {
                current.unsubscribe();
            } catch (Exception ignored) {
                // best-effort shutdown
            }
        }
    }
}

package com.jaruizes.processplatform.infrastructure.messaging.nats;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent-platform.nats")
public record AgentPlatformNatsProperties(
        String url,
        String commandSubject,
        String eventsSubject,
        String eventsDurable,
        int maxCommandBytes) {

    public AgentPlatformNatsProperties {
        if (url == null || url.isBlank()) url = "nats://localhost:4222";
        if (commandSubject == null || commandSubject.isBlank()) {
            commandSubject = "platform.commands.execution";
        }
        if (eventsSubject == null || eventsSubject.isBlank()) {
            eventsSubject = "platform.events.execution.>";
        }
        if (eventsDurable == null || eventsDurable.isBlank()) {
            eventsDurable = "process-platform-agent-events";
        }
        if (maxCommandBytes <= 0) maxCommandBytes = 900_000;
    }
}

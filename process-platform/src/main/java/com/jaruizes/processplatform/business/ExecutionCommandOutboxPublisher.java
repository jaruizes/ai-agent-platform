package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.ports.AgentPlatformCommandPort;
import com.jaruizes.processplatform.domain.ports.ExecutionCommandOutboxPort;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class ExecutionCommandOutboxPublisher {

    private final ExecutionCommandOutboxPort outbox;
    private final AgentPlatformCommandPort commandPort;

    public ExecutionCommandOutboxPublisher(
            ExecutionCommandOutboxPort outbox,
            AgentPlatformCommandPort commandPort) {
        this.outbox = outbox;
        this.commandPort = commandPort;
    }

    @Scheduled(fixedDelayString = "${process.runtime.outbox-poll-ms:250}")
    public void publishPending() {
        for (var pending : outbox.pending(50)) {
            try {
                commandPort.submit(pending.command());
                outbox.markPublished(pending.outboxId());
            } catch (Exception publishError) {
                outbox.markAttempt(pending.outboxId());
            }
        }
    }
}

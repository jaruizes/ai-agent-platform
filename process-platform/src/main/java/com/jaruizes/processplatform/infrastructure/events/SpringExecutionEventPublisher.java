package com.jaruizes.processplatform.infrastructure.events;

import com.jaruizes.processplatform.domain.model.AgentExecutionEventReceived;
import com.jaruizes.processplatform.domain.model.ExecutionEvent;
import com.jaruizes.processplatform.domain.ports.ExecutionEventPublisherPort;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

/**
 * Converts the external Agent Platform event into an internal Spring event.
 * Future Process Runtime code can consume AgentExecutionEventReceived and remain
 * completely independent from NATS.
 */
@Component
public class SpringExecutionEventPublisher implements ExecutionEventPublisherPort {

    private final ApplicationEventPublisher publisher;

    public SpringExecutionEventPublisher(ApplicationEventPublisher publisher) {
        this.publisher = publisher;
    }

    @Override
    public void publish(ExecutionEvent event) {
        publisher.publishEvent(new AgentExecutionEventReceived(event));
    }
}

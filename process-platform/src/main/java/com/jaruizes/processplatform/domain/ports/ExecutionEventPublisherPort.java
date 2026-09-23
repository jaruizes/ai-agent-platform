package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.ExecutionEvent;

public interface ExecutionEventPublisherPort {
    void publish(ExecutionEvent event);
}

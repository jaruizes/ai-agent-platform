package com.jaruizes.processplatform.infrastructure.events;

import com.jaruizes.processplatform.domain.model.AgentExecutionEventReceived;
import com.jaruizes.processplatform.domain.model.ExecutionEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Bounded, in-memory diagnostic journal used only to inspect the M9.1 integration.
 *
 * This is NOT process state and is intentionally not durable. M9.2 will introduce
 * ProcessInstance/ProcessContext persistence; process semantics must never depend
 * on this journal.
 */
@Component
public class ExecutionEventJournal {

    private static final int MAX_EVENTS = 1_000;
    private final ArrayDeque<ExecutionEvent> events = new ArrayDeque<>();

    @EventListener
    public synchronized void on(AgentExecutionEventReceived received) {
        if (events.size() >= MAX_EVENTS) {
            events.removeFirst();
        }
        events.addLast(received.event());
    }

    public synchronized List<ExecutionEvent> findByExecutionId(UUID executionId) {
        var result = new ArrayList<ExecutionEvent>();
        for (var event : events) {
            if (event.execution() != null
                    && executionId.equals(event.execution().executionId())) {
                result.add(event);
            }
        }
        return List.copyOf(result);
    }
}

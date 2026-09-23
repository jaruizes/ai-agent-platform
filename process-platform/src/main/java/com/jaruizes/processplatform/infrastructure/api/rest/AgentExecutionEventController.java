package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.domain.model.ExecutionEvent;
import com.jaruizes.processplatform.infrastructure.events.ExecutionEventJournal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * Diagnostic endpoint for M9.1. It proves that standard Agent Platform events
 * arrived through NATS and were converted into internal Process Platform events.
 */
@RestController
@RequestMapping("/v1/agent-executions")
public class AgentExecutionEventController {

    private final ExecutionEventJournal journal;

    public AgentExecutionEventController(ExecutionEventJournal journal) {
        this.journal = journal;
    }

    @GetMapping("/{executionId}/events")
    public List<ExecutionEvent> events(@PathVariable UUID executionId) {
        return journal.findByExecutionId(executionId);
    }
}

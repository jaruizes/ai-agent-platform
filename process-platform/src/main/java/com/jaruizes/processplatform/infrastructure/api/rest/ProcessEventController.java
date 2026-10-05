package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.ProcessRuntimeService;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.SignalProcessEventRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/v1/process-events")
public class ProcessEventController {
    private final ProcessRuntimeService runtime;
    public ProcessEventController(ProcessRuntimeService runtime){this.runtime=runtime;}

    @PostMapping
    public Map<String,Object> signal(@Valid @RequestBody SignalProcessEventRequest request) {
        var matched = runtime.signalEvent(
                request.eventType(),
                request.correlationId(),
                request.payload());
        return Map.of("matchedWaits", matched);
    }
}

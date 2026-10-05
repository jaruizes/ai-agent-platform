package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.ProcessInstanceService;
import com.jaruizes.processplatform.domain.model.ProcessInstance;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.*;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/v1/process-instances")
public class ProcessInstanceController {

    private final ProcessInstanceService service;

    public ProcessInstanceController(ProcessInstanceService service) {
        this.service = service;
    }

    @GetMapping
    public List<ProcessInstance> list() {
        return service.list();
    }

    @GetMapping("/{id}")
    public ProcessInstance get(@PathVariable UUID id) {
        return service.get(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ProcessInstance create(
            @Valid @RequestBody CreateProcessInstanceRequest request) {
        return service.create(
                request.definitionKey(),
                request.version(),
                request.correlationId(),
                request.input(),
                request.context()
        );
    }

    @PutMapping("/{id}/context")
    public ProcessInstance replaceContext(
            @PathVariable UUID id,
            @RequestBody UpdateProcessContextRequest request) {
        return service.replaceContext(
                id,
                request.context() == null ? Map.of() : request.context()
        );
    }
}

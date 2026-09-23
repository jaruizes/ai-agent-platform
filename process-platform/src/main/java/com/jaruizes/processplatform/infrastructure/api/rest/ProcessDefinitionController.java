package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.ProcessDefinitionService;
import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.*;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/v1/process-definitions")
public class ProcessDefinitionController {

    private final ProcessDefinitionService service;

    public ProcessDefinitionController(ProcessDefinitionService service) {
        this.service = service;
    }

    @GetMapping
    public List<ProcessDefinition> list() {
        return service.list();
    }

    @GetMapping("/{id}")
    public ProcessDefinition get(@PathVariable UUID id) {
        return service.get(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ProcessDefinition create(
            @Valid @RequestBody CreateProcessDefinitionRequest request) {
        return service.create(
                request.definitionKey(),
                request.name(),
                request.description(),
                request.version(),
                request.inputSchema(),
                request.outputSchema(),
                steps(request.steps())
        );
    }

    @PutMapping("/{id}")
    public ProcessDefinition update(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateProcessDefinitionRequest request) {
        return service.updateDraft(
                id,
                request.name(),
                request.description(),
                request.inputSchema(),
                request.outputSchema(),
                steps(request.steps())
        );
    }

    @PostMapping("/{id}/activate")
    public ProcessDefinition activate(@PathVariable UUID id) {
        return service.activate(id);
    }

    @PostMapping("/{id}/retire")
    public ProcessDefinition retire(@PathVariable UUID id) {
        return service.retire(id);
    }

    @PostMapping("/{id}/next-version")
    @ResponseStatus(HttpStatus.CREATED)
    public ProcessDefinition nextVersion(@PathVariable UUID id) {
        return service.createNextVersion(id);
    }

    private static List<ProcessStepDefinition> steps(
            List<ProcessStepDefinitionRequest> requests) {
        if (requests == null) return List.of();
        return requests.stream().map(step ->
                new ProcessStepDefinition(
                        UUID.randomUUID(),
                        step.stepKey(),
                        step.name(),
                        step.description() == null ? "" : step.description(),
                        step.type(),
                        step.dependsOn(),
                        step.inputSchema(),
                        step.outputSchema(),
                        step.configuration()
                )
        ).toList();
    }
}

package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessDefinitionRepositoryPort;
import com.jaruizes.processplatform.domain.ports.ProcessInstanceRepositoryPort;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

@Service
public class ProcessInstanceService {

    private final ProcessDefinitionRepositoryPort definitions;
    private final ProcessInstanceRepositoryPort instances;

    public ProcessInstanceService(
            ProcessDefinitionRepositoryPort definitions,
            ProcessInstanceRepositoryPort instances) {
        this.definitions = definitions;
        this.instances = instances;
    }

    public ProcessInstance create(
            String definitionKey,
            Integer version,
            String correlationId,
            Map<String,Object> input,
            Map<String,Object> initialContext) {

        var definition = version == null
                ? definitions.findLatestActiveByKey(definitionKey)
                    .orElseThrow(() -> new NoSuchElementException(
                            "No ACTIVE process definition found for key: " + definitionKey))
                : definitions.findByKeyAndVersion(definitionKey, version)
                    .filter(d -> d.status() == ProcessDefinitionStatus.ACTIVE)
                    .orElseThrow(() -> new NoSuchElementException(
                            "ACTIVE process definition '%s' version %d not found"
                                    .formatted(definitionKey, version)));

        var instanceId = UUID.randomUUID();
        var now = Instant.now();
        var materializedSteps = definition.steps().stream()
                .map(step -> new ProcessStepInstance(
                        UUID.randomUUID(),
                        instanceId,
                        step.id(),
                        step.stepKey(),
                        step.type(),
                        ProcessStepStatus.PENDING,
                        Map.of(),
                        Map.of(),
                        Map.of(),
                        null,
                        0,
                        null,
                        null,
                        null,
                        null,
                        now
                ))
                .toList();

        return instances.create(new ProcessInstance(
                instanceId,
                definition.id(),
                definition.definitionKey(),
                definition.version(),
                ProcessInstanceStatus.CREATED,
                correlationId == null || correlationId.isBlank()
                        ? UUID.randomUUID().toString()
                        : correlationId,
                safeMap(input),
                safeMap(initialContext),
                materializedSteps,
                now,
                now,
                null
        ));
    }

    public ProcessInstance get(UUID id) {
        return instances.findById(id)
                .orElseThrow(() -> new NoSuchElementException("Process instance not found: " + id));
    }

    public List<ProcessInstance> list() {
        return instances.findAll();
    }

    public ProcessInstance replaceContext(UUID id, Map<String,Object> context) {
        get(id);
        return instances.updateContext(id, safeMap(context));
    }

    private static Map<String,Object> safeMap(Map<String,Object> value) {
        return value == null ? Map.of() : new LinkedHashMap<>(value);
    }
}

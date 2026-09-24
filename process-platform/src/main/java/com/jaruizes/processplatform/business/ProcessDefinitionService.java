package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.ProcessDefinition;
import com.jaruizes.processplatform.domain.model.ProcessDefinitionStatus;
import com.jaruizes.processplatform.domain.model.ProcessStepDefinition;
import com.jaruizes.processplatform.domain.ports.ProcessDefinitionRepositoryPort;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

@Service
public class ProcessDefinitionService {

    private final ProcessDefinitionRepositoryPort repository;
    private final ProcessServiceCatalogService services;

    public ProcessDefinitionService(
            ProcessDefinitionRepositoryPort repository,
            ProcessServiceCatalogService services) {
        this.repository = repository;
        this.services = services;
    }

    public ProcessDefinition create(
            String definitionKey,
            String name,
            String description,
            int version,
            Map<String,Object> inputSchema,
            Map<String,Object> outputSchema,
            List<ProcessStepDefinition> steps) {

        validateIdentity(definitionKey, name, version);
        if (repository.existsByKeyAndVersion(definitionKey, version)) {
            throw new IllegalArgumentException(
                    "Process definition '%s' version %d already exists".formatted(definitionKey, version)
            );
        }
        validateGraph(steps);

        var now = Instant.now();
        return repository.save(new ProcessDefinition(
                UUID.randomUUID(),
                definitionKey.trim(),
                name.trim(),
                description == null ? "" : description,
                version,
                ProcessDefinitionStatus.DRAFT,
                safeMap(inputSchema),
                safeMap(outputSchema),
                normalizeSteps(steps),
                now,
                now,
                null
        ));
    }

    public ProcessDefinition updateDraft(
            UUID id,
            String name,
            String description,
            Map<String,Object> inputSchema,
            Map<String,Object> outputSchema,
            List<ProcessStepDefinition> steps) {

        var current = get(id);
        if (current.status() != ProcessDefinitionStatus.DRAFT) {
            throw new IllegalStateException("Only DRAFT process definitions can be modified");
        }
        validateGraph(steps);

        var existingIds = new HashMap<String, UUID>();
        current.steps().forEach(step -> existingIds.put(step.stepKey(), step.id()));
        var normalizedSteps = normalizeSteps(steps).stream()
                .map(step -> new ProcessStepDefinition(
                        existingIds.getOrDefault(step.stepKey(), step.id()),
                        step.stepKey(),
                        step.name(),
                        step.description(),
                        step.type(),
                        step.dependsOn(),
                        step.inputSchema(),
                        step.outputSchema(),
                        step.configuration()
                ))
                .toList();

        return repository.save(new ProcessDefinition(
                current.id(),
                current.definitionKey(),
                name == null || name.isBlank() ? current.name() : name.trim(),
                description == null ? "" : description,
                current.version(),
                current.status(),
                safeMap(inputSchema),
                safeMap(outputSchema),
                normalizedSteps,
                current.createdAt(),
                Instant.now(),
                current.activatedAt()
        ));
    }

    public ProcessDefinition activate(UUID id) {
        var current = get(id);
        if (current.status() == ProcessDefinitionStatus.ACTIVE) return current;
        if (current.status() != ProcessDefinitionStatus.DRAFT) {
            throw new IllegalStateException("Only DRAFT process definitions can be activated");
        }
        validateGraph(current.steps());
        if (current.steps().isEmpty()) {
            throw new IllegalStateException("A process definition must contain at least one step");
        }

        var resolvedSteps = current.steps().stream()
                .map(this::resolveStepReferences)
                .toList();

        validateStepSemantics(resolvedSteps);

        return repository.save(new ProcessDefinition(
                current.id(),
                current.definitionKey(),
                current.name(),
                current.description(),
                current.version(),
                ProcessDefinitionStatus.ACTIVE,
                current.inputSchema(),
                current.outputSchema(),
                resolvedSteps,
                current.createdAt(),
                Instant.now(),
                Instant.now()
        ));
    }

    public ProcessDefinition createNextVersion(UUID sourceId) {
        var source = get(sourceId);
        if (source.status() == ProcessDefinitionStatus.DRAFT) {
            throw new IllegalStateException("Create the next version from an ACTIVE or RETIRED definition");
        }

        var nextVersion = source.version() + 1;
        while (repository.existsByKeyAndVersion(source.definitionKey(), nextVersion)) {
            nextVersion++;
        }

        var clonedSteps = source.steps().stream().map(step ->
                new ProcessStepDefinition(
                        UUID.randomUUID(),
                        step.stepKey(),
                        step.name(),
                        step.description(),
                        step.type(),
                        step.dependsOn(),
                        step.inputSchema(),
                        step.outputSchema(),
                        step.configuration()
                )
        ).toList();

        return create(
                source.definitionKey(),
                source.name(),
                source.description(),
                nextVersion,
                source.inputSchema(),
                source.outputSchema(),
                clonedSteps
        );
    }

    public ProcessDefinition retire(UUID id) {
        var current = get(id);
        if (current.status() == ProcessDefinitionStatus.RETIRED) return current;
        if (current.status() != ProcessDefinitionStatus.ACTIVE) {
            throw new IllegalStateException("Only ACTIVE process definitions can be retired");
        }
        return repository.save(new ProcessDefinition(
                current.id(),
                current.definitionKey(),
                current.name(),
                current.description(),
                current.version(),
                ProcessDefinitionStatus.RETIRED,
                current.inputSchema(),
                current.outputSchema(),
                current.steps(),
                current.createdAt(),
                Instant.now(),
                current.activatedAt()
        ));
    }

    public ProcessDefinition get(UUID id) {
        return repository.findById(id)
                .orElseThrow(() -> new NoSuchElementException("Process definition not found: " + id));
    }

    public List<ProcessDefinition> list() {
        return repository.findAll();
    }

    private static void validateIdentity(String key, String name, int version) {
        if (key == null || key.isBlank()) throw new IllegalArgumentException("definitionKey is required");
        if (name == null || name.isBlank()) throw new IllegalArgumentException("name is required");
        if (version < 1) throw new IllegalArgumentException("version must be >= 1");
    }

    private static List<ProcessStepDefinition> normalizeSteps(List<ProcessStepDefinition> steps) {
        if (steps == null) return List.of();
        return steps.stream().map(step -> new ProcessStepDefinition(
                step.id() == null ? UUID.randomUUID() : step.id(),
                step.stepKey(),
                step.name(),
                step.description(),
                step.type(),
                step.dependsOn(),
                step.inputSchema(),
                step.outputSchema(),
                step.configuration()
        )).toList();
    }

    static void validateGraph(List<ProcessStepDefinition> steps) {
        if (steps == null) return;

        var keys = new LinkedHashSet<String>();
        for (var step : steps) {
            if (step.stepKey() == null || step.stepKey().isBlank()) {
                throw new IllegalArgumentException("Every process step requires stepKey");
            }
            if (step.type() == null) {
                throw new IllegalArgumentException("Step '%s' requires type".formatted(step.stepKey()));
            }
            if (!keys.add(step.stepKey())) {
                throw new IllegalArgumentException("Duplicate process step key: " + step.stepKey());
            }
        }

        for (var step : steps) {
            for (var dependency : step.dependsOn()) {
                if (!keys.contains(dependency)) {
                    throw new IllegalArgumentException(
                            "Step '%s' depends on unknown step '%s'".formatted(step.stepKey(), dependency)
                    );
                }
                if (step.stepKey().equals(dependency)) {
                    throw new IllegalArgumentException("A process step cannot depend on itself");
                }
            }
        }

        var visiting = new HashSet<String>();
        var visited = new HashSet<String>();
        var byKey = new HashMap<String, ProcessStepDefinition>();
        steps.forEach(step -> byKey.put(step.stepKey(), step));
        for (var key : keys) {
            detectCycle(key, byKey, visiting, visited);
        }
    }

    private static void detectCycle(
            String key,
            Map<String, ProcessStepDefinition> byKey,
            Set<String> visiting,
            Set<String> visited) {
        if (visited.contains(key)) return;
        if (!visiting.add(key)) {
            throw new IllegalArgumentException("Process definition contains a dependency cycle at step: " + key);
        }
        for (var dependency : byKey.get(key).dependsOn()) {
            detectCycle(dependency, byKey, visiting, visited);
        }
        visiting.remove(key);
        visited.add(key);
    }


    private ProcessStepDefinition resolveStepReferences(ProcessStepDefinition step) {
        if (step.type() != com.jaruizes.processplatform.domain.model.ProcessStepType.SERVICE) {
            return step;
        }
        var configuration = new LinkedHashMap<>(step.configuration());
        var serviceKey = stringValue(configuration.get("serviceKey"));
        if (serviceKey == null || serviceKey.isBlank()) {
            throw new IllegalArgumentException(
                    "SERVICE step '%s' requires configuration.serviceKey"
                            .formatted(step.stepKey()));
        }
        Integer requestedVersion = integerValue(configuration.get("serviceVersion"));
        var service = services.resolveActive(serviceKey, requestedVersion);
        configuration.remove("handler");
        configuration.put("serviceKey", service.serviceKey());
        configuration.put("serviceVersion", service.version());
        return new ProcessStepDefinition(
                step.id(), step.stepKey(), step.name(), step.description(), step.type(),
                step.dependsOn(), step.inputSchema(), step.outputSchema(), configuration);
    }

    private static void validateStepSemantics(List<ProcessStepDefinition> steps) {
        var byKey = new HashMap<String,ProcessStepDefinition>();
        steps.forEach(step -> byKey.put(step.stepKey(), step));

        for (var step : steps) {
            if (step.type() == com.jaruizes.processplatform.domain.model.ProcessStepType.AGENTIC_EXECUTION
                    && !hasText(step.configuration().get("intent"))) {
                throw new IllegalArgumentException(
                        "AGENTIC_EXECUTION step '%s' requires configuration.intent"
                                .formatted(step.stepKey()));
            }
            if (step.type() == com.jaruizes.processplatform.domain.model.ProcessStepType.HUMAN
                    && !hasText(step.configuration().get("title"))) {
                throw new IllegalArgumentException(
                        "HUMAN step '%s' requires configuration.title"
                                .formatted(step.stepKey()));
            }
            if (step.type() == com.jaruizes.processplatform.domain.model.ProcessStepType.WAIT_EVENT
                    && !hasText(step.configuration().get("eventType"))) {
                throw new IllegalArgumentException(
                        "WAIT_EVENT step '%s' requires configuration.eventType"
                                .formatted(step.stepKey()));
            }
            if (step.type() == com.jaruizes.processplatform.domain.model.ProcessStepType.DECISION
                    && (!hasText(step.configuration().get("path"))
                        || !hasText(step.configuration().get("operator")))) {
                throw new IllegalArgumentException(
                        "DECISION step '%s' requires configuration.path and configuration.operator"
                                .formatted(step.stepKey()));
            }

            var when = step.configuration().get("when");
            if (when instanceof Map<?,?> condition) {
                var decisionKey = stringValue(condition.get("decisionStep"));
                if (decisionKey == null || !byKey.containsKey(decisionKey)
                        || byKey.get(decisionKey).type()
                            != com.jaruizes.processplatform.domain.model.ProcessStepType.DECISION) {
                    throw new IllegalArgumentException(
                            "Step '%s' has invalid configuration.when.decisionStep"
                                    .formatted(step.stepKey()));
                }
                if (!condition.containsKey("equals")) {
                    throw new IllegalArgumentException(
                            "Conditional step '%s' requires configuration.when.equals"
                                    .formatted(step.stepKey()));
                }
                if (!step.dependsOn().contains(decisionKey)) {
                    throw new IllegalArgumentException(
                            "Conditional step '%s' must depend on decision step '%s'"
                                    .formatted(step.stepKey(), decisionKey));
                }
            }
        }
    }

    private static boolean hasText(Object value) {
        return value != null && !String.valueOf(value).isBlank();
    }

    private static String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static Integer integerValue(Object value) {
        if (value == null) return null;
        if (value instanceof Number number) return number.intValue();
        return Integer.valueOf(String.valueOf(value));
    }

    private static Map<String,Object> safeMap(Map<String,Object> value) {
        return value == null ? Map.of() : new LinkedHashMap<>(value);
    }
}

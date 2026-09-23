package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.*;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.*;

import static org.assertj.core.api.Assertions.assertThat;

class ProcessInstanceServiceTest {

    @Test
    void materializesExactDefinitionVersionAndPendingSteps() {
        var definitions = new Definitions();
        var instances = new Instances();

        definitions.save(definition(1, ProcessDefinitionStatus.ACTIVE));
        definitions.save(definition(2, ProcessDefinitionStatus.DRAFT));

        var service = new ProcessInstanceService(definitions, instances);
        var instance = service.create(
                "proposal",
                null,
                "corr-1",
                Map.of("proposalId", "P-1"),
                Map.of("locale", "es")
        );

        assertThat(instance.definitionVersion()).isEqualTo(1);
        assertThat(instance.status()).isEqualTo(ProcessInstanceStatus.CREATED);
        assertThat(instance.input()).containsEntry("proposalId", "P-1");
        assertThat(instance.context()).containsEntry("locale", "es");
        assertThat(instance.steps()).hasSize(2);
        assertThat(instance.steps())
                .allMatch(step -> step.status() == ProcessStepStatus.PENDING);
        assertThat(instance.steps())
                .allMatch(step -> step.processInstanceId().equals(instance.id()));
    }

    private static ProcessDefinition definition(
            int version,
            ProcessDefinitionStatus status) {
        var now = Instant.now();
        return new ProcessDefinition(
                UUID.randomUUID(),
                "proposal",
                "Proposal",
                "",
                version,
                status,
                Map.of(),
                Map.of(),
                List.of(
                        new ProcessStepDefinition(
                                UUID.randomUUID(), "validate", "Validate", "",
                                ProcessStepType.SERVICE, List.of(),
                                Map.of(), Map.of(), Map.of()),
                        new ProcessStepDefinition(
                                UUID.randomUUID(), "analyse", "Analyse", "",
                                ProcessStepType.AGENTIC_EXECUTION, List.of("validate"),
                                Map.of(), Map.of(), Map.of())
                ),
                now,
                now,
                status == ProcessDefinitionStatus.ACTIVE ? now : null
        );
    }

    private static final class Definitions
            implements ProcessDefinitionRepositoryPort {
        private final List<ProcessDefinition> data = new ArrayList<>();

        @Override public ProcessDefinition save(ProcessDefinition value) {
            data.removeIf(x -> x.id().equals(value.id()));
            data.add(value);
            return value;
        }
        @Override public Optional<ProcessDefinition> findById(UUID id) {
            return data.stream().filter(x -> x.id().equals(id)).findFirst();
        }
        @Override public Optional<ProcessDefinition> findByKeyAndVersion(String key, int version) {
            return data.stream().filter(x -> x.definitionKey().equals(key) && x.version()==version).findFirst();
        }
        @Override public Optional<ProcessDefinition> findLatestActiveByKey(String key) {
            return data.stream()
                    .filter(x -> x.definitionKey().equals(key) && x.status()==ProcessDefinitionStatus.ACTIVE)
                    .max(Comparator.comparing(ProcessDefinition::version));
        }
        @Override public List<ProcessDefinition> findAll() { return List.copyOf(data); }
        @Override public boolean existsByKeyAndVersion(String key, int version) {
            return findByKeyAndVersion(key, version).isPresent();
        }
    }

    private static final class Instances
            implements ProcessInstanceRepositoryPort {
        private final Map<UUID,ProcessInstance> data = new LinkedHashMap<>();

        @Override public ProcessInstance create(ProcessInstance value) {
            data.put(value.id(), value);
            return value;
        }
        @Override public Optional<ProcessInstance> findById(UUID id) {
            return Optional.ofNullable(data.get(id));
        }
        @Override public List<ProcessInstance> findAll() {
            return List.copyOf(data.values());
        }
        @Override public ProcessInstance updateContext(UUID id, Map<String,Object> context) {
            var old = data.get(id);
            var updated = new ProcessInstance(
                    old.id(), old.definitionId(), old.definitionKey(),
                    old.definitionVersion(), old.status(), old.correlationId(),
                    old.input(), context, old.steps(), old.createdAt(),
                    Instant.now(), old.completedAt());
            data.put(id, updated);
            return updated;
        }
    }
}

package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessDefinitionRepositoryPort;
import org.junit.jupiter.api.Test;

import java.util.*;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ProcessDefinitionServiceTest {

    @Test
    void rejectsUnknownDependenciesAndCycles() {
        var service = definitionService(new InMemoryDefinitions());

        assertThatThrownBy(() -> service.create(
                "proposal",
                "Proposal",
                "",
                1,
                Map.of(),
                Map.of(),
                List.of(step("a", List.of("missing")))
        )).isInstanceOf(IllegalArgumentException.class)
          .hasMessageContaining("unknown step");

        assertThatThrownBy(() -> service.create(
                "proposal",
                "Proposal",
                "",
                1,
                Map.of(),
                Map.of(),
                List.of(
                        step("a", List.of("b")),
                        step("b", List.of("a"))
                )
        )).isInstanceOf(IllegalArgumentException.class)
          .hasMessageContaining("cycle");
    }

    @Test
    void activatedDefinitionIsImmutableAndNextVersionIsDraft() {
        var repository = new InMemoryDefinitions();
        var service = definitionService(repository);

        var draft = service.create(
                "proposal",
                "Proposal",
                "",
                1,
                Map.of("type", "object"),
                Map.of("type", "object"),
                List.of(
                        step("validate", List.of()),
                        step("analyse", List.of("validate"))
                )
        );
        var active = service.activate(draft.id());

        assertThat(active.status()).isEqualTo(ProcessDefinitionStatus.ACTIVE);
        assertThatThrownBy(() -> service.updateDraft(
                active.id(),
                "Changed",
                "",
                Map.of(),
                Map.of(),
                active.steps()
        )).isInstanceOf(IllegalStateException.class);

        var v2 = service.createNextVersion(active.id());

        assertThat(v2.definitionKey()).isEqualTo("proposal");
        assertThat(v2.version()).isEqualTo(2);
        assertThat(v2.status()).isEqualTo(ProcessDefinitionStatus.DRAFT);
        assertThat(v2.steps()).extracting(ProcessStepDefinition::stepKey)
                .containsExactly("validate", "analyse");
        assertThat(v2.steps().getFirst().id())
                .isNotEqualTo(active.steps().getFirst().id());
    }

    private static ProcessStepDefinition step(String key, List<String> dependencies) {
        return new ProcessStepDefinition(
                UUID.randomUUID(),
                key,
                key,
                "",
                ProcessStepType.SERVICE,
                dependencies,
                Map.of(),
                Map.of(),
                Map.of("serviceKey", "test.echo")
        );
    }

    private static ProcessDefinitionService definitionService(
            ProcessDefinitionRepositoryPort repository) {
        var catalog = mock(ProcessServiceCatalogService.class);
        var now = java.time.Instant.now();
        when(catalog.resolveActive(eq("test.echo"), nullable(Integer.class)))
                .thenReturn(new ProcessServiceDefinition(
                        UUID.randomUUID(),
                        "test.echo",
                        "Test echo",
                        "",
                        1,
                        ProcessServiceStatus.ACTIVE,
                        "echo",
                        Map.of(),
                        Map.of(),
                        now,
                        now,
                        now));
        return new ProcessDefinitionService(repository, catalog);
    }

    private static final class InMemoryDefinitions
            implements ProcessDefinitionRepositoryPort {
        private final Map<UUID,ProcessDefinition> data = new LinkedHashMap<>();

        @Override
        public ProcessDefinition save(ProcessDefinition definition) {
            data.put(definition.id(), definition);
            return definition;
        }

        @Override
        public Optional<ProcessDefinition> findById(UUID id) {
            return Optional.ofNullable(data.get(id));
        }

        @Override
        public Optional<ProcessDefinition> findByKeyAndVersion(String key, int version) {
            return data.values().stream()
                    .filter(x -> x.definitionKey().equals(key) && x.version() == version)
                    .findFirst();
        }

        @Override
        public Optional<ProcessDefinition> findLatestActiveByKey(String key) {
            return data.values().stream()
                    .filter(x -> x.definitionKey().equals(key))
                    .filter(x -> x.status() == ProcessDefinitionStatus.ACTIVE)
                    .max(Comparator.comparing(ProcessDefinition::version));
        }

        @Override
        public List<ProcessDefinition> findAll() {
            return List.copyOf(data.values());
        }

        @Override
        public boolean existsByKeyAndVersion(String key, int version) {
            return findByKeyAndVersion(key, version).isPresent();
        }
    }
}

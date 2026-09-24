package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.*;
import com.jaruizes.processplatform.infrastructure.service.EchoProcessServiceHandler;
import org.junit.jupiter.api.Test;

import java.util.*;

import static org.assertj.core.api.Assertions.*;

class ProcessServiceCatalogServiceTest {

    @Test
    void activatesOnlyRegisteredImplementationsAndResolvesRetiredPinnedVersion() {
        var repository = new InMemoryServices();
        var handlers = new ProcessServiceHandlerRegistry(
                List.of(new EchoProcessServiceHandler()));
        var catalog = new ProcessServiceCatalogService(repository, handlers);

        var draft = catalog.create(
                "customer.lookup",
                "Customer lookup",
                "",
                1,
                "echo",
                Map.of("type", "object"),
                Map.of("type", "object"));

        var active = catalog.activate(draft.id());

        assertThat(active.status()).isEqualTo(ProcessServiceStatus.ACTIVE);
        assertThat(catalog.resolveActive("customer.lookup", null).version()).isEqualTo(1);

        catalog.retire(active.id());

        assertThatThrownBy(() -> catalog.resolveActive("customer.lookup", 1))
                .isInstanceOf(NoSuchElementException.class);
        assertThat(catalog.resolvePinned("customer.lookup", 1).status())
                .isEqualTo(ProcessServiceStatus.RETIRED);
        assertThat(catalog.resolveHandler("customer.lookup", 1).handler().key())
                .isEqualTo("echo");
    }

    @Test
    void rejectsActivationWhenImplementationIsNotInstalled() {
        var catalog = new ProcessServiceCatalogService(
                new InMemoryServices(),
                new ProcessServiceHandlerRegistry(List.of()));

        var draft = catalog.create(
                "missing.service", "Missing", "", 1, "not-installed",
                Map.of(), Map.of());

        assertThatThrownBy(() -> catalog.activate(draft.id()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("No ProcessServiceHandler");
    }

    private static final class InMemoryServices implements ProcessServiceRepositoryPort {
        private final Map<UUID,ProcessServiceDefinition> data = new LinkedHashMap<>();

        @Override public ProcessServiceDefinition save(ProcessServiceDefinition value) {
            data.put(value.id(), value); return value;
        }
        @Override public Optional<ProcessServiceDefinition> findById(UUID id) {
            return Optional.ofNullable(data.get(id));
        }
        @Override public Optional<ProcessServiceDefinition> findByKeyAndVersion(String key,int version) {
            return data.values().stream()
                    .filter(v -> v.serviceKey().equals(key) && v.version()==version)
                    .findFirst();
        }
        @Override public Optional<ProcessServiceDefinition> findLatestActiveByKey(String key) {
            return data.values().stream()
                    .filter(v -> v.serviceKey().equals(key) && v.status()==ProcessServiceStatus.ACTIVE)
                    .max(Comparator.comparing(ProcessServiceDefinition::version));
        }
        @Override public List<ProcessServiceDefinition> findAll() { return List.copyOf(data.values()); }
        @Override public boolean existsByKeyAndVersion(String key,int version) {
            return findByKeyAndVersion(key,version).isPresent();
        }
    }
}

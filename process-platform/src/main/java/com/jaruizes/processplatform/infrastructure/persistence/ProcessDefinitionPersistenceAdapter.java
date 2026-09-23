package com.jaruizes.processplatform.infrastructure.persistence;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessDefinitionRepositoryPort;
import com.jaruizes.processplatform.infrastructure.persistence.entity.*;
import com.jaruizes.processplatform.infrastructure.persistence.repository.SpringProcessDefinitionRepository;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Component
public class ProcessDefinitionPersistenceAdapter
        implements ProcessDefinitionRepositoryPort {

    private final SpringProcessDefinitionRepository repository;

    public ProcessDefinitionPersistenceAdapter(
            SpringProcessDefinitionRepository repository) {
        this.repository = repository;
    }

    @Override
    @Transactional
    public ProcessDefinition save(ProcessDefinition definition) {
        var entity = repository.findById(definition.id())
                .orElseGet(ProcessDefinitionJpaEntity::new);
        mapIntoEntity(definition, entity);
        return toDomain(repository.saveAndFlush(entity));
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<ProcessDefinition> findById(UUID id) {
        return repository.findById(id).map(this::toDomain);
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<ProcessDefinition> findByKeyAndVersion(
            String definitionKey,
            int version) {
        return repository.findByDefinitionKeyAndVersion(definitionKey, version)
                .map(this::toDomain);
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<ProcessDefinition> findLatestActiveByKey(String definitionKey) {
        return repository
                .findFirstByDefinitionKeyAndStatusOrderByVersionDesc(
                        definitionKey,
                        ProcessDefinitionStatus.ACTIVE)
                .map(this::toDomain);
    }

    @Override
    @Transactional(readOnly = true)
    public List<ProcessDefinition> findAll() {
        return repository.findAll().stream()
                .map(this::toDomain)
                .sorted(Comparator.comparing(ProcessDefinition::definitionKey)
                        .thenComparing(ProcessDefinition::version).reversed())
                .toList();
    }

    @Override
    public boolean existsByKeyAndVersion(String definitionKey, int version) {
        return repository.existsByDefinitionKeyAndVersion(definitionKey, version);
    }

    private static void mapIntoEntity(
            ProcessDefinition source,
            ProcessDefinitionJpaEntity target) {
        target.setId(source.id());
        target.setDefinitionKey(source.definitionKey());
        target.setName(source.name());
        target.setDescription(source.description());
        target.setVersion(source.version());
        target.setStatus(source.status());
        target.setInputSchema(new LinkedHashMap<>(source.inputSchema()));
        target.setOutputSchema(new LinkedHashMap<>(source.outputSchema()));
        target.setCreatedAt(source.createdAt());
        target.setUpdatedAt(source.updatedAt());
        target.setActivatedAt(source.activatedAt());

        var existing = new HashMap<UUID, ProcessStepDefinitionJpaEntity>();
        target.getSteps().forEach(step -> existing.put(step.getId(), step));

        var incomingIds = source.steps().stream()
                .map(ProcessStepDefinition::id)
                .collect(java.util.stream.Collectors.toSet());
        target.getSteps().removeIf(step -> !incomingIds.contains(step.getId()));

        for (var step : source.steps()) {
            var entity = existing.get(step.id());
            if (entity == null) {
                entity = new ProcessStepDefinitionJpaEntity();
                entity.setId(step.id());
                entity.setDefinition(target);
                target.getSteps().add(entity);
            }
            entity.setStepKey(step.stepKey());
            entity.setName(step.name());
            entity.setDescription(step.description() == null ? "" : step.description());
            entity.setType(step.type());
            entity.setDependsOn(new ArrayList<>(step.dependsOn()));
            entity.setInputSchema(new LinkedHashMap<>(step.inputSchema()));
            entity.setOutputSchema(new LinkedHashMap<>(step.outputSchema()));
            entity.setConfiguration(new LinkedHashMap<>(step.configuration()));
        }
    }

    private ProcessDefinition toDomain(ProcessDefinitionJpaEntity entity) {
        return new ProcessDefinition(
                entity.getId(),
                entity.getDefinitionKey(),
                entity.getName(),
                entity.getDescription(),
                entity.getVersion(),
                entity.getStatus(),
                entity.getInputSchema(),
                entity.getOutputSchema(),
                entity.getSteps().stream().map(step ->
                        new ProcessStepDefinition(
                                step.getId(),
                                step.getStepKey(),
                                step.getName(),
                                step.getDescription(),
                                step.getType(),
                                step.getDependsOn(),
                                step.getInputSchema(),
                                step.getOutputSchema(),
                                step.getConfiguration()
                        )
                ).toList(),
                entity.getCreatedAt(),
                entity.getUpdatedAt(),
                entity.getActivatedAt()
        );
    }
}

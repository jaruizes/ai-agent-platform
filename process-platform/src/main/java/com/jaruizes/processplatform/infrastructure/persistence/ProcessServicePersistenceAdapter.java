package com.jaruizes.processplatform.infrastructure.persistence;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessServiceRepositoryPort;
import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessServiceDefinitionJpaEntity;
import com.jaruizes.processplatform.infrastructure.persistence.repository.SpringProcessServiceDefinitionRepository;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Component
public class ProcessServicePersistenceAdapter implements ProcessServiceRepositoryPort {
    private final SpringProcessServiceDefinitionRepository repository;

    public ProcessServicePersistenceAdapter(SpringProcessServiceDefinitionRepository repository) {
        this.repository = repository;
    }

    @Override
    @Transactional
    public ProcessServiceDefinition save(ProcessServiceDefinition value) {
        var entity = repository.findById(value.id()).orElseGet(ProcessServiceDefinitionJpaEntity::new);
        entity.setId(value.id());
        entity.setServiceKey(value.serviceKey());
        entity.setName(value.name());
        entity.setDescription(value.description());
        entity.setVersion(value.version());
        entity.setStatus(value.status());
        entity.setImplementationKey(value.implementationKey());
        entity.setInputSchema(new LinkedHashMap<>(value.inputSchema()));
        entity.setOutputSchema(new LinkedHashMap<>(value.outputSchema()));
        entity.setCreatedAt(value.createdAt());
        entity.setUpdatedAt(value.updatedAt());
        entity.setActivatedAt(value.activatedAt());
        return map(repository.saveAndFlush(entity));
    }

    @Override @Transactional(readOnly=true)
    public Optional<ProcessServiceDefinition> findById(UUID id){ return repository.findById(id).map(this::map); }

    @Override @Transactional(readOnly=true)
    public Optional<ProcessServiceDefinition> findByKeyAndVersion(String key,int version){
        return repository.findByServiceKeyAndVersion(key, version).map(this::map);
    }

    @Override @Transactional(readOnly=true)
    public Optional<ProcessServiceDefinition> findLatestActiveByKey(String key){
        return repository.findFirstByServiceKeyAndStatusOrderByVersionDesc(key, ProcessServiceStatus.ACTIVE).map(this::map);
    }

    @Override @Transactional(readOnly=true)
    public List<ProcessServiceDefinition> findAll(){
        return repository.findAll().stream()
                .map(this::map)
                .sorted(Comparator.comparing(ProcessServiceDefinition::serviceKey)
                        .thenComparing(ProcessServiceDefinition::version).reversed())
                .toList();
    }

    @Override @Transactional(readOnly=true)
    public boolean existsByKeyAndVersion(String key,int version){
        return repository.existsByServiceKeyAndVersion(key, version);
    }

    private ProcessServiceDefinition map(ProcessServiceDefinitionJpaEntity e){
        return new ProcessServiceDefinition(
                e.getId(), e.getServiceKey(), e.getName(), e.getDescription(), e.getVersion(),
                e.getStatus(), e.getImplementationKey(), e.getInputSchema(), e.getOutputSchema(),
                e.getCreatedAt(), e.getUpdatedAt(), e.getActivatedAt());
    }
}

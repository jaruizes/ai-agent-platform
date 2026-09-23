package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.ProcessDefinition;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProcessDefinitionRepositoryPort {
    ProcessDefinition save(ProcessDefinition definition);
    Optional<ProcessDefinition> findById(UUID id);
    Optional<ProcessDefinition> findByKeyAndVersion(String definitionKey, int version);
    Optional<ProcessDefinition> findLatestActiveByKey(String definitionKey);
    List<ProcessDefinition> findAll();
    boolean existsByKeyAndVersion(String definitionKey, int version);
}

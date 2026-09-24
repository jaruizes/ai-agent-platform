package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.ProcessServiceDefinition;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProcessServiceRepositoryPort {
    ProcessServiceDefinition save(ProcessServiceDefinition service);
    Optional<ProcessServiceDefinition> findById(UUID id);
    Optional<ProcessServiceDefinition> findByKeyAndVersion(String key, int version);
    Optional<ProcessServiceDefinition> findLatestActiveByKey(String key);
    List<ProcessServiceDefinition> findAll();
    boolean existsByKeyAndVersion(String key, int version);
}

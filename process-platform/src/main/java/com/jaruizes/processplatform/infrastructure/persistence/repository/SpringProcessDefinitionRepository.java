package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.domain.model.ProcessDefinitionStatus;
import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessDefinitionJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface SpringProcessDefinitionRepository
        extends JpaRepository<ProcessDefinitionJpaEntity, UUID> {

    boolean existsByDefinitionKeyAndVersion(String definitionKey, int version);

    Optional<ProcessDefinitionJpaEntity> findByDefinitionKeyAndVersion(
            String definitionKey,
            int version);

    Optional<ProcessDefinitionJpaEntity>
    findFirstByDefinitionKeyAndStatusOrderByVersionDesc(
            String definitionKey,
            ProcessDefinitionStatus status);
}

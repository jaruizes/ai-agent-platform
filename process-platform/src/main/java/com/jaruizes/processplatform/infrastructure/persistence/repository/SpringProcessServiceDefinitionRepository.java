package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.domain.model.ProcessServiceStatus;
import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessServiceDefinitionJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface SpringProcessServiceDefinitionRepository
        extends JpaRepository<ProcessServiceDefinitionJpaEntity, UUID> {
    Optional<ProcessServiceDefinitionJpaEntity> findByServiceKeyAndVersion(String serviceKey, int version);
    Optional<ProcessServiceDefinitionJpaEntity> findFirstByServiceKeyAndStatusOrderByVersionDesc(
            String serviceKey, ProcessServiceStatus status);
    boolean existsByServiceKeyAndVersion(String serviceKey, int version);
}

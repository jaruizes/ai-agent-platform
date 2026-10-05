package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessExecutionCommandOutboxJpaEntity;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface SpringProcessExecutionCommandOutboxRepository
        extends JpaRepository<ProcessExecutionCommandOutboxJpaEntity, UUID> {

    List<ProcessExecutionCommandOutboxJpaEntity>
    findByPublishedAtIsNullOrderByCreatedAtAsc(Pageable pageable);
}

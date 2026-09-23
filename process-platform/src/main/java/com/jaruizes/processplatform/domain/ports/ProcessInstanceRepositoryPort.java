package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.ProcessInstance;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

public interface ProcessInstanceRepositoryPort {
    ProcessInstance create(ProcessInstance instance);
    Optional<ProcessInstance> findById(UUID id);
    List<ProcessInstance> findAll();
    ProcessInstance updateContext(UUID id, Map<String,Object> context);
}

package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

public interface ProcessRuntimeRepositoryPort {
    Optional<ProcessInstance> findInstance(UUID instanceId);
    Optional<ProcessInstance> findByDelegatedExecutionId(UUID executionId);
    List<ProcessInstance> findRunnableInstances();

    ProcessInstance updateInstanceStatus(UUID instanceId, ProcessInstanceStatus status);
    ProcessInstance updateStepStatus(UUID instanceId, String stepKey, ProcessStepStatus status);
    ProcessInstance startStep(UUID instanceId, String stepKey, Map<String,Object> input);
    ProcessInstance waitForAgent(UUID instanceId, String stepKey, UUID executionId);
    ProcessInstance completeStep(UUID instanceId, String stepKey, Map<String,Object> output, Map<String,Object> mergedContext);
    ProcessInstance failStep(UUID instanceId, String stepKey, Map<String,Object> error);
    ProcessInstance completeInstance(UUID instanceId);
    ProcessInstance failInstance(UUID instanceId);
}

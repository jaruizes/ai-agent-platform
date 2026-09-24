package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

public interface ProcessRuntimeRepositoryPort {
    Optional<ProcessInstance> findInstance(UUID instanceId);
    Optional<ProcessInstance> findByDelegatedExecutionId(UUID executionId);
    List<ProcessInstance> findRunnableInstances();

    ProcessInstance updateInstanceStatus(UUID instanceId, ProcessInstanceStatus status);
    boolean markReady(UUID instanceId, String stepKey);
    boolean claimReady(UUID instanceId, String stepKey, Map<String,Object> input, Long timeoutSeconds);
    boolean resetRunningStep(UUID instanceId, String stepKey);
    ProcessInstance retryStep(UUID instanceId, String stepKey, Map<String,Object> error, Instant availableAt);
    ProcessInstance waitStep(UUID instanceId, String stepKey);
    ProcessInstance skipStep(UUID instanceId, String stepKey, Map<String,Object> output);
    ProcessInstance delegateAgent(UUID instanceId, String stepKey, ExecutionCommand command);
    ProcessInstance completeStep(UUID instanceId, String stepKey, Map<String,Object> output);
    ProcessInstance failStep(UUID instanceId, String stepKey, Map<String,Object> error);
    ProcessInstance completeInstance(UUID instanceId);
    ProcessInstance failInstance(UUID instanceId);
    ProcessInstance cancelInstance(UUID instanceId);
}

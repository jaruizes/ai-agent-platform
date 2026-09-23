package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.*;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Service
public class ProcessRuntimeService {

    private final ProcessRuntimeRepositoryPort runtime;
    private final ProcessDefinitionRepositoryPort definitions;
    private final ProcessContractValidator contracts;
    private final ProcessServiceHandlerRegistry serviceHandlers;
    private final AgentPlatformIntegrationService agentPlatform;
    private final long staleStepSeconds;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public ProcessRuntimeService(
            ProcessRuntimeRepositoryPort runtime,
            ProcessDefinitionRepositoryPort definitions,
            ProcessContractValidator contracts,
            ProcessServiceHandlerRegistry serviceHandlers,
            AgentPlatformIntegrationService agentPlatform,
            @Value("${process.runtime.step-stale-seconds:60}")
            long staleStepSeconds) {
        this.runtime = runtime;
        this.definitions = definitions;
        this.contracts = contracts;
        this.serviceHandlers = serviceHandlers;
        this.agentPlatform = agentPlatform;
        this.staleStepSeconds = Math.max(1, staleStepSeconds);
    }

    public ProcessInstance start(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.COMPLETED
                || instance.status() == ProcessInstanceStatus.FAILED
                || instance.status() == ProcessInstanceStatus.CANCELLED) {
            throw new IllegalStateException(
                    "Process instance is terminal: " + instance.status());
        }

        var definition = requireDefinition(instance.definitionId());
        contracts.validate("process.input", definition.inputSchema(), instance.input());

        var running = runtime.updateInstanceStatus(
                instanceId,
                ProcessInstanceStatus.RUNNING);
        scheduleAdvance(instanceId);
        return running;
    }

    public ProcessInstance get(UUID instanceId) {
        return requireInstance(instanceId);
    }

    @EventListener
    public void onAgentExecutionEvent(AgentExecutionEventReceived received) {
        var event = received.event();
        if (event == null || !event.isTerminal()
                || event.execution() == null
                || event.execution().executionId() == null) {
            return;
        }

        runtime.findByDelegatedExecutionId(event.execution().executionId())
                .ifPresent(instance -> executor.submit(
                        () -> handleTerminalAgentEvent(instance, event)));
    }

    @Scheduled(fixedDelayString = "${process.runtime.recovery-delay-ms:2000}")
    public void recoverRunnableInstances() {
        var cutoff = java.time.Instant.now().minusSeconds(staleStepSeconds);
        for (var instance : runtime.findRunnableInstances()) {
            for (var step : instance.steps()) {
                if ((step.type() == ProcessStepType.SERVICE
                        || step.type() == ProcessStepType.AGENTIC_EXECUTION)
                        && step.status() == ProcessStepStatus.RUNNING
                        && step.startedAt() != null
                        && step.startedAt().isBefore(cutoff)) {
                    runtime.resetRunningStep(instance.id(), step.stepKey());
                }
            }
            scheduleAdvance(instance.id());
        }
    }

    private void advance(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.COMPLETED
                || instance.status() == ProcessInstanceStatus.FAILED
                || instance.status() == ProcessInstanceStatus.CANCELLED) {
            return;
        }

        var definition = requireDefinition(instance.definitionId());
        var stepDefinitions = byKey(definition.steps());
        var stepInstances = instance.steps().stream()
                .collect(java.util.stream.Collectors.toMap(
                        ProcessStepInstance::stepKey,
                        step -> step));

        if (stepInstances.values().stream()
                .anyMatch(step -> step.status() == ProcessStepStatus.FAILED)) {
            runtime.failInstance(instanceId);
            return;
        }

        if (!stepInstances.isEmpty()
                && stepInstances.values().stream()
                .allMatch(step -> step.status() == ProcessStepStatus.COMPLETED
                        || step.status() == ProcessStepStatus.SKIPPED)) {
            try {
                contracts.validate(
                        "process.output",
                        definition.outputSchema(),
                        instance.context());
                runtime.completeInstance(instanceId);
            } catch (Exception outputContractError) {
                runtime.failInstance(instanceId);
            }
            return;
        }

        var ready = new ArrayList<String>();
        stepInstances.values().stream()
                .filter(step -> step.status() == ProcessStepStatus.READY)
                .map(ProcessStepInstance::stepKey)
                .forEach(ready::add);
        for (var stepDefinition : definition.steps()) {
            var step = stepInstances.get(stepDefinition.stepKey());
            if (step == null || step.status() != ProcessStepStatus.PENDING) {
                continue;
            }

            var dependenciesCompleted = stepDefinition.dependsOn().stream()
                    .allMatch(dep -> {
                        var dependency = stepInstances.get(dep);
                        return dependency != null
                                && (dependency.status() == ProcessStepStatus.COMPLETED
                                    || dependency.status() == ProcessStepStatus.SKIPPED);
                    });
            if (dependenciesCompleted
                    && runtime.markReady(instanceId, stepDefinition.stepKey())) {
                ready.add(stepDefinition.stepKey());
            }
        }

        for (var stepKey : ready) {
            executor.submit(() -> executeReadyStep(instanceId, stepKey));
        }

        var refreshed = requireInstance(instanceId);
        var hasActive = refreshed.steps().stream().anyMatch(step ->
                step.status() == ProcessStepStatus.READY
                        || step.status() == ProcessStepStatus.RUNNING);
        var hasWaiting = refreshed.steps().stream().anyMatch(step ->
                step.status() == ProcessStepStatus.WAITING);

        if (!hasActive && hasWaiting
                && refreshed.status() != ProcessInstanceStatus.WAITING) {
            runtime.updateInstanceStatus(instanceId, ProcessInstanceStatus.WAITING);
        }
    }

    private void executeReadyStep(UUID instanceId, String stepKey) {
        var instance = requireInstance(instanceId);
        var definition = requireDefinition(instance.definitionId());
        var stepDefinition = byKey(definition.steps()).get(stepKey);
        if (stepDefinition == null) {
            failStep(instanceId, stepKey, "STEP_DEFINITION_NOT_FOUND",
                    "Step definition not found: " + stepKey);
            return;
        }

        var input = buildStepInput(instance, stepDefinition);
        try {
            contracts.validate(
                    "step.%s.input".formatted(stepKey),
                    stepDefinition.inputSchema(),
                    input);
        } catch (Exception validationError) {
            failStep(instanceId, stepKey, "INPUT_CONTRACT_VIOLATION",
                    validationError.getMessage());
            return;
        }

        if (!runtime.claimReady(instanceId, stepKey, input)) {
            return;
        }

        try {
            switch (stepDefinition.type()) {
                case SERVICE -> executeService(instanceId, stepDefinition, input);
                case AGENTIC_EXECUTION ->
                        executeAgentic(instanceId, stepDefinition, input);
                default -> failStep(
                        instanceId,
                        stepKey,
                        "UNSUPPORTED_STEP_TYPE",
                        "M9.3 does not execute step type "
                                + stepDefinition.type());
            }
        } catch (Exception exception) {
            failStep(
                    instanceId,
                    stepKey,
                    "STEP_EXECUTION_ERROR",
                    exception.getMessage());
        }
    }

    private void executeService(
            UUID instanceId,
            ProcessStepDefinition step,
            Map<String,Object> input) {
        var handlerKey = stringValue(step.configuration().get("handler"));
        var handler = serviceHandlers.require(handlerKey);
        var output = handler.execute(input, step.configuration());
        completeStep(instanceId, step, output == null ? Map.of() : output);
    }

    @SuppressWarnings("unchecked")
    private void executeAgentic(
            UUID instanceId,
            ProcessStepDefinition step,
            Map<String,Object> input) {
        var instance = requireInstance(instanceId);
        var configuration = step.configuration();
        var intent = stringValue(configuration.get("intent"));
        if (intent == null || intent.isBlank()) {
            throw new IllegalArgumentException(
                    "AGENTIC_EXECUTION step requires configuration.intent");
        }

        var instructions = configuration.get("instructions") instanceof Collection<?> items
                ? items.stream().map(String::valueOf).toList()
                : List.<String>of();
        var metadata = configuration.get("metadata") instanceof Map<?,?> values
                ? new LinkedHashMap<String,Object>((Map<String,Object>) values)
                : new LinkedHashMap<String,Object>();
        metadata.put("processInstanceId", instance.id().toString());
        metadata.put("processStepKey", step.stepKey());
        metadata.put("processDefinitionKey", instance.definitionKey());
        metadata.put("processDefinitionVersion", instance.definitionVersion());

        var prepared = agentPlatform.prepare(new AgentExecutionRequest(
                stringValue(configuration.getOrDefault("name", step.stepKey())),
                intent,
                input,
                Map.of(),
                instructions,
                metadata,
                null,
                instance.correlationId(),
                step.id().toString(),
                stringValue(configuration.get("tenantId"))
        ));

        runtime.delegateAgent(
                instanceId,
                step.stepKey(),
                prepared.command());
    }

    private void handleTerminalAgentEvent(
            ProcessInstance instance,
            ExecutionEvent event) {
        var step = instance.steps().stream()
                .filter(candidate -> event.execution().executionId()
                        .equals(candidate.delegatedExecutionId()))
                .findFirst()
                .orElse(null);
        if (step == null || step.status() != ProcessStepStatus.WAITING) {
            return;
        }

        if (!event.isCompleted()) {
            var error = event.execution().error();
            failStep(
                    instance.id(),
                    step.stepKey(),
                    "AGENT_EXECUTION_FAILED",
                    error == null
                            ? "Delegated Agent Platform execution ended with status "
                                + event.execution().status()
                            : String.valueOf(error.getOrDefault(
                                "message",
                                "Delegated Agent Platform execution failed")));
            return;
        }

        var definition = requireDefinition(instance.definitionId());
        var stepDefinition = byKey(definition.steps()).get(step.stepKey());
        var result = event.execution().result() == null
                ? Map.<String,Object>of()
                : new LinkedHashMap<>(event.execution().result());

        completeStep(instance.id(), stepDefinition, result);
    }

    private void completeStep(
            UUID instanceId,
            ProcessStepDefinition step,
            Map<String,Object> output) {
        try {
            contracts.validate(
                    "step.%s.output".formatted(step.stepKey()),
                    step.outputSchema(),
                    output);

            runtime.completeStep(
                    instanceId,
                    step.stepKey(),
                    output);
            scheduleAdvance(instanceId);
        } catch (Exception validationError) {
            failStep(
                    instanceId,
                    step.stepKey(),
                    "OUTPUT_CONTRACT_VIOLATION",
                    validationError.getMessage());
        }
    }

    private Map<String,Object> buildStepInput(
            ProcessInstance instance,
            ProcessStepDefinition step) {
        var dependencies = new LinkedHashMap<String,Object>();
        var byKey = instance.steps().stream()
                .collect(java.util.stream.Collectors.toMap(
                        ProcessStepInstance::stepKey,
                        value -> value));
        for (var dependencyKey : step.dependsOn()) {
            var dependency = byKey.get(dependencyKey);
            dependencies.put(
                    dependencyKey,
                    dependency == null || dependency.output() == null
                            ? Map.of()
                            : dependency.output());
        }

        var input = new LinkedHashMap<String,Object>();
        input.put("processInput", instance.input());
        input.put("context", instance.context());
        input.put("dependencies", dependencies);
        return input;
    }

    private void failStep(
            UUID instanceId,
            String stepKey,
            String code,
            String message) {
        var error = new LinkedHashMap<String,Object>();
        error.put("code", code);
        error.put("message", message == null ? code : message);
        runtime.failStep(instanceId, stepKey, error);
    }

    private ProcessInstance requireInstance(UUID id) {
        return runtime.findInstance(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + id));
    }

    private ProcessDefinition requireDefinition(UUID id) {
        return definitions.findById(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process definition not found: " + id));
    }

    private static Map<String,ProcessStepDefinition> byKey(
            List<ProcessStepDefinition> steps) {
        return steps.stream().collect(
                java.util.stream.Collectors.toMap(
                        ProcessStepDefinition::stepKey,
                        step -> step,
                        (left, right) -> left,
                        LinkedHashMap::new));
    }

    private static String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private void scheduleAdvance(UUID instanceId) {
        executor.submit(() -> {
            try {
                advance(instanceId);
            } catch (Exception ignored) {
                // Durable state remains authoritative; the recovery loop will retry progression.
            }
        });
    }

    @PreDestroy
    void shutdown() {
        executor.shutdownNow();
    }
}

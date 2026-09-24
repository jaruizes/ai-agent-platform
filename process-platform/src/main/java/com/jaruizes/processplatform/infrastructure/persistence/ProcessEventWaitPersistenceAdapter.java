package com.jaruizes.processplatform.infrastructure.persistence;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessEventWaitRepositoryPort;
import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessEventWaitJpaEntity;
import com.jaruizes.processplatform.infrastructure.persistence.repository.SpringProcessEventWaitRepository;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;

@Component
public class ProcessEventWaitPersistenceAdapter implements ProcessEventWaitRepositoryPort {
    private final SpringProcessEventWaitRepository repository;
    public ProcessEventWaitPersistenceAdapter(SpringProcessEventWaitRepository repository){this.repository=repository;}

    @Override @Transactional
    public ProcessEventWait createIfAbsent(ProcessEventWait wait){
        return repository.findByProcessInstanceIdAndStepKey(wait.processInstanceId(), wait.stepKey())
                .map(this::map)
                .orElseGet(() -> {
                    var e=new ProcessEventWaitJpaEntity();
                    e.setId(wait.id()); e.setProcessInstanceId(wait.processInstanceId()); e.setStepKey(wait.stepKey());
                    e.setEventType(wait.eventType()); e.setCorrelationId(wait.correlationId()); e.setStatus(wait.status());
                    e.setPayload(new LinkedHashMap<>(wait.payload())); e.setCreatedAt(wait.createdAt()); e.setConsumedAt(wait.consumedAt());
                    return map(repository.saveAndFlush(e));
                });
    }

    @Override @Transactional(readOnly=true)
    public List<ProcessEventWait> findWaiting(String eventType,String correlationId){
        return repository.findByEventTypeAndCorrelationIdAndStatus(eventType,correlationId,ProcessEventWaitStatus.WAITING)
                .stream().map(this::map).toList();
    }

    @Override @Transactional
    public ProcessEventWait consume(UUID id,Map<String,Object> payload){
        var e=repository.findById(id).orElseThrow(() -> new NoSuchElementException("Process event wait not found: "+id));
        if(e.getStatus()!=ProcessEventWaitStatus.WAITING) return map(e);
        e.setPayload(new LinkedHashMap<>(payload==null?Map.of():payload));
        e.setStatus(ProcessEventWaitStatus.CONSUMED); e.setConsumedAt(Instant.now());
        return map(repository.saveAndFlush(e));
    }

    @Override @Transactional
    public void cancelWaitingForInstance(UUID processInstanceId){
        for(var e:repository.findByProcessInstanceIdAndStatus(processInstanceId,ProcessEventWaitStatus.WAITING)){
            e.setStatus(ProcessEventWaitStatus.CANCELLED); e.setConsumedAt(Instant.now()); repository.save(e);
        }
    }

    private ProcessEventWait map(ProcessEventWaitJpaEntity e){
        return new ProcessEventWait(e.getId(),e.getProcessInstanceId(),e.getStepKey(),e.getEventType(),
                e.getCorrelationId(),e.getStatus(),e.getPayload(),e.getCreatedAt(),e.getConsumedAt());
    }
}

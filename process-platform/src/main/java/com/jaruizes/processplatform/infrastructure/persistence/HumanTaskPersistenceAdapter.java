package com.jaruizes.processplatform.infrastructure.persistence;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.HumanTaskRepositoryPort;
import com.jaruizes.processplatform.infrastructure.persistence.entity.HumanTaskJpaEntity;
import com.jaruizes.processplatform.infrastructure.persistence.repository.SpringHumanTaskRepository;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;

@Component
public class HumanTaskPersistenceAdapter implements HumanTaskRepositoryPort {
    private final SpringHumanTaskRepository repository;
    public HumanTaskPersistenceAdapter(SpringHumanTaskRepository repository){this.repository=repository;}

    @Override @Transactional
    public HumanTask createIfAbsent(HumanTask task){
        return repository.findByProcessInstanceIdAndStepKeyAndIteration(
                        task.processInstanceId(), task.stepKey(), task.iteration())
                .map(this::map)
                .orElseGet(() -> {
                    var e=new HumanTaskJpaEntity();
                    e.setId(task.id()); e.setProcessInstanceId(task.processInstanceId()); e.setStepKey(task.stepKey());
                    e.setIteration(task.iteration());
                    e.setTitle(task.title()); e.setDescription(task.description());
                    e.setPayload(new LinkedHashMap<>(task.payload())); e.setStatus(task.status());
                    e.setDecision(task.decision()); e.setResult(new LinkedHashMap<>(task.result()));
                    e.setCreatedAt(task.createdAt()); e.setCompletedAt(task.completedAt());
                    return map(repository.saveAndFlush(e));
                });
    }

    @Override @Transactional(readOnly=true)
    public Optional<HumanTask> findById(UUID id){return repository.findById(id).map(this::map);}
    @Override @Transactional(readOnly=true)
    public List<HumanTask> findAll(){return repository.findAll().stream().map(this::map).toList();}
    @Override @Transactional(readOnly=true)
    public List<HumanTask> findPending(){
        return repository.findByStatusOrderByCreatedAtAsc(HumanTaskStatus.PENDING).stream().map(this::map).toList();
    }

    @Override @Transactional
    public HumanTask complete(UUID id,String decision,Map<String,Object> result){
        var e=repository.findLockedById(id).orElseThrow(() -> new NoSuchElementException("Human task not found: "+id));
        if(e.getStatus()!=HumanTaskStatus.PENDING) return map(e);
        e.setDecision(decision); e.setResult(new LinkedHashMap<>(result==null?Map.of():result));
        e.setStatus(HumanTaskStatus.COMPLETED); e.setCompletedAt(Instant.now());
        return map(repository.saveAndFlush(e));
    }

    @Override @Transactional
    public void cancelPendingForInstance(UUID processInstanceId){
        for(var e:repository.findByProcessInstanceIdAndStatus(processInstanceId,HumanTaskStatus.PENDING)){
            e.setStatus(HumanTaskStatus.CANCELLED); e.setCompletedAt(Instant.now()); repository.save(e);
        }
    }

    private HumanTask map(HumanTaskJpaEntity e){
        return new HumanTask(e.getId(),e.getProcessInstanceId(),e.getStepKey(),e.getIteration(),e.getTitle(),e.getDescription(),
                e.getPayload(),e.getStatus(),e.getDecision(),e.getResult(),e.getCreatedAt(),e.getCompletedAt());
    }
}

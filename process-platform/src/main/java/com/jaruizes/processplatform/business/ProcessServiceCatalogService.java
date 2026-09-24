package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessServiceRepositoryPort;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

@Service
public class ProcessServiceCatalogService {
    private final ProcessServiceRepositoryPort repository;
    private final ProcessServiceHandlerRegistry handlers;

    public ProcessServiceCatalogService(
            ProcessServiceRepositoryPort repository,
            ProcessServiceHandlerRegistry handlers) {
        this.repository = repository;
        this.handlers = handlers;
    }

    public ProcessServiceDefinition create(
            String serviceKey,
            String name,
            String description,
            int version,
            String implementationKey,
            Map<String,Object> inputSchema,
            Map<String,Object> outputSchema) {
        if(serviceKey==null||serviceKey.isBlank()) throw new IllegalArgumentException("serviceKey is required");
        if(name==null||name.isBlank()) throw new IllegalArgumentException("name is required");
        if(version<1) throw new IllegalArgumentException("version must be >= 1");
        if(implementationKey==null||implementationKey.isBlank()) throw new IllegalArgumentException("implementationKey is required");
        if(repository.existsByKeyAndVersion(serviceKey,version))
            throw new IllegalArgumentException("Process service '%s' version %d already exists".formatted(serviceKey,version));

        var now=Instant.now();
        return repository.save(new ProcessServiceDefinition(
                UUID.randomUUID(),serviceKey.trim(),name.trim(),description==null?"":description,
                version,ProcessServiceStatus.DRAFT,implementationKey.trim(),
                safe(inputSchema),safe(outputSchema),now,now,null));
    }

    public ProcessServiceDefinition activate(UUID id){
        var current=get(id);
        if(current.status()==ProcessServiceStatus.ACTIVE) return current;
        if(current.status()!=ProcessServiceStatus.DRAFT)
            throw new IllegalStateException("Only DRAFT process services can be activated");
        handlers.require(current.implementationKey());
        return repository.save(copy(current,ProcessServiceStatus.ACTIVE,Instant.now()));
    }

    public ProcessServiceDefinition retire(UUID id){
        var current=get(id);
        if(current.status()==ProcessServiceStatus.RETIRED) return current;
        if(current.status()!=ProcessServiceStatus.ACTIVE)
            throw new IllegalStateException("Only ACTIVE process services can be retired");
        return repository.save(copy(current,ProcessServiceStatus.RETIRED,current.activatedAt()));
    }

    public ProcessServiceDefinition get(UUID id){
        return repository.findById(id).orElseThrow(() -> new NoSuchElementException("Process service not found: "+id));
    }

    public List<ProcessServiceDefinition> list(){return repository.findAll();}

    public List<ProcessServiceDefinition> listActive(){
        return repository.findAll().stream()
                .filter(value -> value.status()==ProcessServiceStatus.ACTIVE)
                .toList();
    }

    public ProcessServiceDefinition resolveActive(String key,Integer version){
        if(key==null||key.isBlank()) throw new IllegalArgumentException("SERVICE requires configuration.serviceKey");
        return version==null
                ? repository.findLatestActiveByKey(key).orElseThrow(() -> new NoSuchElementException("No ACTIVE process service found for key: "+key))
                : repository.findByKeyAndVersion(key,version)
                    .filter(v -> v.status()==ProcessServiceStatus.ACTIVE)
                    .orElseThrow(() -> new NoSuchElementException("ACTIVE process service '%s' version %d not found".formatted(key,version)));
    }

    public ProcessServiceDefinition resolvePinned(String key,int version){
        return repository.findByKeyAndVersion(key,version)
                .filter(v -> v.status()!=ProcessServiceStatus.DRAFT)
                .orElseThrow(() -> new NoSuchElementException(
                        "Published process service '%s' version %d not found"
                                .formatted(key,version)));
    }

    public ProcessServiceHandlerPortBinding resolveHandler(String key,int version){
        var service=resolvePinned(key,version);
        return new ProcessServiceHandlerPortBinding(service,handlers.require(service.implementationKey()));
    }

    public record ProcessServiceHandlerPortBinding(
            ProcessServiceDefinition service,
            com.jaruizes.processplatform.domain.ports.ProcessServiceHandlerPort handler) {}

    private static ProcessServiceDefinition copy(ProcessServiceDefinition v,ProcessServiceStatus status,Instant activatedAt){
        return new ProcessServiceDefinition(v.id(),v.serviceKey(),v.name(),v.description(),v.version(),status,
                v.implementationKey(),v.inputSchema(),v.outputSchema(),v.createdAt(),Instant.now(),activatedAt);
    }
    private static Map<String,Object> safe(Map<String,Object> v){return v==null?Map.of():new LinkedHashMap<>(v);}
}

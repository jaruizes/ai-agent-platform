package com.jaruizes.processplatform.infrastructure.service;

import com.jaruizes.processplatform.domain.ports.ProcessServiceHandlerPort;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Generic deterministic handler useful for integration tests and simple pass-through steps.
 * Business-specific handlers belong in adapters/plugins built on the same port.
 */
@Component
public class EchoProcessServiceHandler implements ProcessServiceHandlerPort {

    @Override
    public String key() {
        return "echo";
    }

    @Override
    public Map<String,Object> execute(
            Map<String,Object> input,
            Map<String,Object> configuration) {
        return new LinkedHashMap<>(input);
    }
}

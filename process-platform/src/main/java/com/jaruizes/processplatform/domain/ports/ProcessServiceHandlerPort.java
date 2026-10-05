package com.jaruizes.processplatform.domain.ports;

import java.util.Map;

public interface ProcessServiceHandlerPort {
    String key();

    default void validateConfiguration(Map<String,Object> serviceConfiguration) {
        // Most adapters do not require catalog-level configuration.
    }

    Map<String,Object> execute(
            Map<String,Object> input,
            Map<String,Object> serviceConfiguration,
            Map<String,Object> stepConfiguration);
}

package com.jaruizes.processplatform.domain.ports;

import java.util.Map;

public interface ProcessServiceHandlerPort {
    String key();
    Map<String,Object> execute(Map<String,Object> input, Map<String,Object> configuration);
}

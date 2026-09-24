package com.jaruizes.processplatform.infrastructure.service;

import com.jaruizes.processplatform.domain.ports.ProcessServiceHandlerPort;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

@Component
public class HttpProcessServiceHandler implements ProcessServiceHandlerPort {

    private static final Set<String> ALLOWED_METHODS =
            Set.of("GET", "POST", "PUT", "PATCH", "DELETE");

    private final RestClient client;

    public HttpProcessServiceHandler(RestClient.Builder builder) {
        this.client = builder.build();
    }

    @Override
    public String key() {
        return "http";
    }

    @Override
    public void validateConfiguration(Map<String,Object> configuration) {
        var url = string(configuration.get("url"));
        if (url == null || url.isBlank()) {
            throw new IllegalArgumentException(
                    "HTTP process service requires configuration.url");
        }

        var uri = URI.create(url);
        if (uri.getScheme() == null
                || (!uri.getScheme().equalsIgnoreCase("http")
                    && !uri.getScheme().equalsIgnoreCase("https"))) {
            throw new IllegalArgumentException(
                    "HTTP process service URL must use http or https");
        }

        var method = method(configuration);
        if (!ALLOWED_METHODS.contains(method)) {
            throw new IllegalArgumentException(
                    "Unsupported HTTP process service method: " + method);
        }

        var headers = configuration.get("headers");
        if (headers != null && !(headers instanceof Map<?,?>)) {
            throw new IllegalArgumentException(
                    "HTTP process service configuration.headers must be an object");
        }
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String,Object> execute(
            Map<String,Object> input,
            Map<String,Object> serviceConfiguration,
            Map<String,Object> stepConfiguration) {

        validateConfiguration(serviceConfiguration);

        var url = string(serviceConfiguration.get("url"));
        var methodName = method(serviceConfiguration);
        var method = HttpMethod.valueOf(methodName);

        RestClient.RequestBodySpec request = client.method(method).uri(url);

        var configuredHeaders = serviceConfiguration.get("headers");
        if (configuredHeaders instanceof Map<?,?> headers) {
            request.headers(httpHeaders -> headers.forEach((name, value) -> {
                if (value instanceof Iterable<?> values) {
                    for (var item : values) {
                        httpHeaders.add(String.valueOf(name), String.valueOf(item));
                    }
                } else if (value != null) {
                    httpHeaders.add(String.valueOf(name), String.valueOf(value));
                }
            }));
        }

        if (method != HttpMethod.GET && method != HttpMethod.DELETE) {
            request.body(input);
        }

        var response = request.retrieve().toEntity(Object.class);
        var body = response.getBody();

        if (body == null) {
            return Map.of();
        }
        if (body instanceof Map<?,?> map) {
            return new LinkedHashMap<>((Map<String,Object>) map);
        }

        var wrapped = new LinkedHashMap<String,Object>();
        wrapped.put("value", body);
        return wrapped;
    }

    private static String method(Map<String,Object> configuration) {
        var configured = string(configuration.get("method"));
        return configured == null || configured.isBlank()
                ? "POST"
                : configured.toUpperCase(java.util.Locale.ROOT);
    }

    private static String string(Object value) {
        return value == null ? null : String.valueOf(value);
    }
}

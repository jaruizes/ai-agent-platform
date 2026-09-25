package com.jaruizes.processplatform.infrastructure.google;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Map;

@Component
public class GoogleOAuthAccessTokenProvider {

    private final RestClient client;
    private final ObjectMapper objectMapper;
    private final Path tokenPath;
    private final String tokenEndpoint;

    private volatile CachedToken cached;

    public GoogleOAuthAccessTokenProvider(
            RestClient.Builder builder,
            ObjectMapper objectMapper,
            @Value("${google.oauth.token-path:/run/secrets/google/google-token.json}")
            String tokenPath,
            @Value("${google.oauth.token-endpoint:https://oauth2.googleapis.com/token}")
            String tokenEndpoint) {
        this.client = builder.build();
        this.objectMapper = objectMapper;
        this.tokenPath = Path.of(tokenPath);
        this.tokenEndpoint = tokenEndpoint;
    }

    public String accessToken() {
        var current = cached;
        var now = Instant.now();
        if (current != null && current.expiresAt().isAfter(now.plusSeconds(60))) {
            return current.value();
        }

        synchronized (this) {
            current = cached;
            now = Instant.now();
            if (current != null && current.expiresAt().isAfter(now.plusSeconds(60))) {
                return current.value();
            }

            var credentials = readStoredToken();
            var form = new LinkedMultiValueMap<String,String>();
            form.add("client_id", required(credentials, "client_id"));
            form.add("client_secret", required(credentials, "client_secret"));
            form.add("refresh_token", required(credentials, "refresh_token"));
            form.add("grant_type", "refresh_token");

            @SuppressWarnings("unchecked")
            var response = client.post()
                    .uri(tokenEndpoint)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(form)
                    .retrieve()
                    .body(Map.class);

            if (response == null) {
                throw new IllegalStateException(
                        "Google OAuth token endpoint returned an empty response");
            }

            var value = String.valueOf(response.getOrDefault("access_token", "")).trim();
            if (value.isBlank()) {
                throw new IllegalStateException(
                        "Google OAuth token endpoint did not return access_token");
            }

            var expiresIn = number(response.get("expires_in"), 3600L);
            var expiresAt = Instant.now().plusSeconds(Math.max(120L, expiresIn));
            cached = new CachedToken(value, expiresAt);
            return value;
        }
    }

    private Map<String,Object> readStoredToken() {
        if (!Files.isRegularFile(tokenPath)) {
            throw new IllegalStateException(
                    "Google OAuth token file not found: " + tokenPath
                            + ". Run the Google Workspace MCP auth flow first.");
        }
        try {
            return objectMapper.readValue(
                    Files.readString(tokenPath),
                    new TypeReference<>() {});
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Could not read Google OAuth token file: " + tokenPath,
                    exception);
        }
    }

    private static String required(Map<String,Object> values, String key) {
        var value = String.valueOf(values.getOrDefault(key, "")).trim();
        if (value.isBlank()) {
            throw new IllegalStateException(
                    "Google OAuth token file is missing '" + key + "'");
        }
        return value;
    }

    private static long number(Object value, long fallback) {
        if (value instanceof Number number) return number.longValue();
        if (value == null) return fallback;
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private record CachedToken(String value, Instant expiresAt) {}
}

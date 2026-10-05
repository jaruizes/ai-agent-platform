package com.jaruizes.processplatform.infrastructure.service;

import com.jaruizes.processplatform.domain.ports.ProcessServiceHandlerPort;
import com.jaruizes.processplatform.infrastructure.google.GoogleOAuthAccessTokenProvider;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.util.*;

@Component
public class GoogleDriveFolderProcessServiceHandler implements ProcessServiceHandlerPort {

    private final RestClient client;
    private final GoogleOAuthAccessTokenProvider tokenProvider;

    public GoogleDriveFolderProcessServiceHandler(
            RestClient.Builder builder,
            GoogleOAuthAccessTokenProvider tokenProvider) {
        this.client = builder.build();
        this.tokenProvider = tokenProvider;
    }

    @Override
    public String key() {
        return "google-drive-folder";
    }

    @Override
    public void validateConfiguration(Map<String,Object> configuration) {
        var folderPath = string(configuration.getOrDefault(
                "folderIdPath",
                "processInput.driveFolderId"));
        if (folderPath == null || folderPath.isBlank()) {
            throw new IllegalArgumentException(
                    "Google Drive process service requires configuration.folderIdPath");
        }
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String,Object> execute(
            Map<String,Object> input,
            Map<String,Object> serviceConfiguration,
            Map<String,Object> stepConfiguration) {

        validateConfiguration(serviceConfiguration);

        var accessToken = tokenProvider.accessToken();

        var folderPath = string(serviceConfiguration.getOrDefault(
                "folderIdPath",
                "processInput.driveFolderId"));
        var folderId = string(readPath(input, folderPath));
        if (folderId == null || folderId.isBlank()) {
            throw new IllegalArgumentException(
                    "Google Drive folder id was not found at input path: " + folderPath);
        }

        var apiBase = string(serviceConfiguration.getOrDefault(
                "apiBaseUrl",
                "https://www.googleapis.com/drive/v3"));
        var pageSize = integer(serviceConfiguration.getOrDefault("pageSize", 100));
        pageSize = Math.max(1, Math.min(pageSize, 1000));

        var documents = new ArrayList<Map<String,Object>>();
        String pageToken = null;

        do {
            var builder = UriComponentsBuilder
                    .fromUriString(apiBase + "/files")
                    .queryParam(
                            "q",
                            "'" + folderId.replace("'", "\\'") + "' in parents and trashed = false")
                    .queryParam(
                            "fields",
                            "nextPageToken,files(id,name,mimeType,modifiedTime,size,webViewLink)")
                    .queryParam("pageSize", pageSize)
                    .queryParam("supportsAllDrives", true)
                    .queryParam("includeItemsFromAllDrives", true);

            if (pageToken != null && !pageToken.isBlank()) {
                builder.queryParam("pageToken", pageToken);
            }

            URI uri = builder.build().encode().toUri();
            var response = client.get()
                    .uri(uri)
                    .header("Authorization", "Bearer " + accessToken)
                    .retrieve()
                    .body(Map.class);

            if (response == null) break;

            var files = response.get("files");
            if (files instanceof Collection<?> values) {
                for (var value : values) {
                    if (value instanceof Map<?,?> raw) {
                        var document = new LinkedHashMap<String,Object>();
                        raw.forEach((key,item) -> document.put(String.valueOf(key), item));
                        documents.add(document);
                    }
                }
            }

            pageToken = string(response.get("nextPageToken"));
        } while (pageToken != null && !pageToken.isBlank());

        var result = new LinkedHashMap<String,Object>();
        result.put("folderId", folderId);
        result.put("documentCount", documents.size());
        result.put("documents", documents);
        result.put(
                "retrievalHint",
                "Use google-drive-read-file in Agent Platform to read document content by id.");
        return result;
    }

    private static Object readPath(Map<String,Object> root, String path) {
        Object current = root;
        for (var segment : path.split("\\.")) {
            if (!(current instanceof Map<?,?> map)) return null;
            current = map.get(segment);
        }
        return current;
    }

    private static String string(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static int integer(Object value) {
        if (value instanceof Number number) return number.intValue();
        return Integer.parseInt(String.valueOf(value));
    }
}

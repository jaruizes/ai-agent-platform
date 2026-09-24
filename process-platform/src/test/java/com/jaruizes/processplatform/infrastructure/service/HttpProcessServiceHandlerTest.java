package com.jaruizes.processplatform.infrastructure.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class HttpProcessServiceHandlerTest {

    @Test
    void invokesConfiguredHttpServiceAndReturnsObjectBody() {
        var builder = RestClient.builder();
        var server = MockRestServiceServer.bindTo(builder).build();
        var handler = new HttpProcessServiceHandler(builder);

        server.expect(once(), requestTo("http://customer-service/v1/customer"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(
                        "{\"customerId\":\"C-1\"}",
                        MediaType.APPLICATION_JSON));

        var result = handler.execute(
                Map.of("processInput", Map.of("customerId", "C-1")),
                Map.of(
                        "url", "http://customer-service/v1/customer",
                        "method", "GET"),
                Map.of());

        assertThat(result).containsEntry("customerId", "C-1");
        server.verify();
    }

    @Test
    void rejectsUnsupportedProtocolAndMethod() {
        var handler = new HttpProcessServiceHandler(RestClient.builder());

        assertThatThrownBy(() -> handler.validateConfiguration(
                Map.of("url", "file:///tmp/data", "method", "GET")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("http or https");

        assertThatThrownBy(() -> handler.validateConfiguration(
                Map.of("url", "http://service", "method", "TRACE")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Unsupported");
    }
}

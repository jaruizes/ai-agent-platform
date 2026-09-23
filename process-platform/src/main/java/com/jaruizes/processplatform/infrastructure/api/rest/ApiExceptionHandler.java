package com.jaruizes.processplatform.infrastructure.api.rest;

import org.springframework.http.*;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.*;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(NoSuchElementException.class)
    ResponseEntity<Map<String,Object>> notFound(NoSuchElementException exception) {
        return error(HttpStatus.NOT_FOUND, exception.getMessage());
    }

    @ExceptionHandler(IllegalStateException.class)
    ResponseEntity<Map<String,Object>> conflict(IllegalStateException exception) {
        return error(HttpStatus.CONFLICT, exception.getMessage());
    }

    @ExceptionHandler({IllegalArgumentException.class, MethodArgumentNotValidException.class})
    ResponseEntity<Map<String,Object>> badRequest(Exception exception) {
        var message = exception instanceof MethodArgumentNotValidException validation
                ? validation.getBindingResult().getAllErrors().stream()
                    .findFirst().map(error -> error.getDefaultMessage())
                    .orElse("Validation failed")
                : exception.getMessage();
        return error(HttpStatus.BAD_REQUEST, message);
    }

    private static ResponseEntity<Map<String,Object>> error(
            HttpStatus status,
            String message) {
        return ResponseEntity.status(status).body(Map.of(
                "timestamp", Instant.now().toString(),
                "status", status.value(),
                "error", status.getReasonPhrase(),
                "message", message == null ? status.getReasonPhrase() : message
        ));
    }
}

package org.ossustain.api;

import jakarta.servlet.http.HttpServletRequest;
import org.ossustain.api.dto.ApiErrorResponse;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(ApiException.class)
    ResponseEntity<ApiErrorResponse> handleApiException(ApiException error, HttpServletRequest request) {
        return response(error.status(), error.code(), error.getMessage(), request);
    }

    @ExceptionHandler({MethodArgumentTypeMismatchException.class, MissingServletRequestParameterException.class})
    ResponseEntity<ApiErrorResponse> handleInvalidParameter(Exception error, HttpServletRequest request) {
        return response(HttpStatus.BAD_REQUEST, "invalid_parameter",
                "A request parameter has an invalid value or type.", request);
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<ApiErrorResponse> handleNotFound(NoResourceFoundException error, HttpServletRequest request) {
        return response(HttpStatus.NOT_FOUND, "not_found", "The requested resource was not found.", request);
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ResponseEntity<ApiErrorResponse> handleMethodNotAllowed(
            HttpRequestMethodNotSupportedException error, HttpServletRequest request) {
        return response(HttpStatus.METHOD_NOT_ALLOWED, "method_not_allowed",
                "The requested HTTP method is not supported.", request);
    }

    @ExceptionHandler(DataAccessException.class)
    ResponseEntity<ApiErrorResponse> handleDatabaseFailure(DataAccessException error, HttpServletRequest request) {
        return response(HttpStatus.INTERNAL_SERVER_ERROR, "data_access_error",
                "The requested data could not be read.", request);
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiErrorResponse> handleUnexpectedFailure(Exception error, HttpServletRequest request) {
        return response(HttpStatus.INTERNAL_SERVER_ERROR, "internal_error",
                "The request could not be completed.", request);
    }

    private ResponseEntity<ApiErrorResponse> response(
            HttpStatus status, String code, String message, HttpServletRequest request) {
        var body = new ApiErrorResponse(
                OffsetDateTime.now(ZoneOffset.UTC), status.value(), code, message, request.getRequestURI());
        return ResponseEntity.status(status).body(body);
    }
}

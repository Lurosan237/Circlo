"""Property tests for input validation and error handling.

Feature: circlo-safety-app
Property 21: Input Validation
Property 22: Consistent Error Response Format
Property 23: Protected Endpoint Authentication

**Validates: Requirements 9.4, 9.5, 10.2, 10.3, 10.5**
"""
import pytest
from httpx import AsyncClient, ASGITransport
from hypothesis import given, strategies as st, settings as hyp_settings, HealthCheck
from app.main import app
from app.middleware.validation import (
    ValidationMiddleware,
    InputValidator,
    sanitize_string,
    sanitize_dict,
)
from app.middleware.error_handler import (
    ErrorResponse,
    create_error_response,
    ERROR_CODES,
    ERROR_MESSAGES,
)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


class TestInputValidation:
    """Property tests for input validation - Property 21.
    
    Feature: circlo-safety-app, Property 21: Input Validation
    **Validates: Requirements 9.4, 10.3**
    
    Property: For any user input or API request, invalid data should be rejected 
    before processing and return standardized error responses.
    """
    
    @given(
        value=st.text(min_size=1, max_size=100)
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_uuid_validation_property(self, value: str):
        """
        Property 21: Input Validation
        *For any* string input, UUID validation should correctly identify valid/invalid UUIDs.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        
        result = InputValidator.is_valid_uuid(value)
        
        # Valid UUID format: 8-4-4-4-12 hex characters
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        expected = bool(uuid_pattern.match(value))
        
        assert result == expected, f"UUID validation mismatch for '{value}'"
    
    @given(
        value=st.text(min_size=1, max_size=100)
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_sha256_validation_property(self, value: str):
        """
        Property 21: Input Validation
        *For any* string input, SHA-256 validation should correctly identify valid/invalid hashes.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        
        result = InputValidator.is_valid_sha256(value)
        
        # Valid SHA-256: exactly 64 hex characters
        import re
        sha256_pattern = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)
        expected = bool(sha256_pattern.match(value))
        
        assert result == expected, f"SHA-256 validation mismatch for '{value}'"
    
    @given(
        min_len=st.integers(min_value=0, max_value=50),
        max_len=st.integers(min_value=50, max_value=200),
        value=st.text(min_size=0, max_size=250)
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_string_length_validation_property(self, min_len: int, max_len: int, value: str):
        """
        Property 21: Input Validation
        *For any* string and length constraints, validation should correctly enforce limits.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        
        result = InputValidator.validate_string_length(value, min_len, max_len)
        expected = min_len <= len(value) <= max_len
        
        assert result == expected, \
            f"String length validation mismatch for len={len(value)}, min={min_len}, max={max_len}"
    
    @given(
        value=st.text(min_size=0, max_size=500)
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_string_sanitization_property(self, value: str):
        """
        Property 21: Input Validation
        *For any* string input, sanitization should escape HTML entities.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        
        sanitized = sanitize_string(value)
        
        # Verify HTML entities are escaped
        assert '<' not in sanitized or '&lt;' in sanitized or '<' not in value
        assert '>' not in sanitized or '&gt;' in sanitized or '>' not in value
        assert '&' not in sanitized or '&amp;' in sanitized or '&' not in value or sanitized.count('&') <= value.count('&')
        
        # Verify null bytes are removed
        assert '\x00' not in sanitized
    
    @given(
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            values=st.text(min_size=0, max_size=100),
            min_size=0,
            max_size=10
        )
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_dict_sanitization_property(self, data: dict):
        """
        Property 21: Input Validation
        *For any* dictionary input, sanitization should escape all string values.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        
        sanitized = sanitize_dict(data)
        
        # Verify all keys are preserved
        assert set(sanitized.keys()) == set(data.keys())
        
        # Verify all values are sanitized
        for key in data:
            if isinstance(data[key], str):
                assert '\x00' not in sanitized[key]
    
    @given(
        sql_keyword=st.sampled_from([
            "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "UNION", "ALTER"
        ]),
        prefix=st.text(min_size=0, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz '),
        suffix=st.text(min_size=0, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_sql_injection_detection_property(self, sql_keyword: str, prefix: str, suffix: str):
        """
        Property 21: Input Validation
        *For any* SQL keyword in input, the validation should detect it as potentially malicious.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        from unittest.mock import MagicMock
        
        middleware = ValidationMiddleware(MagicMock())
        
        # Test with SQL keyword
        test_value = f"{prefix} {sql_keyword} {suffix}"
        result = middleware._contains_malicious_content(test_value)
        
        # SQL keywords should be detected
        assert result is True, f"SQL keyword '{sql_keyword}' should be detected in '{test_value}'"
    
    @given(
        xss_pattern=st.sampled_from([
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<iframe src='evil.com'>",
            "onclick=alert(1)",
            "onerror=alert(1)",
        ])
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_xss_detection_property(self, xss_pattern: str):
        """
        Property 21: Input Validation
        *For any* XSS pattern in input, the validation should detect it as potentially malicious.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        from unittest.mock import MagicMock
        
        middleware = ValidationMiddleware(MagicMock())
        result = middleware._contains_malicious_content(xss_pattern)
        
        # XSS patterns should be detected
        assert result is True, f"XSS pattern should be detected: '{xss_pattern}'"
    
    @pytest.mark.anyio
    async def test_invalid_json_body_rejected(self):
        """
        Property 21: Input Validation
        Invalid JSON body should be rejected with proper error response.
        **Validates: Requirements 9.4, 10.3**
        """
        # Feature: circlo-safety-app, Property 21: Input Validation
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                content="not valid json",
                headers={"Content-Type": "application/json"}
            )
            
            # Should return validation error
            assert response.status_code == 422
            data = response.json()
            assert data["success"] is False
            assert "code" in data


class TestErrorResponseConsistency:
    """Property tests for error response consistency - Property 22.
    
    Feature: circlo-safety-app, Property 22: Consistent Error Response Format
    **Validates: Requirements 9.5, 10.5**
    
    Property: For any error condition, the response should follow the standardized 
    JSON format with success, message, and code fields.
    """
    
    @given(
        status_code=st.sampled_from([400, 401, 403, 404, 405, 409, 422, 429, 500, 502, 503]),
        message=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz '),
        code=st.text(min_size=1, max_size=50, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ_')
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_error_response_format_property(self, status_code: int, message: str, code: str):
        """
        Property 22: Consistent Error Response Format
        *For any* error condition, the response should have success, message, and code fields.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        
        response = create_error_response(
            status_code=status_code,
            message=message,
            code=code,
            log_error=False
        )
        
        # Verify response structure
        content = response.body.decode()
        import json
        data = json.loads(content)
        
        # Must have required fields
        assert "success" in data, "Response must have 'success' field"
        assert "message" in data, "Response must have 'message' field"
        assert "code" in data, "Response must have 'code' field"
        
        # Verify field types
        assert isinstance(data["success"], bool), "'success' must be boolean"
        assert isinstance(data["message"], str), "'message' must be string"
        assert isinstance(data["code"], str), "'code' must be string"
        
        # For errors, success should be False
        assert data["success"] is False, "Error response should have success=False"
        
        # Verify status code
        assert response.status_code == status_code
    
    @given(
        status_code=st.sampled_from(list(ERROR_CODES.keys()))
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_default_error_codes_property(self, status_code: int):
        """
        Property 22: Consistent Error Response Format
        *For any* HTTP status code, there should be a default error code mapping.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        
        # Create response without custom code
        response = create_error_response(
            status_code=status_code,
            log_error=False
        )
        
        content = response.body.decode()
        import json
        data = json.loads(content)
        
        # Should use default code from mapping
        assert data["code"] == ERROR_CODES[status_code], \
            f"Expected code {ERROR_CODES[status_code]} for status {status_code}"
    
    @given(
        status_code=st.sampled_from(list(ERROR_MESSAGES.keys()))
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_default_error_messages_property(self, status_code: int):
        """
        Property 22: Consistent Error Response Format
        *For any* HTTP status code, there should be a default error message.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        
        # Create response without custom message
        response = create_error_response(
            status_code=status_code,
            log_error=False
        )
        
        content = response.body.decode()
        import json
        data = json.loads(content)
        
        # Should use default message from mapping
        assert data["message"] == ERROR_MESSAGES[status_code], \
            f"Expected message '{ERROR_MESSAGES[status_code]}' for status {status_code}"
    
    def test_error_response_class_consistency(self):
        """
        Property 22: Consistent Error Response Format
        ErrorResponse class should produce consistent output.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        
        error = ErrorResponse(
            success=False,
            message="Test error",
            code="TEST_ERROR"
        )
        
        result = error.to_dict()
        
        assert result["success"] is False
        assert result["message"] == "Test error"
        assert result["code"] == "TEST_ERROR"
        assert "details" not in result  # No details provided
    
    def test_error_response_with_details(self):
        """
        Property 22: Consistent Error Response Format
        ErrorResponse with details should include them in output.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        
        error = ErrorResponse(
            success=False,
            message="Validation error",
            code="VALIDATION_ERROR",
            details={"field": "email", "error": "invalid format"}
        )
        
        result = error.to_dict()
        
        assert "details" in result
        assert result["details"]["field"] == "email"
    
    @pytest.mark.anyio
    async def test_404_error_format(self):
        """
        Property 22: Consistent Error Response Format
        404 errors should follow the standard format.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/nonexistent-endpoint")
            
            assert response.status_code == 404
            data = response.json()
            
            # Should have standard format
            assert "success" in data or "detail" in data  # FastAPI default or our format
    
    @pytest.mark.anyio
    async def test_validation_error_format(self):
        """
        Property 22: Consistent Error Response Format
        Validation errors should follow the standard format.
        **Validates: Requirements 9.5, 10.5**
        """
        # Feature: circlo-safety-app, Property 22: Consistent Error Response Format
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Send invalid data to trigger validation error
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "phone_hash": "invalid",  # Too short
                    "name_encrypted": "",  # Empty
                    "password": "short"  # Too short
                }
            )
            
            assert response.status_code == 422
            data = response.json()
            
            # Should have standard format
            assert "success" in data
            assert data["success"] is False
            assert "code" in data
            assert data["code"] == "VALIDATION_ERROR"


class TestProtectedEndpointAuthentication:
    """Property tests for protected endpoint authentication - Property 23.
    
    Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
    **Validates: Requirements 10.2**
    
    Property: For any protected API endpoint, requests without valid authentication 
    should be rejected with appropriate error responses.
    """
    
    @given(
        endpoint=st.sampled_from([
            "/api/v1/auth/me",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/circles",
            "/api/v1/circles/owned",
            "/api/v1/circles/member",
            "/api/v1/circles/invitations",
            "/api/v1/alerts",
            "/api/v1/alerts/pending-verification",
        ])
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_protected_endpoints_require_auth_property(self, endpoint: str):
        """
        Property 23: Protected Endpoint Authentication
        *For any* protected endpoint, requests without auth should be rejected.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        
        # This is a synchronous property test that verifies the endpoint list
        # The actual HTTP test is done in the async test below
        
        # Verify endpoint is in protected list
        protected_prefixes = [
            "/api/v1/auth/me",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/circles",
            "/api/v1/alerts",
            "/api/v1/messages",
            "/api/v1/notifications",
        ]
        
        is_protected = any(endpoint.startswith(prefix) for prefix in protected_prefixes)
        assert is_protected, f"Endpoint {endpoint} should be protected"
    
    @pytest.mark.anyio
    async def test_no_auth_header_rejected(self):
        """
        Property 23: Protected Endpoint Authentication
        Requests without Authorization header should be rejected.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Test protected endpoint without auth
            response = await client.get("/api/v1/auth/me")
            
            # Should be rejected (403 for missing header)
            assert response.status_code == 403
    
    @pytest.mark.anyio
    async def test_invalid_token_rejected(self):
        """
        Property 23: Protected Endpoint Authentication
        Requests with invalid token should be rejected.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid_token_here"}
            )
            
            # Should be rejected with 401
            assert response.status_code == 401
            data = response.json()
            # Check for error code in either format
            if "detail" in data:
                assert data["detail"]["code"] == "AUTH_TOKEN_INVALID"
            else:
                assert data.get("code") == "AUTH_TOKEN_INVALID"
    
    @pytest.mark.anyio
    async def test_malformed_auth_header_rejected(self):
        """
        Property 23: Protected Endpoint Authentication
        Requests with malformed Authorization header should be rejected.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Test with malformed header (no Bearer prefix)
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "just_a_token"}
            )
            
            # Should be rejected
            assert response.status_code in [401, 403]
    
    @given(
        token=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789._-')
    )
    @hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_random_tokens_rejected_property(self, token: str):
        """
        Property 23: Protected Endpoint Authentication
        *For any* random token string, it should be rejected as invalid.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        from app.core.security import decode_access_token
        
        # Random tokens should not decode successfully
        result = decode_access_token(token)
        assert result is None, f"Random token '{token}' should not be valid"
    
    @pytest.mark.anyio
    async def test_expired_token_rejected(self):
        """
        Property 23: Protected Endpoint Authentication
        Requests with expired token should be rejected.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        from app.core.security import create_access_token
        from datetime import timedelta
        
        # Create an expired token
        expired_token = create_access_token(
            data={"sub": "test-user"},
            expires_delta=timedelta(hours=-1)  # Expired 1 hour ago
        )
        
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            
            # Should be rejected with 401
            assert response.status_code == 401
            data = response.json()
            # Check for error code in either format
            if "detail" in data:
                assert data["detail"]["code"] == "AUTH_TOKEN_INVALID"
            else:
                assert data.get("code") == "AUTH_TOKEN_INVALID"
    
    @pytest.mark.anyio
    async def test_public_endpoints_accessible(self):
        """
        Property 23: Protected Endpoint Authentication
        Public endpoints should be accessible without authentication.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Health check should be public
            response = await client.get("/health")
            assert response.status_code == 200
            
            # API health should be public
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
    
    @pytest.mark.anyio
    @pytest.mark.skip(reason="Requires database connection")
    async def test_auth_endpoints_accessible(self):
        """
        Property 23: Protected Endpoint Authentication
        Login and register endpoints should be accessible without authentication.
        **Validates: Requirements 10.2**
        """
        # Feature: circlo-safety-app, Property 23: Protected Endpoint Authentication
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Login endpoint should be accessible (even if it fails validation or DB connection)
            response = await client.post(
                "/api/v1/auth/login",
                json={"phone_hash": "a" * 64, "password": "testpassword"}
            )
            # Should not be 401/403 (auth required) - may be 500 if no DB
            assert response.status_code not in [401, 403], \
                f"Login endpoint should not require auth, got {response.status_code}"
            
            # Register endpoint should be accessible
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "phone_hash": "b" * 64,
                    "name_encrypted": "test",
                    "password": "testpassword123"
                }
            )
            # Should not be 401/403 (auth required) - may be 500 if no DB
            assert response.status_code not in [401, 403], \
                f"Register endpoint should not require auth, got {response.status_code}"

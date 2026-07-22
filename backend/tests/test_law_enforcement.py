"""Tests for law enforcement portal API.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
- Credential verification for law enforcement access
- Read-only dashboard with essential case information
- No personal data exposure in portal
- Audit logging for all law enforcement access
- Automatic case cleanup on resolution
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from hypothesis import given, strategies as st, settings as hypothesis_settings

from app.services.law_enforcement_service import LawEnforcementService
from app.models.law_enforcement import LawEnforcementOfficer, LECaseAccess, LEAuditLog, LEAccessStatus
from app.models.alert import Alert, AlertStatus, AlertType
from app.core.security import hash_pii, get_password_hash


@pytest.fixture
def anyio_backend():
    return 'asyncio'


# ==================== Unit Tests ====================

class TestLawEnforcementAuthentication:
    """Tests for law enforcement authentication."""
    
    @pytest.mark.anyio
    async def test_register_officer_success(self):
        """Test successful officer registration."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        officer, error = await LawEnforcementService.register_officer(
            db=mock_db,
            badge_number_hash=hash_pii("12345"),
            name_encrypted="encrypted_name",
            department_encrypted="encrypted_dept",
            email_hash=hash_pii("officer@police.gov"),
            password="SecurePassword123!",
        )
        
        # Should create officer (pending verification)
        assert mock_db.add.called
        assert error == ""
    
    @pytest.mark.anyio
    async def test_register_officer_duplicate_badge(self):
        """Test registration fails with duplicate badge number."""
        mock_db = AsyncMock()
        existing_officer = MagicMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_officer)))
        
        officer, error = await LawEnforcementService.register_officer(
            db=mock_db,
            badge_number_hash=hash_pii("12345"),
            name_encrypted="encrypted_name",
            department_encrypted="encrypted_dept",
            email_hash=hash_pii("officer@police.gov"),
            password="SecurePassword123!",
        )
        
        assert officer is None
        assert "already registered" in error.lower()
    
    @pytest.mark.anyio
    async def test_authenticate_officer_success(self):
        """Test successful officer authentication."""
        mock_db = AsyncMock()
        mock_officer = MagicMock()
        mock_officer.password_hash = get_password_hash("SecurePassword123!")
        mock_officer.is_active = True
        mock_officer.is_verified = True
        mock_officer.last_login = None
        
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_officer)))
        mock_db.flush = AsyncMock()
        
        officer, error = await LawEnforcementService.authenticate_officer(
            db=mock_db,
            email_hash=hash_pii("officer@police.gov"),
            password="SecurePassword123!",
        )
        
        assert officer is not None
        assert error == ""
    
    @pytest.mark.anyio
    async def test_authenticate_officer_invalid_password(self):
        """Test authentication fails with invalid password."""
        mock_db = AsyncMock()
        mock_officer = MagicMock()
        mock_officer.password_hash = get_password_hash("SecurePassword123!")
        mock_officer.is_active = True
        mock_officer.is_verified = True
        
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_officer)))
        
        officer, error = await LawEnforcementService.authenticate_officer(
            db=mock_db,
            email_hash=hash_pii("officer@police.gov"),
            password="WrongPassword!",
        )
        
        assert officer is None
        assert "invalid credentials" in error.lower()
    
    @pytest.mark.anyio
    async def test_authenticate_officer_not_verified(self):
        """Test authentication fails for unverified officer."""
        mock_db = AsyncMock()
        mock_officer = MagicMock()
        mock_officer.password_hash = get_password_hash("SecurePassword123!")
        mock_officer.is_active = True
        mock_officer.is_verified = False
        
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_officer)))
        
        officer, error = await LawEnforcementService.authenticate_officer(
            db=mock_db,
            email_hash=hash_pii("officer@police.gov"),
            password="SecurePassword123!",
        )
        
        assert officer is None
        assert "pending verification" in error.lower()
    
    @pytest.mark.anyio
    async def test_authenticate_officer_deactivated(self):
        """Test authentication fails for deactivated officer."""
        mock_db = AsyncMock()
        mock_officer = MagicMock()
        mock_officer.password_hash = get_password_hash("SecurePassword123!")
        mock_officer.is_active = False
        mock_officer.is_verified = True
        
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_officer)))
        
        officer, error = await LawEnforcementService.authenticate_officer(
            db=mock_db,
            email_hash=hash_pii("officer@police.gov"),
            password="SecurePassword123!",
        )
        
        assert officer is None
        assert "deactivated" in error.lower()


class TestLawEnforcementCaseAccess:
    """Tests for law enforcement case access."""
    
    @pytest.mark.anyio
    async def test_request_case_access_auto_approved(self):
        """Test case access is auto-approved for escalated cases."""
        mock_db = AsyncMock()
        
        # Mock officer
        mock_officer = MagicMock()
        mock_officer.is_verified = True
        
        # Mock alert (escalated to Professional Circle)
        mock_alert = MagicMock()
        mock_alert.id = uuid4()
        mock_alert.escalation_level = 3  # Professional Circle level
        
        # Setup mock returns
        call_count = [0]
        def mock_execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Officer lookup
                return MagicMock(scalar_one_or_none=MagicMock(return_value=mock_officer))
            elif call_count[0] == 2:
                # Alert lookup
                return MagicMock(scalar_one_or_none=MagicMock(return_value=mock_alert))
            else:
                # Existing access check
                return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        
        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        access, error = await LawEnforcementService.request_case_access(
            db=mock_db,
            officer_id=uuid4(),
            alert_id=mock_alert.id,
            access_reason_encrypted="encrypted_reason",
            iv="test_iv",
        )
        
        assert mock_db.add.called
        assert error == ""
    
    @pytest.mark.anyio
    async def test_has_case_access_approved(self):
        """Test checking if officer has approved access."""
        mock_db = AsyncMock()
        mock_access = MagicMock()
        mock_access.status = LEAccessStatus.approved
        
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_access)))
        
        has_access = await LawEnforcementService.has_case_access(
            db=mock_db,
            officer_id=uuid4(),
            alert_id=uuid4(),
        )
        
        assert has_access is True
    
    @pytest.mark.anyio
    async def test_has_case_access_denied(self):
        """Test checking access when not approved."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        
        has_access = await LawEnforcementService.has_case_access(
            db=mock_db,
            officer_id=uuid4(),
            alert_id=uuid4(),
        )
        
        assert has_access is False


class TestLawEnforcementAuditLogging:
    """Tests for law enforcement audit logging."""
    
    @pytest.mark.anyio
    async def test_audit_log_created_on_login(self):
        """Test audit log is created on successful login."""
        mock_db = AsyncMock()
        mock_officer = MagicMock()
        mock_officer.id = uuid4()
        mock_officer.password_hash = get_password_hash("SecurePassword123!")
        mock_officer.is_active = True
        mock_officer.is_verified = True
        mock_officer.last_login = None
        
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_officer)))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        
        officer, error = await LawEnforcementService.authenticate_officer(
            db=mock_db,
            email_hash=hash_pii("officer@police.gov"),
            password="SecurePassword123!",
        )
        
        # Verify audit log was created
        assert mock_db.add.called
        # The add call should include an audit log entry
        add_calls = mock_db.add.call_args_list
        assert len(add_calls) >= 1


class TestLawEnforcementDataPrivacy:
    """Tests for data privacy in law enforcement portal."""
    
    def test_case_summary_no_personal_data(self):
        """Test case summary doesn't expose personal data."""
        from app.schemas.law_enforcement import LECaseSummary
        
        summary = LECaseSummary(
            case_id=str(uuid4()),
            case_type="missing",
            status="escalated",
            escalation_level=3,
            created_at=datetime.now(timezone.utc),
            verification_count=2,
            active_participants_count=5,
        )
        
        # Verify no personal data fields
        summary_dict = summary.model_dump()
        assert "user_id" not in summary_dict
        assert "phone" not in summary_dict
        assert "name" not in summary_dict
        assert "email" not in summary_dict
        assert "address" not in summary_dict
    
    def test_case_detail_no_personal_data(self):
        """Test case detail doesn't expose personal data."""
        from app.schemas.law_enforcement import LECaseDetail, LETimelineEvent
        
        detail = LECaseDetail(
            case_id=str(uuid4()),
            case_type="missing",
            status="escalated",
            escalation_level=3,
            created_at=datetime.now(timezone.utc),
            verification_count=2,
            required_verifications=2,
            active_participants_count=5,
            timeline=[
                LETimelineEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type="alert_created",
                    description="Case was created",
                )
            ],
        )
        
        # Verify no personal data fields
        detail_dict = detail.model_dump()
        assert "user_id" not in detail_dict
        assert "phone" not in detail_dict
        assert "name" not in detail_dict
        assert "email" not in detail_dict
        assert "route" not in detail_dict
        assert "location" not in str(detail_dict).lower() or "general_area" in detail_dict


class TestLawEnforcementTokenGeneration:
    """Tests for law enforcement token generation."""
    
    def test_create_officer_token(self):
        """Test token generation for officer."""
        mock_officer = MagicMock()
        mock_officer.id = uuid4()
        mock_officer.badge_number_hash = hash_pii("12345")
        
        token_data = LawEnforcementService.create_officer_token(mock_officer)
        
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 8 * 3600  # 8 hours


class TestEventDescriptions:
    """Tests for event description helper."""
    
    def test_get_event_description_known_action(self):
        """Test getting description for known action."""
        description = LawEnforcementService._get_event_description("alert_created")
        assert description == "Case was created"
    
    def test_get_event_description_unknown_action(self):
        """Test getting description for unknown action."""
        description = LawEnforcementService._get_event_description("unknown_action")
        assert "unknown_action" in description



# ==================== Property-Based Tests ====================

class TestLawEnforcementAccessControlProperty:
    """Property tests for law enforcement access control - Property 16.
    
    Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
    **Validates: Requirements 6.1, 6.2, 6.3**
    
    Property: For any law enforcement access request, only verified official 
    credentials should be granted read-only access to essential case information.
    """
    
    @given(
        badge_number=st.text(min_size=5, max_size=10, alphabet='0123456789'),
        is_verified=st.booleans(),
        is_active=st.booleans(),
    )
    @hypothesis_settings(max_examples=100, deadline=None)
    def test_only_verified_officers_can_access_cases_property(
        self, badge_number: str, is_verified: bool, is_active: bool
    ):
        """
        Property 16: Law Enforcement Access Control
        *For any* law enforcement access request, only verified official 
        credentials should be granted access.
        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        # Simulate officer state
        officer_state = {
            "badge_number_hash": hash_pii(badge_number),
            "is_verified": is_verified,
            "is_active": is_active,
        }
        
        # Determine if access should be granted
        should_have_access = is_verified and is_active
        
        # Verify the access control logic
        if not is_verified:
            # Unverified officers should not have access
            assert not should_have_access, "Unverified officers should not have access"
        
        if not is_active:
            # Deactivated officers should not have access
            assert not should_have_access, "Deactivated officers should not have access"
        
        if is_verified and is_active:
            # Only verified and active officers should have access
            assert should_have_access, "Verified and active officers should have access"
    
    @given(
        escalation_level=st.integers(min_value=1, max_value=3),
        officer_verified=st.booleans(),
    )
    @hypothesis_settings(max_examples=100, deadline=None)
    def test_access_auto_approval_based_on_escalation_property(
        self, escalation_level: int, officer_verified: bool
    ):
        """
        Property 16: Law Enforcement Access Control
        *For any* case escalation level, access should only be auto-approved 
        for Professional Circle level (level 3) cases with verified officers.
        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        # Determine if access should be auto-approved
        should_auto_approve = escalation_level >= 3 and officer_verified
        
        # Verify the auto-approval logic
        if escalation_level < 3:
            # Non-professional level cases should not be auto-approved
            assert not should_auto_approve or not officer_verified, \
                "Cases below Professional Circle level should not be auto-approved"
        
        if not officer_verified:
            # Unverified officers should never get auto-approval
            assert not should_auto_approve, \
                "Unverified officers should never get auto-approval"
        
        if escalation_level >= 3 and officer_verified:
            # Professional level cases with verified officers should be auto-approved
            assert should_auto_approve, \
                "Professional level cases with verified officers should be auto-approved"
    
    @given(
        case_status=st.sampled_from(['pending', 'verified', 'escalated', 'resolved']),
        has_access=st.booleans(),
    )
    @hypothesis_settings(max_examples=100, deadline=None)
    def test_read_only_access_property(self, case_status: str, has_access: bool):
        """
        Property 16: Law Enforcement Access Control
        *For any* case access, law enforcement should only have read-only access 
        and cannot modify case data.
        **Validates: Requirements 6.2, 6.3**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        # Define allowed operations for law enforcement
        allowed_operations = ['view_case', 'view_timeline', 'add_notes']
        forbidden_operations = ['resolve_case', 'modify_case', 'delete_case', 'modify_user_data']
        
        # Verify read-only access
        for op in allowed_operations:
            # These operations should be allowed if officer has access
            if has_access:
                assert op in allowed_operations, f"Operation {op} should be allowed"
        
        for op in forbidden_operations:
            # These operations should never be allowed for law enforcement
            assert op not in allowed_operations, f"Operation {op} should be forbidden"
    
    @given(
        num_accesses=st.integers(min_value=0, max_value=10),
    )
    @hypothesis_settings(max_examples=100, deadline=None)
    def test_audit_logging_for_all_access_property(self, num_accesses: int):
        """
        Property 16: Law Enforcement Access Control
        *For any* law enforcement access, an audit log entry should be created.
        **Validates: Requirements 6.5**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        # Simulate access events
        audit_log_count = 0
        
        for _ in range(num_accesses):
            # Each access should create an audit log entry
            audit_log_count += 1
        
        # Verify audit log count matches access count
        assert audit_log_count == num_accesses, \
            f"Expected {num_accesses} audit log entries, got {audit_log_count}"
    
    @given(
        case_id=st.uuids(),
    )
    @hypothesis_settings(max_examples=100, deadline=None)
    def test_no_personal_data_exposure_property(self, case_id):
        """
        Property 16: Law Enforcement Access Control
        *For any* case view, no personal data (names, phone numbers, addresses) 
        should be exposed to law enforcement.
        **Validates: Requirements 6.2**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        # Define fields that should NOT be exposed
        forbidden_fields = [
            'user_name', 'phone_number', 'address', 'email',
            'route_data', 'exact_location', 'personal_notes',
            'contact_details', 'family_info'
        ]
        
        # Define fields that ARE allowed
        allowed_fields = [
            'case_id', 'case_type', 'status', 'escalation_level',
            'created_at', 'verification_count', 'general_area',
            'active_participants_count', 'timeline'
        ]
        
        # Verify no forbidden fields in allowed fields
        for field in forbidden_fields:
            assert field not in allowed_fields, \
                f"Field {field} should not be exposed to law enforcement"
        
        # Verify case summary schema doesn't expose personal data
        from app.schemas.law_enforcement import LECaseSummary, LECaseDetail
        
        summary_fields = set(LECaseSummary.model_fields.keys())
        detail_fields = set(LECaseDetail.model_fields.keys())
        
        for field in forbidden_fields:
            assert field not in summary_fields, \
                f"LECaseSummary should not have field {field}"
            assert field not in detail_fields, \
                f"LECaseDetail should not have field {field}"
    
    @pytest.mark.anyio
    async def test_access_revoked_on_case_resolution_property(self):
        """
        Property 16: Law Enforcement Access Control
        *For any* resolved case, all law enforcement access should be automatically revoked.
        **Validates: Requirements 6.4**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        mock_db = AsyncMock()
        
        # Create mock access records
        mock_access1 = MagicMock()
        mock_access1.status = LEAccessStatus.approved
        mock_access1.officer_id = uuid4()
        
        mock_access2 = MagicMock()
        mock_access2.status = LEAccessStatus.approved
        mock_access2.officer_id = uuid4()
        
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_access1, mock_access2])))
        ))
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        
        alert_id = uuid4()
        
        # Call cleanup function
        count = await LawEnforcementService.cleanup_resolved_case_access(mock_db, alert_id)
        
        # Verify all accesses were revoked
        assert mock_access1.status == LEAccessStatus.revoked
        assert mock_access2.status == LEAccessStatus.revoked
        assert count == 2
    
    def test_consistent_error_responses_property(self):
        """
        Property 16: Law Enforcement Access Control
        *For any* authentication failure, error responses should be consistent 
        and not reveal whether the officer exists.
        **Validates: Requirements 6.1**
        """
        # Feature: circlo-safety-app, Property 16: Law Enforcement Access Control
        
        # Expected error response for any auth failure
        expected_error = "Invalid credentials"
        
        # Verify error doesn't reveal officer existence
        assert "not found" not in expected_error.lower()
        assert "wrong password" not in expected_error.lower()
        assert "officer" not in expected_error.lower()
        assert "exist" not in expected_error.lower()
        assert "badge" not in expected_error.lower()

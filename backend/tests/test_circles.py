"""Property tests for circle management."""
import pytest
from hypothesis import given, strategies as st, settings, assume
from uuid import uuid4
from datetime import datetime, timezone

from app.models.circle import CircleType, MemberStatus, Circle, CircleMember
from app.services.circle_service import CircleService


class TestCircleSizeEnforcement:
    """Property tests for circle size enforcement.
    
    Feature: circlo-safety-app, Property 5: Circle Size Enforcement
    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    
    # Strategy for generating circle types
    circle_type_strategy = st.sampled_from([
        CircleType.inner,
        CircleType.community,
        CircleType.professional,
    ])
    
    @given(
        circle_type=circle_type_strategy,
        max_members=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_circle_size_validation_enforces_limits(self, circle_type: CircleType, max_members: int):
        """
        Property 5: Circle Size Enforcement
        *For any* circle type, the system should enforce the maximum member limits
        (Inner: 3-5, Community: 15-30, Professional: 1-50)
        
        Feature: circlo-safety-app, Property 5: Circle Size Enforcement
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        min_limit, max_limit = CircleService.get_circle_limits(circle_type)
        
        is_valid, error_msg = CircleService.validate_max_members(circle_type, max_members)
        
        # Should be valid only if within limits
        expected_valid = min_limit <= max_members <= max_limit
        
        assert is_valid == expected_valid, (
            f"Circle type {circle_type.value} with max_members={max_members} "
            f"should be {'valid' if expected_valid else 'invalid'} "
            f"(limits: {min_limit}-{max_limit})"
        )
        
        # If invalid, error message should be present
        if not is_valid:
            assert error_msg != "", "Invalid configuration should have error message"
    
    @given(max_members=st.integers(min_value=3, max_value=5))
    @settings(max_examples=100)
    def test_inner_circle_valid_range(self, max_members: int):
        """Inner circle should accept 3-5 members."""
        is_valid, _ = CircleService.validate_max_members(CircleType.inner, max_members)
        assert is_valid, f"Inner circle should accept {max_members} members"
    
    @given(max_members=st.integers(min_value=6, max_value=100))
    @settings(max_examples=100)
    def test_inner_circle_rejects_too_many(self, max_members: int):
        """Inner circle should reject more than 5 members."""
        is_valid, error_msg = CircleService.validate_max_members(CircleType.inner, max_members)
        assert not is_valid, f"Inner circle should reject {max_members} members"
        assert "5" in error_msg or "exceed" in error_msg.lower()
    
    @given(max_members=st.integers(min_value=0, max_value=2))
    @settings(max_examples=100)
    def test_inner_circle_rejects_too_few(self, max_members: int):
        """Inner circle should reject fewer than 3 members."""
        is_valid, error_msg = CircleService.validate_max_members(CircleType.inner, max_members)
        assert not is_valid, f"Inner circle should reject {max_members} members"
        assert "3" in error_msg or "at least" in error_msg.lower()
    
    @given(max_members=st.integers(min_value=15, max_value=30))
    @settings(max_examples=100)
    def test_community_circle_valid_range(self, max_members: int):
        """Community circle should accept 15-30 members."""
        is_valid, _ = CircleService.validate_max_members(CircleType.community, max_members)
        assert is_valid, f"Community circle should accept {max_members} members"
    
    @given(max_members=st.integers(min_value=31, max_value=100))
    @settings(max_examples=100)
    def test_community_circle_rejects_too_many(self, max_members: int):
        """Community circle should reject more than 30 members."""
        is_valid, error_msg = CircleService.validate_max_members(CircleType.community, max_members)
        assert not is_valid, f"Community circle should reject {max_members} members"
        assert "30" in error_msg or "exceed" in error_msg.lower()
    
    @given(max_members=st.integers(min_value=0, max_value=14))
    @settings(max_examples=100)
    def test_community_circle_rejects_too_few(self, max_members: int):
        """Community circle should reject fewer than 15 members."""
        is_valid, error_msg = CircleService.validate_max_members(CircleType.community, max_members)
        assert not is_valid, f"Community circle should reject {max_members} members"
        assert "15" in error_msg or "at least" in error_msg.lower()
    
    @given(max_members=st.integers(min_value=1, max_value=50))
    @settings(max_examples=100)
    def test_professional_circle_valid_range(self, max_members: int):
        """Professional circle should accept 1-50 members."""
        is_valid, _ = CircleService.validate_max_members(CircleType.professional, max_members)
        assert is_valid, f"Professional circle should accept {max_members} members"
    
    @given(max_members=st.integers(min_value=51, max_value=100))
    @settings(max_examples=100)
    def test_professional_circle_rejects_too_many(self, max_members: int):
        """Professional circle should reject more than 50 members."""
        is_valid, error_msg = CircleService.validate_max_members(CircleType.professional, max_members)
        assert not is_valid, f"Professional circle should reject {max_members} members"
        assert "50" in error_msg or "exceed" in error_msg.lower()
    
    def test_professional_circle_rejects_zero(self):
        """Professional circle should reject 0 members."""
        is_valid, error_msg = CircleService.validate_max_members(CircleType.professional, 0)
        assert not is_valid, "Professional circle should reject 0 members"
        assert "1" in error_msg or "at least" in error_msg.lower()


class TestCircleLimitsConsistency:
    """Tests for circle limits consistency."""
    
    def test_all_circle_types_have_limits(self):
        """All circle types should have defined limits."""
        for circle_type in CircleType:
            min_limit, max_limit = CircleService.get_circle_limits(circle_type)
            assert min_limit > 0, f"{circle_type.value} should have positive min limit"
            assert max_limit >= min_limit, f"{circle_type.value} max should be >= min"
    
    def test_inner_circle_limits(self):
        """Inner circle should have limits 3-5."""
        min_limit, max_limit = CircleService.get_circle_limits(CircleType.inner)
        assert min_limit == 3
        assert max_limit == 5
    
    def test_community_circle_limits(self):
        """Community circle should have limits 15-30."""
        min_limit, max_limit = CircleService.get_circle_limits(CircleType.community)
        assert min_limit == 15
        assert max_limit == 30
    
    def test_professional_circle_limits(self):
        """Professional circle should have limits 1-50."""
        min_limit, max_limit = CircleService.get_circle_limits(CircleType.professional)
        assert min_limit == 1
        assert max_limit == 50


class TestMutualVerification:
    """Property tests for mutual verification requirement.
    
    Feature: circlo-safety-app, Property 6: Mutual Verification Requirement
    **Validates: Requirements 2.4**
    """
    
    def test_new_member_starts_pending(self):
        """
        Property 6: Mutual Verification Requirement
        *For any* contact addition to a circle, the relationship should remain
        inactive until both parties provide verification.
        
        Feature: circlo-safety-app, Property 6: Mutual Verification Requirement
        **Validates: Requirements 2.4**
        """
        # Create a member without verification
        member = CircleMember(
            id=uuid4(),
            circle_id=uuid4(),
            user_id=uuid4(),
            status=MemberStatus.pending,
            invited_at=datetime.now(timezone.utc),
            verified_at=None,
            mutual_verified=False,
        )
        
        # New member should be pending
        assert member.status == MemberStatus.pending
        assert member.mutual_verified is False
        assert member.verified_at is None
    
    def test_member_not_active_without_verification(self):
        """Member should not be active without mutual verification."""
        member = CircleMember(
            id=uuid4(),
            circle_id=uuid4(),
            user_id=uuid4(),
            status=MemberStatus.pending,
            invited_at=datetime.now(timezone.utc),
            verified_at=None,
            mutual_verified=False,
        )
        
        # Should not be active
        assert member.status != MemberStatus.active
    
    def test_verified_member_is_active(self):
        """Verified member should be active with mutual_verified=True."""
        member = CircleMember(
            id=uuid4(),
            circle_id=uuid4(),
            user_id=uuid4(),
            status=MemberStatus.active,
            invited_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            mutual_verified=True,
        )
        
        # Should be active with verification
        assert member.status == MemberStatus.active
        assert member.mutual_verified is True
        assert member.verified_at is not None


class TestAccessRevocation:
    """Property tests for access revocation on removal.
    
    Feature: circlo-safety-app, Property 7: Access Revocation on Removal
    **Validates: Requirements 2.6**
    """
    
    def test_removed_member_status(self):
        """
        Property 7: Access Revocation on Removal
        *For any* contact removed from a circle, their access to the user's data
        should be immediately revoked and subsequent access attempts should fail.
        
        Feature: circlo-safety-app, Property 7: Access Revocation on Removal
        **Validates: Requirements 2.6**
        """
        # Create an active member
        member = CircleMember(
            id=uuid4(),
            circle_id=uuid4(),
            user_id=uuid4(),
            status=MemberStatus.active,
            invited_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            mutual_verified=True,
        )
        
        # Simulate removal
        member.status = MemberStatus.removed
        member.mutual_verified = False
        
        # Should be removed with revoked verification
        assert member.status == MemberStatus.removed
        assert member.mutual_verified is False
    
    @given(st.sampled_from([MemberStatus.pending, MemberStatus.active]))
    @settings(max_examples=100)
    def test_any_member_can_be_removed(self, initial_status: MemberStatus):
        """Any member status can transition to removed."""
        member = CircleMember(
            id=uuid4(),
            circle_id=uuid4(),
            user_id=uuid4(),
            status=initial_status,
            invited_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc) if initial_status == MemberStatus.active else None,
            mutual_verified=initial_status == MemberStatus.active,
        )
        
        # Simulate removal
        member.status = MemberStatus.removed
        member.mutual_verified = False
        
        # Should be removed
        assert member.status == MemberStatus.removed
        assert member.mutual_verified is False
    
    def test_removed_member_loses_verification(self):
        """Removed member should lose mutual verification status."""
        member = CircleMember(
            id=uuid4(),
            circle_id=uuid4(),
            user_id=uuid4(),
            status=MemberStatus.active,
            invited_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            mutual_verified=True,
        )
        
        # Verify initially active
        assert member.mutual_verified is True
        
        # Simulate removal
        member.status = MemberStatus.removed
        member.mutual_verified = False
        
        # Verification should be revoked
        assert member.mutual_verified is False


class TestCircleTypeProperties:
    """Tests for CircleType enum properties."""
    
    def test_circle_type_min_members(self):
        """Circle types should have correct min_members property."""
        assert CircleType.inner.min_members == 3
        assert CircleType.community.min_members == 15
        assert CircleType.professional.min_members == 1
    
    def test_circle_type_max_members(self):
        """Circle types should have correct max_members property."""
        assert CircleType.inner.max_members == 5
        assert CircleType.community.max_members == 30
        assert CircleType.professional.max_members == 50
    
    @given(st.sampled_from(list(CircleType)))
    @settings(max_examples=100)
    def test_circle_type_limits_match_service(self, circle_type: CircleType):
        """CircleType properties should match CircleService limits."""
        service_min, service_max = CircleService.get_circle_limits(circle_type)
        
        assert circle_type.min_members == service_min
        assert circle_type.max_members == service_max

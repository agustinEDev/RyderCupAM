"""
Tests for Support Module - Contact Form

Tests for ContactCategory, ContactRequestDTO, ContactResponseDTO, and SubmitContactUseCase.
"""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.modules.support.application.dto.contact_dto import (
    ContactRequestDTO,
    ContactResponseDTO,
)
from src.modules.support.application.use_cases.submit_contact_use_case import (
    GitHubIssueCreationError,
    SubmitContactUseCase,
)
from src.modules.support.domain.value_objects.contact_category import ContactCategory

# =============================================================================
# ContactCategory Tests
# =============================================================================


class TestContactCategory:
    """Tests for ContactCategory enum."""

    def test_all_categories_exist(self):
        """All expected categories should be defined."""
        assert ContactCategory.BUG.value == "BUG"
        assert ContactCategory.FEATURE.value == "FEATURE"
        assert ContactCategory.QUESTION.value == "QUESTION"
        assert ContactCategory.OTHER.value == "OTHER"

    def test_bug_to_github_label(self):
        """BUG category should map to 'bug' label."""
        assert ContactCategory.BUG.to_github_label() == "bug"

    def test_feature_to_github_label(self):
        """FEATURE category should map to 'enhancement' label."""
        assert ContactCategory.FEATURE.to_github_label() == "enhancement"

    def test_question_to_github_label(self):
        """QUESTION category should map to 'question' label."""
        assert ContactCategory.QUESTION.to_github_label() == "question"

    def test_other_to_github_label(self):
        """OTHER category should map to 'other' label."""
        assert ContactCategory.OTHER.to_github_label() == "other"

    def test_category_is_string_enum(self):
        """ContactCategory should be a string enum for Pydantic compatibility."""
        assert isinstance(ContactCategory.BUG, str)
        assert ContactCategory.BUG == "BUG"


# =============================================================================
# ContactRequestDTO Tests
# =============================================================================


class TestContactRequestDTO:
    """Tests for ContactRequestDTO validation."""

    def _valid_data(self, **overrides):
        """Helper to build valid DTO data with optional overrides."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "category": "BUG",
            "subject": "Something is broken",
            "message": "When I click the button, nothing happens. Please fix.",
        }
        data.update(overrides)
        return data

    def test_valid_request(self):
        """Should create DTO with valid data."""
        dto = ContactRequestDTO(**self._valid_data())
        assert dto.name == "John Doe"
        assert str(dto.email) == "john@example.com"
        assert dto.category == ContactCategory.BUG
        assert dto.subject == "Something is broken"

    def test_all_categories_accepted(self):
        """Should accept all valid category values."""
        for category in ["BUG", "FEATURE", "QUESTION", "OTHER"]:
            dto = ContactRequestDTO(**self._valid_data(category=category))
            assert dto.category.value == category

    def test_name_too_short(self):
        """Should reject name shorter than 2 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(name="A"))

    def test_name_too_long(self):
        """Should reject name longer than 100 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(name="A" * 101))

    def test_invalid_email(self):
        """Should reject invalid email format."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(email="not-an-email"))

    def test_invalid_category(self):
        """Should reject invalid category value."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(category="INVALID"))

    def test_subject_too_short(self):
        """Should reject subject shorter than 3 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(subject="AB"))

    def test_subject_too_long(self):
        """Should reject subject longer than 200 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(subject="A" * 201))

    def test_message_too_short(self):
        """Should reject message shorter than 10 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(message="Short"))

    def test_message_too_long(self):
        """Should reject message longer than 5000 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(message="A" * 5001))

    def test_missing_required_fields(self):
        """Should reject request with missing fields."""
        with pytest.raises(ValidationError):
            ContactRequestDTO()


# =============================================================================
# ContactResponseDTO Tests
# =============================================================================


class TestContactResponseDTO:
    """Tests for ContactResponseDTO."""

    def test_valid_response(self):
        """Should create response DTO with message."""
        dto = ContactResponseDTO(message="Success")
        assert dto.message == "Success"


# =============================================================================
# SubmitContactUseCase Tests
# =============================================================================


class TestSubmitContactUseCase:
    """Tests for SubmitContactUseCase."""

    def _make_request(self, **overrides):
        """Helper to create a valid ContactRequestDTO."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "category": "BUG",
            "subject": "Something is broken",
            "message": "When I click the button, nothing happens. Please fix.",
        }
        data.update(overrides)
        return ContactRequestDTO(**data)

    @pytest.mark.asyncio
    async def test_successful_submission(self):
        """Should return success response when GitHub issue is created."""
        mock_service = AsyncMock()
        mock_service.create_issue.return_value = True

        use_case = SubmitContactUseCase(mock_service)
        result = await use_case.execute(self._make_request())

        assert isinstance(result, ContactResponseDTO)
        assert "received" in result.message.lower()
        mock_service.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_github_failure_raises_error(self):
        """Should raise GitHubIssueCreationError when GitHub API fails."""
        mock_service = AsyncMock()
        mock_service.create_issue.return_value = False

        use_case = SubmitContactUseCase(mock_service)

        with pytest.raises(GitHubIssueCreationError):
            await use_case.execute(self._make_request())

    @pytest.mark.asyncio
    async def test_title_format(self):
        """Should format title as [CATEGORY] Subject."""
        mock_service = AsyncMock()
        mock_service.create_issue.return_value = True

        use_case = SubmitContactUseCase(mock_service)
        await use_case.execute(self._make_request(category="FEATURE", subject="Add dark mode"))

        call_args = mock_service.create_issue.call_args
        title = call_args[1].get("title") or call_args[0][0]
        assert title == "[FEATURE] Add dark mode"

    @pytest.mark.asyncio
    async def test_labels_mapped_correctly(self):
        """Should map category to correct GitHub label."""
        mock_service = AsyncMock()
        mock_service.create_issue.return_value = True

        use_case = SubmitContactUseCase(mock_service)
        await use_case.execute(self._make_request(category="BUG"))

        call_args = mock_service.create_issue.call_args
        labels = call_args[1].get("labels") or call_args[0][2]
        assert labels == ["bug"]

    @pytest.mark.asyncio
    async def test_body_contains_contact_info(self):
        """Should include contact info in issue body."""
        mock_service = AsyncMock()
        mock_service.create_issue.return_value = True

        use_case = SubmitContactUseCase(mock_service)
        await use_case.execute(self._make_request(name="Jane Smith", email="jane@test.com"))

        call_args = mock_service.create_issue.call_args
        body = call_args[1].get("body") or call_args[0][1]
        assert "Jane Smith" in body
        assert "jane@test.com" in body

    @pytest.mark.asyncio
    async def test_html_sanitization(self):
        """Should sanitize HTML tags from inputs."""
        mock_service = AsyncMock()
        mock_service.create_issue.return_value = True

        use_case = SubmitContactUseCase(mock_service)
        await use_case.execute(
            self._make_request(
                name="<script>alert('xss')</script>John",
                subject="<b>Bold</b> subject test",
                message="This is a <img src=x onerror=alert(1)> test message here",
            )
        )

        call_args = mock_service.create_issue.call_args
        title = call_args[1].get("title") or call_args[0][0]
        body = call_args[1].get("body") or call_args[0][1]

        assert "<script>" not in title
        assert "<script>" not in body
        assert "<b>" not in title
        assert "<img" not in body

    @pytest.mark.asyncio
    async def test_all_categories_produce_correct_labels(self):
        """Should map all categories to their correct GitHub labels."""
        expected_labels = {
            "BUG": "bug",
            "FEATURE": "enhancement",
            "QUESTION": "question",
            "OTHER": "other",
        }

        for category, expected_label in expected_labels.items():
            mock_service = AsyncMock()
            mock_service.create_issue.return_value = True

            use_case = SubmitContactUseCase(mock_service)
            await use_case.execute(self._make_request(category=category))

            call_args = mock_service.create_issue.call_args
            labels = call_args[1].get("labels") or call_args[0][2]
            assert labels == [expected_label], (
                f"Category {category} should produce label '{expected_label}'"
            )

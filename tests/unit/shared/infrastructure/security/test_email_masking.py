"""Tests para la utilidad compartida mask_email."""

from src.shared.infrastructure.security.email_masking import mask_email


class TestMaskEmail:
    def test_masks_local_part_keeping_first_char(self):
        assert mask_email("test@example.com") == "t***@example.com"

    def test_single_char_local_part_fully_masked(self):
        assert mask_email("a@test.com") == "***@test.com"

    def test_no_at_sign_returns_fully_masked(self):
        assert mask_email("not-an-email") == "***"

    def test_multiple_at_signs_returns_fully_masked(self):
        assert mask_email("a@b@c.com") == "***"

    def test_empty_local_part_returns_fully_masked(self):
        assert mask_email("@example.com") == "***"

    def test_empty_domain_part_returns_fully_masked(self):
        assert mask_email("alice@") == "***"

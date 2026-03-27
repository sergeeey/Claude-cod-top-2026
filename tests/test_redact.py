"""Unit tests for scripts/redact.py — PII/secrets redaction."""

from redact import clean, redact, should_exclude

# === National ID (example: 12-digit format) ===


class TestNationalIDRedaction:
    def test_valid_national_id(self):
        result = redact("ID: 920315450123")
        assert "[REDACTED:NATIONAL_ID]" in result
        assert "920315450123" not in result

    def test_national_id_in_sentence(self):
        result = redact("Client ID is 850101312345, verified.")
        assert "[REDACTED:NATIONAL_ID]" in result

    def test_short_number_not_national_id(self):
        """11 digits should NOT match national ID pattern."""
        result = redact("92031545012")
        assert "[REDACTED:NATIONAL_ID]" not in result


# === Bank cards ===


class TestCardRedaction:
    def test_card_no_separators(self):
        result = redact("Card: 4400430154763891")
        assert "[REDACTED:CARD]" in result

    def test_card_with_spaces(self):
        result = redact("Card: 4400 4301 5476 3891")
        assert "[REDACTED:CARD]" in result

    def test_card_with_dashes(self):
        result = redact("Card: 4400-4301-5476-3891")
        assert "[REDACTED:CARD]" in result


# === IBAN ===


class TestIBANRedaction:
    def test_iban(self):
        result = redact("IBAN: KZ75125KZT2069100243")
        assert "[REDACTED:IBAN]" in result


# === API keys ===


class TestAPIKeyRedaction:
    def test_openai_key(self):
        result = redact("key: sk-abc123def456ghi789jkl012mno")
        assert "[REDACTED:API_KEY]" in result

    def test_github_token(self):
        result = redact("token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij")
        assert "[REDACTED:GITHUB_TOKEN]" in result

    def test_aws_key(self):
        result = redact("aws: AKIAIOSFODNN7EXAMPLE")
        assert "[REDACTED:AWS_KEY]" in result

    def test_slack_token(self):
        # WHY: Token is split to avoid GitHub Push Protection false positive.
        # The regex pattern matches xoxb- prefix + 50+ alphanumeric chars.
        token = "xoxb-" + "1" * 20 + "-" + "A" * 20 + "-" + "B" * 12
        result = redact(f"slack: {token}")
        assert "[REDACTED:SLACK_TOKEN]" in result


# === JWT ===


class TestJWTRedaction:
    def test_jwt_token(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact(f"Bearer {jwt}")
        assert "[REDACTED:JWT]" in result


# === IP addresses ===


class TestIPRedaction:
    def test_ipv4(self):
        result = redact("Server: 192.168.1.100")
        assert "[REDACTED:IP]" in result

    def test_localhost(self):
        result = redact("Connect to 127.0.0.1")
        assert "[REDACTED:IP]" in result


# === Email ===


class TestEmailRedaction:
    def test_email(self):
        result = redact("Contact: user@example.com")
        assert "[REDACTED:EMAIL]" in result


# === Phone ===


class TestPhoneRedaction:
    def test_phone(self):
        result = redact("Call +7 777 123 45 67")
        assert "[REDACTED:PHONE]" in result

    def test_phone_no_plus(self):
        result = redact("Phone: 7 701 555 12 34")
        assert "[REDACTED:PHONE]" in result


# === Exceptions (should NOT redact) ===


class TestExceptions:
    def test_clinvar_id(self):
        assert should_exclude("VCV000123456")

    def test_dbsnp_id(self):
        assert should_exclude("rs12345678")

    def test_genomic_coords(self):
        assert should_exclude("chr11:5225464")

    def test_decimal_number(self):
        assert should_exclude("73.3")

    def test_git_sha(self):
        assert should_exclude("a" * 40)

    def test_ip_not_excluded(self):
        """IP addresses should NOT be excluded."""
        assert not should_exclude("192.168.1.1")


# === Recursive clean ===


class TestClean:
    def test_clean_dict(self):
        data = {"name": "Test", "national_id": "920315450123"}
        result = clean(data)
        assert "[REDACTED:NATIONAL_ID]" in result["national_id"]

    def test_clean_nested_list(self):
        data = [{"email": "user@test.com"}]
        result = clean(data)
        assert "[REDACTED:EMAIL]" in result[0]["email"]

    def test_clean_preserves_numbers(self):
        assert clean(42) == 42
        assert clean(3.14) == 3.14

    def test_clean_preserves_none(self):
        assert clean(None) is None

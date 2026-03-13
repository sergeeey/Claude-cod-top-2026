"""Тесты для redaction pipeline."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from redact import redact

# === Должен очистить ===
assert "[REDACTED:IIN]" in redact("IIN клиента: 850101350123"), "IIN not redacted"
assert "[REDACTED:CARD]" in redact("карта 4400 1234 5678 9012"), "Card not redacted"
assert "[REDACTED:EMAIL]" in redact("пишите на ivan@bank.kz"), "Email not redacted"
assert "[REDACTED:API_KEY]" in redact("ключ sk-abc123def456ghi789jkl012"), "API key not redacted"
assert "[REDACTED:IBAN]" in redact("счёт KZ86125KZT5004100100"), "IBAN not redacted"
assert "[REDACTED:PHONE]" in redact("телефон +7 701 234 56 78"), "Phone not redacted"

# === НЕ должен трогать ===
assert "VCV000012345" in redact("вариант VCV000012345 патогенный"), "ClinVar ID was redacted!"
assert "rs12345" in redact("SNP rs12345 ассоциирован с..."), "dbSNP ID was redacted!"
assert "chr17:43044295" in redact("позиция chr17:43044295"), "Genomic coord was redacted!"
assert "73.3" in redact("accuracy 73.3%"), "Decimal was redacted!"
assert "51.1694" in redact("координаты 51.1694, 71.4491"), "Lat/Lon was redacted!"

print("All 11 redaction tests passed!")

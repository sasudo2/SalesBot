import re

from app.domain.errors import ValidationAppError


def validate_phone(phone: str) -> str:
    normalized = re.sub(r"[\s()\-]", "", phone)
    if normalized.startswith("+977"):
        normalized = normalized[4:]
    elif normalized.startswith("977"):
        normalized = normalized[3:]
    if not re.fullmatch(r"9[78]\d{8}", normalized, flags=re.ASCII):
        raise ValidationAppError(
            "Invalid Nepal mobile number. Expected 10 digits starting with 97 or 98."
        )
    return "+977" + normalized

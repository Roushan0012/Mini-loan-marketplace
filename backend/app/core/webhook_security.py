import hashlib
import hmac
from typing import Optional


def create_mock_webhook_signature(raw_body: bytes, secret: str) -> str:
    """Generate an HMAC-SHA256 signature string in the format 'sha256=<hex_digest>'."""
    if not secret:
        raise ValueError("Webhook signing secret cannot be empty.")
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_mock_webhook_signature(
    raw_body: bytes,
    provided_signature: Optional[str],
    secret: Optional[str],
) -> bool:
    """Verify an incoming HMAC-SHA256 webhook signature in constant time.

    Requirements:
    - Signature must start with 'sha256='.
    - Comparison is performed using constant-time hmac.compare_digest.
    - Missing or empty secret/signature returns False.
    - Malformed format returns False.
    """
    if not secret or not provided_signature or not isinstance(provided_signature, str):
        return False

    prefix = "sha256="
    if not provided_signature.startswith(prefix):
        return False

    expected_hex = provided_signature[len(prefix):].strip()
    if not expected_hex:
        return False

    calculated_hex = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hex, expected_hex)

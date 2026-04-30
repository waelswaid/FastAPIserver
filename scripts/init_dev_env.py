"""Generate RSA keys and inject them into .env on first run.

Idempotent: if .env already contains real keys (no placeholder string),
exit without changes.
"""
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


PLACEHOLDER = "your-private-key-here"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def main() -> int:
    if not ENV_PATH.exists():
        print(f"{ENV_PATH} not found. Run `cp .env.example .env` first.", file=sys.stderr)
        return 1

    content = ENV_PATH.read_text()
    if PLACEHOLDER not in content:
        print("Keys already present, skipping.")
        return 0

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode().strip()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode().strip()

    content = re.sub(
        r'JWT_PRIVATE_KEY=".*?"',
        f'JWT_PRIVATE_KEY="{private_pem}"',
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'JWT_PUBLIC_KEY=".*?"',
        f'JWT_PUBLIC_KEY="{public_pem}"',
        content,
        count=1,
        flags=re.DOTALL,
    )

    ENV_PATH.write_text(content)
    print(f"Generated RSA keys and wrote to {ENV_PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

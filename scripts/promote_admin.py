"""One-off script to promote a user to admin by email.

Usage:
    python -m scripts.promote_admin user@example.com
"""
import sys
from datetime import datetime, timezone

from app.database.session import SessionLocal
from app.models.user import User


def promote(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print(f"No user found with email: {email}")
            sys.exit(1)

        if user.role == "admin":
            print(f"{email} is already an admin.")
            return

        user.role = "admin"
        user.role_changed_at = datetime.now(timezone.utc)
        db.commit()
        print(f"Promoted {email} to admin.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.promote_admin <email>")
        sys.exit(1)
    promote(sys.argv[1])

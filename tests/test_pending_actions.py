from datetime import datetime, timezone, timedelta

from app.models.pending_action import PendingAction
from app.repositories.pending_action_repository import cleanup_expired_actions


def test_cleanup_expired_actions(db_session, create_test_user):
    user, _ = create_test_user(email="cleanup@example.com")

    # expired action
    db_session.add(PendingAction(
        user_id=user.id,
        action_type="email_verification_code",
        code="expired-code",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    ))
    # valid action
    db_session.add(PendingAction(
        user_id=user.id,
        action_type="password_reset_code",
        code="valid-code",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    db_session.flush()

    cleanup_expired_actions(db_session)

    remaining = db_session.query(PendingAction).filter(
        PendingAction.user_id == user.id
    ).all()
    assert len(remaining) == 1
    assert remaining[0].code == "valid-code"

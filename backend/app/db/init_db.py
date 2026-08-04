from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import hash_password


def ensure_seed_data(db: Session) -> None:
    admin = db.scalar(select(User).where(User.username == "admin"))
    if admin:
        return
    db.add(
        User(
            username="admin",
            email="admin@example.local",
            password_hash=hash_password("admin123"),
            role="admin",
        )
    )
    db.commit()


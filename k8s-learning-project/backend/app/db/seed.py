from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models import Order, OrderStatus, User
from app.db.session import SessionLocal


def run_seed() -> None:
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
        if admin is None:
            admin = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                full_name="Platform Admin",
                hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            db.flush()

        demo_email = "demo.user@k8s-learning.local"
        demo_user = db.scalar(select(User).where(User.email == demo_email))
        if demo_user is None:
            demo_user = User(
                email=demo_email,
                full_name="Demo User",
                hashed_password=get_password_hash("demo12345"),
                is_active=True,
                is_superuser=False,
            )
            db.add(demo_user)
            db.flush()

        existing_orders = db.scalars(select(Order).where(Order.user_id == demo_user.id)).all()
        if not existing_orders:
            orders = [
                Order(
                    user_id=demo_user.id,
                    title="First sample order",
                    description="Seeded sample data for local development",
                    status=OrderStatus.pending,
                    total_amount=Decimal("49.99"),
                    priority=2,
                ),
                Order(
                    user_id=demo_user.id,
                    title="Express package",
                    description="High-priority shipment",
                    status=OrderStatus.processing,
                    total_amount=Decimal("125.50"),
                    priority=5,
                ),
                Order(
                    user_id=demo_user.id,
                    title="Completed order sample",
                    description="Successfully delivered order",
                    status=OrderStatus.completed,
                    total_amount=Decimal("19.00"),
                    priority=1,
                ),
            ]
            db.add_all(orders)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()


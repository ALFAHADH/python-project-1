import logging
import time

from app.db.models import Order, OrderStatus
from app.db.session import SessionLocal
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_order",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_order(self, order_id: int) -> str:
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if order is None:
            logger.warning("Order not found in background worker", extra={"order_id": order_id})
            return "not-found"

        if order.status == OrderStatus.pending:
            order.status = OrderStatus.processing
            db.add(order)
            db.commit()

        # Simulates external processing (billing/logistics integrations).
        time.sleep(3)

        order.status = OrderStatus.completed
        db.add(order)
        db.commit()
        logger.info("Order processed", extra={"order_id": order_id, "status": order.status.value})
        return "completed"
    except Exception as exc:
        db.rollback()
        logger.exception("Failed processing order", extra={"order_id": order_id, "error": str(exc)})
        raise
    finally:
        db.close()


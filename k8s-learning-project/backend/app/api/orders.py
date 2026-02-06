import logging
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.models import Order, OrderStatus, User
from app.db.session import get_db
from app.services.order_cache import (
    build_order_cache_key,
    get_cached_orders,
    invalidate_user_order_cache,
    set_cached_orders,
)
from app.workers.tasks import process_order

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger(__name__)


class OrderCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    description: str | None = Field(default=None, max_length=500)
    total_amount: Decimal = Field(gt=0)
    priority: int = Field(default=3, ge=1, le=5)


class OrderUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=140)
    description: str | None = Field(default=None, max_length=500)
    status: OrderStatus | None = None
    total_amount: Decimal | None = Field(default=None, gt=0)
    priority: int | None = Field(default=None, ge=1, le=5)


class OrderResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: str | None
    status: OrderStatus
    total_amount: Decimal
    priority: int

    model_config = ConfigDict(from_attributes=True)


def _get_order_or_404(db: Session, order_id: int, user_id: int) -> Order:
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Order:
    order = Order(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        status=OrderStatus.pending,
        total_amount=payload.total_amount,
        priority=payload.priority,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    invalidate_user_order_cache(current_user.id)

    try:
        process_order.delay(order.id)
    except Exception as exc:
        logger.warning("Order created but background processing queue is unavailable", extra={"error": str(exc)})

    return order


@router.get("/", response_model=list[OrderResponse])
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[OrderResponse]:
    cache_key = build_order_cache_key(current_user.id, status_filter, skip, limit)
    cached = get_cached_orders(cache_key)
    if cached is not None:
        return [OrderResponse.model_validate(item) for item in cached]

    stmt = select(Order).where(Order.user_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
    orders = db.scalars(stmt).all()

    payload = [OrderResponse.model_validate(order).model_dump(mode="json") for order in orders]
    set_cached_orders(cache_key, payload)
    return [OrderResponse.model_validate(item) for item in payload]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Order:
    return _get_order_or_404(db, order_id, current_user.id)


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    payload: OrderUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Order:
    order = _get_order_or_404(db, order_id, current_user.id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

    db.add(order)
    db.commit()
    db.refresh(order)
    invalidate_user_order_cache(current_user.id)
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    order = _get_order_or_404(db, order_id, current_user.id)
    db.delete(order)
    db.commit()
    invalidate_user_order_cache(current_user.id)
    return None


from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)

    shopify_event_id = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    topic = Column(
        String,
        nullable=False,
        default="orders/paid",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "shopify_event_id",
            name="uq_webhook_delivery_event_id",
        ),
    )
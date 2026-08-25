from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.webhook_delivery import WebhookDelivery


def get_delivery(
    db: Session,
    event_id: str,
):
    return (
        db.query(WebhookDelivery)
        .filter(
            WebhookDelivery.shopify_event_id == event_id
        )
        .first()
    )


def register_delivery(
    db: Session,
    event_id: str,
    topic: str = "orders/paid",
):
    delivery = WebhookDelivery(
        shopify_event_id=event_id,
        topic=topic,
    )

    db.add(delivery)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None

    return delivery
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from config import SHOPIFY_WEBHOOK_SECRET
from database import get_db
from schemas.shopify_order import ShopifyOrderPaid
from services.shopify_webhooks import process_paid_order
from services.webhook_security import verify_shopify_webhook
from repositories.webhook_repository import register_delivery


router = APIRouter(
    prefix="/webhooks",
    tags=["Shopify Webhooks"],
)


@router.post("/orders-paid")
async def orders_paid(
    request: Request,
    db: Session = Depends(get_db),
    x_shopify_hmac_sha256: str | None = Header(
        default=None,
        alias="X-Shopify-Hmac-Sha256",
    ),
    x_shopify_event_id: str | None = Header(
        default=None,
        alias="X-Shopify-Event-Id",
    ),
):
    if not SHOPIFY_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Shopify webhook secret is not configured.",
        )

    # ---------------------------------------------------------
    # 1. Read the RAW request body.
    # Shopify signs this exact byte sequence.
    # ---------------------------------------------------------
    body = await request.body()

    # ---------------------------------------------------------
    # 2. Require Shopify HMAC.
    # ---------------------------------------------------------
    if not x_shopify_hmac_sha256:
        raise HTTPException(
            status_code=401,
            detail="Missing Shopify webhook signature.",
        )

    # ---------------------------------------------------------
    # 3. Verify HMAC BEFORE parsing or processing anything.
    # ---------------------------------------------------------
    if not verify_shopify_webhook(
        secret=SHOPIFY_WEBHOOK_SECRET,
        body=body,
        hmac_header=x_shopify_hmac_sha256,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Shopify webhook signature.",
        )

    # ---------------------------------------------------------
    # 4. Require Shopify delivery/event ID.
    # ---------------------------------------------------------
    if not x_shopify_event_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Shopify webhook event ID.",
        )

    # ---------------------------------------------------------
    # 5. Register the delivery AFTER HMAC verification.
    #
    # The database unique constraint prevents the same
    # Shopify delivery from being processed twice.
    # ---------------------------------------------------------
    delivery = register_delivery(
        db=db,
        event_id=x_shopify_event_id,
        topic="orders/paid",
    )

    if delivery is None:
        return {
            "status": "duplicate",
            "message": "Shopify webhook delivery already processed.",
        }

    # ---------------------------------------------------------
    # 6. Only parse the JSON after HMAC verification.
    # ---------------------------------------------------------
    order = ShopifyOrderPaid.model_validate_json(body)

    # ---------------------------------------------------------
    # 7. Process the verified Shopify order.
    #
    # process_paid_order() -> award_seeds()
    # award_seeds() commits the transaction.
    # ---------------------------------------------------------
    customer = process_paid_order(
        db=db,
        order=order,
    )

    # ---------------------------------------------------------
    # 8. Existing order-level duplicate protection.
    #
    # We still record the webhook delivery because this was
    # a legitimate Shopify delivery, even if the order itself
    # had already been processed.
    # ---------------------------------------------------------
    if customer is None:
        db.commit()

        return {
            "status": "duplicate",
            "message": "Seeds already awarded for this order.",
        }

    return {
        "status": "success",
        "customer_id": customer.id,
        "balance": customer.current_balance,
    }
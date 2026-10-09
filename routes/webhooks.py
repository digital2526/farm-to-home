import json
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from config import SHOPIFY_WEBHOOK_SECRET
from database import get_db
from repositories.webhook_repository import register_delivery
from schemas.shopify_order import ShopifyOrderPaid
from services.shopify_webhooks import (
    calculate_delivery_details,
    get_order_delivery_details,
    process_paid_order,
)
from services.webhook_security import verify_shopify_webhook
from shopify_admin import set_order_delivery_details


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

    body = await request.body()

    if not x_shopify_hmac_sha256:
        raise HTTPException(
            status_code=401,
            detail="Missing Shopify webhook signature.",
        )

    if not verify_shopify_webhook(
        secret=SHOPIFY_WEBHOOK_SECRET,
        body=body,
        hmac_header=x_shopify_hmac_sha256,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Shopify webhook signature.",
        )

    if not x_shopify_event_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Shopify webhook event ID.",
        )

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

    order = ShopifyOrderPaid.model_validate_json(body)

    result = process_paid_order(
        db=db,
        order=order,
    )

    delivery_details = get_order_delivery_details(order)

    set_order_delivery_details(
        order_id=order.id,
        delivery_date=delivery_details["delivery_date"],
        delivery_day=delivery_details["delivery_day"],
        delivery_time=delivery_details["delivery_time"],
    )

    db.commit()

    return {
        **result,
        "delivery_date": str(delivery_details["delivery_date"]),
        "delivery_day": delivery_details["delivery_day"],
        "delivery_time": delivery_details["delivery_time"],
    }


@router.post("/orders-created")
async def orders_created(
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

    body = await request.body()

    if not x_shopify_hmac_sha256:
        raise HTTPException(
            status_code=401,
            detail="Missing Shopify webhook signature.",
        )

    if not verify_shopify_webhook(
        secret=SHOPIFY_WEBHOOK_SECRET,
        body=body,
        hmac_header=x_shopify_hmac_sha256,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Shopify webhook signature.",
        )

    if not x_shopify_event_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Shopify webhook event ID.",
        )

    delivery = register_delivery(
        db=db,
        event_id=x_shopify_event_id,
        topic="orders/create",
    )

    if delivery is None:
        return {
            "status": "duplicate",
            "message": "Shopify webhook delivery already processed.",
        }

    try:
        body_data = json.loads(body)

        order_id = body_data.get("id")
        created_at = body_data.get("created_at")

        if not order_id:
            return {
                "status": "ignored",
                "reason": "missing_order_id",
            }

        if not created_at:
            return {
                "status": "ignored",
                "reason": "missing_created_at",
                "order_id": order_id,
            }

        created_at_dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        delivery_options = calculate_delivery_details(created_at_dt)

        if body_data.get("shipping_address"):
            delivery_details = delivery_options["home"]
        else:
            delivery_details = delivery_options["pickup"]

        set_order_delivery_details(
            order_id=order_id,
            delivery_date=delivery_details["delivery_date"],
            delivery_day=delivery_details["delivery_day"],
            delivery_time=delivery_details["delivery_time"],
        )

        db.commit()

        return {
            "status": "success",
            "order_id": order_id,
            "delivery_date": str(delivery_details["delivery_date"]),
            "delivery_day": delivery_details["delivery_day"],
            "delivery_time": delivery_details["delivery_time"],
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        return {
            "status": "error",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


@router.post("/recharge-charge-paid")
async def recharge_charge_paid(request: Request):
    try:
        body = await request.json()

        charge_id = body.get("id")
        charge_type = body.get("type")
        charge_status = body.get("status")

        if str(charge_type).lower() != "recurring":
            return {
                "status": "ignored",
                "reason": "not_recurring",
                "charge_id": charge_id,
            }

        if str(charge_status).lower() != "success":
            return {
                "status": "ignored",
                "reason": "charge_not_successful",
                "charge_id": charge_id,
            }

        external_order_id = body.get("external_order_id") or {}
        shopify_order_id = external_order_id.get("ecommerce")

        if not shopify_order_id:
            return {
                "status": "ignored",
                "reason": "missing_shopify_order_id",
                "charge_id": charge_id,
            }

        try:
            shopify_order_id = int(shopify_order_id)
        except (TypeError, ValueError):
            return {
                "status": "ignored",
                "reason": "invalid_shopify_order_id",
                "charge_id": charge_id,
                "external_order_id": external_order_id,
            }

        created_at = body.get("created_at")

        if not created_at:
            raise HTTPException(
                status_code=400,
                detail="Recharge charge is missing created_at",
            )

        created_at_dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        delivery_options = calculate_delivery_details(created_at_dt)

        if body.get("shipping_address"):
            delivery_details = delivery_options["home"]
        else:
            delivery_details = delivery_options["pickup"]

        set_order_delivery_details(
            order_id=shopify_order_id,
            delivery_date=delivery_details["delivery_date"],
            delivery_day=delivery_details["delivery_day"],
            delivery_time=delivery_details["delivery_time"],
        )

        return {
            "status": "success",
            "charge_id": charge_id,
            "shopify_order_id": shopify_order_id,
            "delivery_date": str(delivery_details["delivery_date"]),
            "delivery_day": delivery_details["delivery_day"],
            "delivery_time": delivery_details["delivery_time"],
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Recharge charge processing failed"
        )
        raise HTTPException(
            status_code=500,
            detail="Recharge charge processing failed",
        )
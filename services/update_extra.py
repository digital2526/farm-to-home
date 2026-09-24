from fastapi import HTTPException

from recharge import (
    get_customer_by_shopify_id,
    get_valid_extra_onetime,
    update_onetime_quantity,
)


def update_extra(
    shopify_customer_id,
    subscription_id,
    quantity,
):
    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found."
        )

    recharge_customer_id = customer["id"]

    onetime = get_valid_extra_onetime(
        recharge_customer_id,
        subscription_id,
    )

    if not onetime:
        raise HTTPException(
            status_code=403,
            detail="One-time item is not an approved extra."
        )

    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be at least 1."
        )

    updated = update_onetime_quantity(
        subscription_id,
        quantity,
    )

    return {
        "success": True,
        "subscription":
            updated["onetime"],
    }
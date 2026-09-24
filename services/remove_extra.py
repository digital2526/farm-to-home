from fastapi import HTTPException

from recharge import (
    get_customer_by_shopify_id,
    get_valid_extra_onetime,
    delete_onetime,
)


def remove_extra(
    shopify_customer_id,
    subscription_id,
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

    return delete_onetime(
        subscription_id
    )
from fastapi import HTTPException

from recharge import (
    get_customer_by_shopify_id,
    get_valid_extra_subscription,
    delete_subscription,
)

def remove_extra(shopify_customer_id, subscription_id):

    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found."
        )

    recharge_customer_id = customer["id"]

    subscription = get_valid_extra_subscription(
        recharge_customer_id,
        subscription_id,
    )

    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="Subscription is not an approved extra."
        )

    return delete_subscription(subscription_id)

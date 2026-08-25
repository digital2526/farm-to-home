from fastapi import HTTPException
from config import EXTRA_VARIANT_IDS

from recharge import (
    get_customer_by_shopify_id,
    get_addresses,
    get_subscriptions,
    create_subscription,
    get_extra_subscription_by_variant,
    update_subscription_quantity
)


def create_extra_subscription(
    shopify_customer_id,
    variant_id,
    quantity=1
):
    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be at least 1."
        )

    if int(variant_id) not in EXTRA_VARIANT_IDS:
        raise HTTPException(
            status_code=400,
            detail="This product is not available as an extra."
        )


    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found."
        )

    recharge_customer_id = customer["id"]

    existing = get_extra_subscription_by_variant(
    recharge_customer_id,
    variant_id
)

    if existing:

        updated = update_subscription_quantity(
            existing["id"],
            quantity
        )

        return {
            "success": True,
            "subscription": updated["subscription"]
        }

    addresses = get_addresses(recharge_customer_id).get("addresses", [])

    if not addresses:
        raise HTTPException(
            status_code=400,
            detail="Customer has no delivery address."
        )

    subscriptions = get_subscriptions(
        recharge_customer_id
    ).get("subscriptions", [])

    active_subscriptions = [
        subscription
        for subscription in subscriptions
        if subscription.get("status") == "ACTIVE"
        and subscription.get("next_charge_scheduled_at")
    ]

    if not active_subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no active subscription with a scheduled delivery."
        )

    subscription = min(
        active_subscriptions,
        key=lambda item: item["next_charge_scheduled_at"]
    )

    address_id = subscription.get("address_id")

    address = next(
        (
            address
            for address in addresses
            if address.get("id") == address_id
        ),
        None,
    )

    if not address:
        raise HTTPException(
            status_code=400,
            detail="No delivery address found for the active subscription."
        )

    new_subscription = create_subscription(
        address_id=address["id"],
        variant_id=variant_id,
        quantity=quantity,
        next_charge_date=subscription["next_charge_scheduled_at"]
    )

    return {
        "success": True,
        "subscription": new_subscription["subscription"]
    }
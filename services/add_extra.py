from fastapi import HTTPException
from shopify_admin import is_extra_variant

from recharge import (
    get_customer_by_shopify_id,
    get_addresses,
    get_subscriptions,
    create_onetime,
)


def create_extra_subscription(
    shopify_customer_id,
    variant_id,
    quantity=1,
):
    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be at least 1.",
        )

    # Only products tagged "add-extra" in Shopify
    # are allowed to be added.
    if not is_extra_variant(variant_id):
        raise HTTPException(
            status_code=400,
            detail="This product is not available as an extra.",
        )

    # Find the Recharge customer belonging to the
    # Shopify customer.
    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found.",
        )

    recharge_customer_id = customer["id"]

    # Get the customer's delivery addresses.
    addresses = get_addresses(
        recharge_customer_id
    ).get("addresses", [])

    if not addresses:
        raise HTTPException(
            status_code=400,
            detail="Customer has no delivery address.",
        )

    # Get all subscriptions for the customer.
    subscriptions = get_subscriptions(
        recharge_customer_id
    ).get("subscriptions", [])

    if not subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no subscription.",
        )

    # IMPORTANT:
    # Use an ACTIVE subscription.
    # Do not use subscriptions[0] because the first
    # subscription may be cancelled.
    active_subscriptions = [
        subscription
        for subscription in subscriptions
        if subscription.get("status", "").upper() == "ACTIVE"
    ]

    if not active_subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no active subscription.",
        )

    subscription = active_subscriptions[0]

    # Get the delivery address from the active subscription.
    address_id = subscription.get("address_id")

    if not address_id:
        raise HTTPException(
            status_code=400,
            detail="Subscription has no delivery address.",
        )

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
            detail="No delivery address found for the subscription.",
        )

    # Get the next scheduled charge date.
    next_charge_date = subscription.get(
        "next_charge_scheduled_at"
    )

    if not next_charge_date:
        raise HTTPException(
            status_code=400,
            detail="Subscription has no scheduled charge date.",
        )

    # IMPORTANT:
    # Add the product as a ONE-TIME item.
    # This does NOT create a new recurring subscription.
    onetime = create_onetime(
        address_id=address["id"],
        variant_id=variant_id,
        quantity=quantity,
        next_charge_scheduled_at=next_charge_date,
    )

    return {
        "success": True,
        "onetime": onetime.get("onetime"),
    }
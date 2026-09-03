from fastapi import HTTPException
from shopify_admin import is_extra_variant

from recharge import (
    get_customer_by_shopify_id,
    get_addresses,
    get_subscriptions,
    create_subscription,
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

    # Get all subscriptions.
    subscriptions = get_subscriptions(
        recharge_customer_id
    ).get("subscriptions", [])

    if not subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no subscription.",
        )

    # IMPORTANT:
    # Use only ACTIVE NON-EXTRA subscriptions as the
    # source for the customer's normal menu/delivery date.
    #
    # Extra subscriptions created by this feature have:
    # subscription_type = extra
    #
    # We must NOT use those subscriptions to determine
    # the customer's next menu date.
    base_subscriptions = []

    for subscription in subscriptions:
        if subscription.get("status", "").upper() != "ACTIVE":
            continue

        properties = subscription.get(
            "properties",
            [],
        )

        is_extra = any(
            prop.get("name") == "subscription_type"
            and prop.get("value") == "extra"
            for prop in properties
        )

        if not is_extra:
            base_subscriptions.append(subscription)

    if not base_subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no active base subscription.",
        )

    # Find the customer's earliest upcoming base
    # subscription charge.
    scheduled_base_subscriptions = [
        subscription
        for subscription in base_subscriptions
        if subscription.get("next_charge_scheduled_at")
    ]

    if not scheduled_base_subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Base subscription has no scheduled charge date.",
        )

    scheduled_base_subscriptions.sort(
        key=lambda subscription: (
            subscription.get("next_charge_scheduled_at")
            or ""
        )
    )

    subscription = scheduled_base_subscriptions[0]

    # Get the address belonging to the base subscription.
    address_id = subscription.get("address_id")

    if not address_id:
        raise HTTPException(
            status_code=400,
            detail="Subscription has no delivery address.",
        )

    # Verify that the address exists.
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

    # This is the actual next delivery date used by the
    # customer's existing menu subscription.
    next_charge_date = subscription.get(
        "next_charge_scheduled_at"
    )

    # Create the extra as a recurring weekly subscription.
    #
    # It starts on the same date as the customer's
    # existing menu subscription and then repeats weekly.
    new_subscription = create_subscription(
        address_id=address_id,
        variant_id=variant_id,
        quantity=quantity,
        next_charge_date=next_charge_date,
    )

    return {
        "success": True,
        "subscription": new_subscription.get(
            "subscription"
        ),
    }
from fastapi import HTTPException
from shopify_admin import is_extra_variant

from recharge import (
    get_customer_by_shopify_id,
    get_addresses,
    get_subscriptions,
    create_subscription,
    get_extra_subscription_by_variant,
    update_subscription_quantity,
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

    if not is_extra_variant(variant_id):
        raise HTTPException(
            status_code=400,
            detail="This product is not available as an extra.",
        )

    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found.",
        )

    recharge_customer_id = customer["id"]

    existing = get_extra_subscription_by_variant(
        recharge_customer_id,
        variant_id,
    )

    if existing:
        updated = update_subscription_quantity(
            existing["id"],
            quantity,
        )

        return {
            "success": True,
            "subscription": updated["subscription"],
        }

    addresses = get_addresses(
        recharge_customer_id
    ).get("addresses", [])

    if not addresses:
        raise HTTPException(
            status_code=400,
            detail="Customer has no delivery address.",
        )

    subscriptions = get_subscriptions(
        recharge_customer_id
    ).get("subscriptions", [])
    
    print("RECHARGE SUBSCRIPTIONS:", subscriptions)

    if not subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no subscription.",
        )

    if not subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no subscription.",
        )

    subscription = subscriptions[0]

    address_id = subscription.get("address_id")

    if not address_id:
        raise HTTPException(
            status_code=400,
            detail="Active subscription has no delivery address.",
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
            detail="No delivery address found for the active subscription.",
        )

    new_subscription = create_subscription(
        address_id=address["id"],
        variant_id=variant_id,
        quantity=quantity,
        next_charge_date=subscription[
            "next_charge_scheduled_at"
        ],
    )

    return {
        "success": True,
        "subscription": new_subscription["subscription"],
    }
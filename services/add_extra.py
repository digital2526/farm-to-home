from fastapi import HTTPException

from shopify_admin import is_extra_variant

from recharge import (
    get_customer_by_shopify_id,
    get_subscriptions,
    get_charges,
    create_subscription,
    set_subscription_next_charge_date,
)

def _is_extra_subscription(subscription):
    properties = subscription.get(
        "properties",
        [],
    )

    for prop in properties:
        if (
            prop.get("name") == "subscription_type"
            and str(prop.get("value", "")).lower() == "extra"
        ):
            return True

    return False


def create_extra_subscription(
    shopify_customer_id,
    variant_id,
    quantity=1,
):
    # ---------------------------------------------------------
    # 1. Validate quantity
    # ---------------------------------------------------------
    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be at least 1.",
        )

    # ---------------------------------------------------------
    # 2. Validate that this Shopify variant is an Add Extra
    # ---------------------------------------------------------
    if not is_extra_variant(variant_id):
        raise HTTPException(
            status_code=400,
            detail="This product is not available as an extra.",
        )

    # ---------------------------------------------------------
    # 3. Find Recharge customer
    # ---------------------------------------------------------
    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found.",
        )

    recharge_customer_id = customer["id"]

    # ---------------------------------------------------------
    # 4. Get customer's active subscriptions
    # ---------------------------------------------------------
    subscriptions_response = get_subscriptions(
        recharge_customer_id
    )
    
    print("\n========== CUSTOMER SUBSCRIPTIONS ==========")

    for s in subscriptions_response.get("subscriptions", []):
        print({
            "id": s.get("id"),
            "product_title": s.get("product_title"),
            "address_id": s.get("address_id"),
            "next_charge_scheduled_at": s.get("next_charge_scheduled_at"),
            "status": s.get("status"),
            "properties": s.get("properties"),
        })

    print("============================================\n")
    
    subscriptions = subscriptions_response.get(
        "subscriptions",
        [],
    )

    if not subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no subscription.",
        )

    # ---------------------------------------------------------
    # 5. Keep only ACTIVE NON-EXTRA subscriptions
    #
    # These are the customer's normal/menu subscriptions.
    # ---------------------------------------------------------
    base_subscriptions = []

    for subscription in subscriptions:
        status = str(
            subscription.get("status", "")
        ).lower()

        if status != "active":
            continue

        if _is_extra_subscription(subscription):
            continue

        address_id = subscription.get(
            "address_id"
        )

        if not address_id:
            continue

        base_subscriptions.append(
            subscription
        )

    if not base_subscriptions:
        raise HTTPException(
            status_code=400,
            detail="Customer has no active base subscription.",
        )

    # ---------------------------------------------------------
    # 6. Use the address of the customer's active base menu
    # ---------------------------------------------------------
    address_id = base_subscriptions[0]["address_id"]

    charges_response = get_charges(
        status="QUEUED",
        limit=250,
        customer_id=recharge_customer_id,
        address_id=address_id,
    )

    charges = charges_response.get(
        "charges",
        [],
    )

    if not charges:
        raise HTTPException(
            status_code=400,
            detail="Customer has no queued delivery charge.",
        )

    # ---------------------------------------------------------
    # 7. Find the next queued delivery charge for this address
    # ---------------------------------------------------------
    valid_charges = [
        charge
        for charge in charges
        if charge.get("scheduled_at")
    ]

    if not valid_charges:
        raise HTTPException(
            status_code=400,
            detail="Customer has no queued delivery charge.",
        )

    valid_charges.sort(
        key=lambda charge: charge["scheduled_at"]
    )

    next_charge = valid_charges[0]

    next_charge_date = next_charge["scheduled_at"]

    # ---------------------------------------------------------
    # 8. Create recurring weekly extra
    #
    # The first charge date is taken directly from Recharge's
    # existing queued Charge.
    #
    # Recharge then manages the recurring weekly schedule.
    # ---------------------------------------------------------
    new_subscription = create_subscription(
        address_id=address_id,
        variant_id=variant_id,
        quantity=quantity,
        next_charge_date=next_charge_date,
    )
    
    created_subscription = new_subscription.get(
        "subscription"
    )

    if not created_subscription:
        raise HTTPException(
            status_code=500,
            detail="Recharge did not return the created subscription.",
        )

    set_subscription_next_charge_date(
        subscription_id=created_subscription["id"],
        date=next_charge_date,
    )

    return {
        "success": True,
        "delivery_date": next_charge_date,
        "address_id": address_id,
        "subscription": created_subscription,
    }
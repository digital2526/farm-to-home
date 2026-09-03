from fastapi import HTTPException

from shopify_admin import is_extra_variant

from recharge import (
    get_customer_by_shopify_id,
    get_subscriptions,
    get_charges,
    create_subscription,
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
    # 6. Find the queued Charge for each base subscription
    #
    # IMPORTANT:
    # We do NOT choose the earliest subscription date.
    #
    # We ask Recharge which QUEUED charge actually exists
    # for that subscription's address.
    # ---------------------------------------------------------
    candidate_charges = []

    for subscription in base_subscriptions:
        address_id = subscription.get(
            "address_id"
        )

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

        for charge in charges:
            scheduled_at = charge.get(
                "scheduled_at"
            )

            if not scheduled_at:
                continue

            candidate_charges.append(
                {
                    "charge": charge,
                    "address_id": address_id,
                    "scheduled_at": scheduled_at,
                }
            )

    if not candidate_charges:
        raise HTTPException(
            status_code=400,
            detail="Customer has no queued delivery charge.",
        )

    # ---------------------------------------------------------
    # 7. Select the next queued Charge
    #
    # This is the actual Recharge charge that will contain
    # the customer's upcoming menu.
    # ---------------------------------------------------------
    candidate_charges.sort(
        key=lambda item: item["scheduled_at"]
    )

    next_charge = candidate_charges[0]

    address_id = next_charge["address_id"]
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

    return {
        "success": True,
        "delivery_date": next_charge_date,
        "address_id": address_id,
        "subscription": new_subscription.get(
            "subscription"
        ),
    }
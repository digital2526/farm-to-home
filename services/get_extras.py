from fastapi import HTTPException

from recharge import (
    get_customer_by_shopify_id,
    get_subscriptions,
    get_charges,
    get_extra_onetimes,
)


def get_extras(shopify_customer_id):

    customer = get_customer_by_shopify_id(
        shopify_customer_id
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found."
        )

    recharge_customer_id = customer["id"]


    # ---------------------------------------------------------
    # Find customer's active main meal-plan subscription
    # ---------------------------------------------------------

    subscriptions_response = get_subscriptions(
        recharge_customer_id
    )

    subscriptions = (
        subscriptions_response.get(
            "subscriptions",
            []
        )
    )

    main_subscription = None

    for subscription in subscriptions:

        status = str(
            subscription.get(
                "status",
                ""
            )
        ).lower()

        if status != "active":
            continue

        properties = subscription.get(
            "properties",
            []
        )

        is_plan_parent = any(
            prop.get("name") == "_plan_parent"
            and str(
                prop.get("value", "")
            ).lower() == "true"
            for prop in properties
        )

        if is_plan_parent:
            main_subscription = subscription
            break


    if not main_subscription:
        return []


    address_id = main_subscription.get(
        "address_id"
    )

    if not address_id:
        return []


    # ---------------------------------------------------------
    # Find NEXT queued charge
    # ---------------------------------------------------------

    charges_response = get_charges(
        status="QUEUED",
        limit=250,
        customer_id=recharge_customer_id,
        address_id=address_id,
    )

    charges = [
        charge
        for charge in charges_response.get(
            "charges",
            []
        )
        if charge.get("scheduled_at")
    ]

    if not charges:
        return []


    charges.sort(
        key=lambda charge:
            charge["scheduled_at"]
    )

    next_charge_date = (
        charges[0]["scheduled_at"]
    )


    # ---------------------------------------------------------
    # Return ONLY Add Extras belonging to
    # the next upcoming charge
    # ---------------------------------------------------------

    return get_extra_onetimes(
        customer_id=recharge_customer_id,
        address_id=address_id,
        next_charge_date=next_charge_date,
    )
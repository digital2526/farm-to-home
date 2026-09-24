from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from shopify_admin import (
    is_extra_variant,
    get_shopify_variant_price,
)

from recharge import (
    get_customer_by_shopify_id,
    get_subscriptions,
    get_charges,
    create_onetime,
    get_extra_onetime_by_variant,
    update_onetime_quantity,
)


def _is_extra_subscription(subscription):
    properties = subscription.get(
        "properties",
        [],
    )

    for prop in properties:
        if (
            prop.get("name") == "subscription_type"
            and str(
                prop.get("value", "")
            ).lower() == "extra"
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
    # 2. Validate Add Extra product
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
    # 4. Get active subscriptions
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
    # 5. Find active BASE meal-plan subscription
    # ---------------------------------------------------------

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

        if _is_extra_subscription(
            subscription
        ):
            continue

        address_id = subscription.get(
            "address_id"
        )

        if not address_id:
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

        raise HTTPException(
            status_code=400,
            detail=(
                "Customer has no active main "
                "meal-plan subscription."
            ),
        )


    address_id = main_subscription.get(
        "address_id"
    )

    if not address_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "Main meal-plan subscription "
                "has no address."
            ),
        )


    # ---------------------------------------------------------
    # 6. Find customer's NEXT queued charge
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

        raise HTTPException(
            status_code=400,
            detail=(
                "Customer has no queued delivery "
                "charge for the main meal plan."
            ),
        )


    charges.sort(
        key=lambda charge:
            charge["scheduled_at"]
    )

    next_charge = charges[0]

    next_charge_date = (
        next_charge["scheduled_at"]
    )


    # ---------------------------------------------------------
    # 7. Check if same extra is already added
    #    to THIS next delivery
    # ---------------------------------------------------------

    existing = get_extra_onetime_by_variant(
        customer_id=recharge_customer_id,
        variant_id=variant_id,
        address_id=address_id,
        next_charge_date=next_charge_date,
    )

    if existing:

        updated = update_onetime_quantity(
            existing["id"],
            quantity,
        )

        onetime = updated.get(
            "onetime"
        )

        if not onetime:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Recharge did not return "
                    "the updated one-time item."
                ),
            )

        return {
            "success": True,
            "delivery_date":
                next_charge_date,
            "address_id":
                address_id,
            "subscription":
                onetime,
        }


    # ---------------------------------------------------------
    # 8. Get Shopify product price
    # ---------------------------------------------------------

    try:

        original_price = (
            get_shopify_variant_price(
                variant_id
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to retrieve Shopify "
                "variant price."
            ),
        ) from exc


    # ---------------------------------------------------------
    # 9. Apply 25% subscriber discount
    # ---------------------------------------------------------

    discounted_price = (
        original_price
        * Decimal("0.75")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


    # ---------------------------------------------------------
    # 10. Create ONE-TIME Recharge item
    # ---------------------------------------------------------

    new_onetime = create_onetime(
        address_id=address_id,
        variant_id=variant_id,
        quantity=quantity,
        next_charge_date=next_charge_date,
        price=discounted_price,
        properties=[
            {
                "name":
                    "subscription_type",

                "value":
                    "extra",
            },
            {
                "name":
                    "subscriber_discount",

                "value":
                    "25",
            },
        ],
    )


    print(
        "\n========== CREATED ONE-TIME =========="
    )

    print(new_onetime)

    print(
        "======================================\n"
    )


    created_onetime = (
        new_onetime.get(
            "onetime"
        )
    )


    if not created_onetime:

        raise HTTPException(
            status_code=500,
            detail=(
                "Recharge did not return "
                "the created one-time item."
            ),
        )


    # ---------------------------------------------------------
    # 11. Preserve existing response structure
    # ---------------------------------------------------------

    return {
        "success": True,

        "delivery_date":
            next_charge_date,

        "address_id":
            address_id,

        "subscription":
            created_onetime,
    }
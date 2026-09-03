from fastapi import HTTPException
from shopify_admin import is_extra_variant

from recharge import (
    get_customer_by_shopify_id,
    get_delivery_schedule,
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

    # Only Shopify products tagged "add-extra"
    # can be added as extras.
    if not is_extra_variant(variant_id):
        raise HTTPException(
            status_code=400,
            detail="This product is not available as an extra.",
        )

    # Find the Recharge customer linked to the
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

    # Recharge Delivery Schedule is the source of truth
    # for the customer's upcoming delivery.
    schedule_response = get_delivery_schedule(
        recharge_customer_id
    )

    delivery_schedule = schedule_response.get(
        "deliverySchedule",
        {}
    )

    deliveries = delivery_schedule.get(
        "deliveries",
        []
    )

    if not deliveries:
        raise HTTPException(
            status_code=400,
            detail="Customer has no upcoming delivery.",
        )

    # Recharge returns deliveries in chronological order.
    # Sort them defensively so we always use the first
    # upcoming delivery.
    deliveries = sorted(
        deliveries,
        key=lambda delivery: (
            delivery.get("date") or ""
        )
    )

    next_delivery = deliveries[0]

    next_charge_date = next_delivery.get("date")

    if not next_charge_date:
        raise HTTPException(
            status_code=400,
            detail="Upcoming delivery has no date.",
        )

    orders = next_delivery.get(
        "orders",
        []
    )

    if not orders:
        raise HTTPException(
            status_code=400,
            detail="Upcoming delivery has no order.",
        )

    # Find the address used by the upcoming delivery.
    address_id = None

    for order in orders:
        if order.get("address_id"):
            address_id = order["address_id"]
            break

    if not address_id:
        raise HTTPException(
            status_code=400,
            detail="Upcoming delivery has no address.",
        )

    # Create the extra as a recurring weekly subscription.
    #
    # Recharge receives the actual upcoming delivery date
    # from its own Delivery Schedule. We do not calculate
    # the date ourselves.
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
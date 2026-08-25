import logging
import logging

from sqlalchemy.orm import Session

from recharge import get_charges, get_customer

from repositories.transaction_repository import (
    get_by_recharge_charge_id,
)

from services.seeds import (
    award_seeds,
    get_or_create_customer,
)

from services.seed_rules import calculate_seeds


logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

def sync_recharge_rewards(db: Session):

    charges = get_charges()["charges"]

    awarded = 0

    for charge in charges:

        try:

            # -------------------------------------------------
            # 1. Only successful Recharge charges can earn Seeds
            # -------------------------------------------------
            if charge.get("status") != "SUCCESS":
                continue

            # -------------------------------------------------
            # 2. Only recurring subscription charges are eligible
            #
            # This prevents first-order CHECKOUT charges from
            # being awarded by this synchronization process.
            # -------------------------------------------------
            if charge.get("type") != "RECURRING":
                continue

            # -------------------------------------------------
            # 3. Require the Recharge recurring-order tag
            # -------------------------------------------------
            tags = {
                tag.strip()
                for tag in str(charge.get("tags", "")).split(",")
            }

            if "Subscription Recurring Order" not in tags:
                continue

            # -------------------------------------------------
            # 4. Idempotency protection
            #
            # The recharge_charge_id also has a UNIQUE database
            # constraint, so the same charge cannot be awarded
            # twice even if synchronization runs concurrently.
            # -------------------------------------------------
            recharge_charge_id = str(charge["id"])

            if get_by_recharge_charge_id(
                db,
                recharge_charge_id,
            ):
                continue

            # -------------------------------------------------
            # 5. Get Recharge customer
            # -------------------------------------------------
            recharge_customer = get_customer(
                charge["customer_id"]
            )["customer"]

            # -------------------------------------------------
            # 6. Create or fetch our local customer
            # -------------------------------------------------
            customer = get_or_create_customer(
                db=db,
                shopify_customer_id=recharge_customer["shopify_customer_id"],
                email=recharge_customer["email"],
            )

            # -------------------------------------------------
            # 7. Calculate Seeds
            #
            # Current business rule:
            # 1€ spent = 1 Seed
            # -------------------------------------------------
            total = float(
                charge["total_line_items_price"]
            )

            seeds = calculate_seeds(total)

            # -------------------------------------------------
            # 8. Award Seeds using Recharge charge ID as the
            #    idempotency identifier.
            # -------------------------------------------------
            award_seeds(
                db=db,
                shopify_customer_id=customer.shopify_customer_id,
                email=customer.email,
                amount=seeds,
                reason=f"Recharge Charge #{charge['id']}",
                order_id=str(charge["shopify_order_id"]),
                recharge_charge_id=str(charge["id"]),
            )

            awarded += 1

        except Exception:
            logger.exception(
                "Failed to process Recharge charge %s",
                charge.get("id"),
            )
            continue

    return {
        "status": "success",
        "awarded": awarded,
    }
from sqlalchemy.orm import Session
from repositories.transaction_repository import create_transaction
from repositories.customer_repository import update_balance
from enums.transaction_type import TransactionType

from repositories.customer_repository import (
    get_by_shopify_customer_id,
    get_for_update_by_shopify_customer_id,
    create_customer,
)


def get_or_create_customer(
    db: Session,
    shopify_customer_id: str,
    email: str,
):
    customer = get_by_shopify_customer_id(
        db,
        shopify_customer_id,
    )

    if customer:
        return customer

    return create_customer(
        db,
        shopify_customer_id,
        email,
    )


def get_customer_balance(
    db: Session,
    shopify_customer_id: str,
):
    customer = get_by_shopify_customer_id(
        db,
        shopify_customer_id,
    )

    if not customer:
        return 0

    return customer.current_balance

def award_seeds(
    db: Session,
    shopify_customer_id: str,
    email: str,
    amount: int,
    reason: str,
    order_id: str | None = None,
    recharge_charge_id: str | None = None,
):
    if amount <= 0:
        raise ValueError("Seed award amount must be greater than zero.")

    try:
        customer = get_or_create_customer(
            db=db,
            shopify_customer_id=shopify_customer_id,
            email=email,
        )

        customer = get_for_update_by_shopify_customer_id(
            db=db,
            shopify_customer_id=shopify_customer_id,
        )

        if not customer:
            raise ValueError("Customer could not be loaded for update.")

        create_transaction(
            db=db,
            customer_id=customer.id,
            amount=amount,
            reason=reason,
            transaction_type=TransactionType.EARN,
            order_id=order_id,
            recharge_charge_id=recharge_charge_id,
        )

        update_balance(
            db=db,
            customer=customer,
            amount=amount,
        )

        db.commit()

        db.refresh(customer)

        return customer

    except Exception:
        db.rollback()
        raise
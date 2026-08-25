from sqlalchemy.orm import Session

from models.customer import Customer


def get_by_shopify_customer_id(
    db: Session,
    shopify_customer_id: str,
):
    return (
        db.query(Customer)
        .filter(Customer.shopify_customer_id == shopify_customer_id)
        .first()
    )

def get_for_update_by_shopify_customer_id(
    db: Session,
    shopify_customer_id: str,
):
    """
    Lock the customer row during balance-changing operations.

    This prevents concurrent redemption requests from spending
    the same Seeds balance. The production database must support
    row-level SELECT ... FOR UPDATE semantics.
    """
    return (
        db.query(Customer)
        .filter(
            Customer.shopify_customer_id == shopify_customer_id
        )
        .with_for_update()
        .first()
    )

def create_customer(
    db: Session,
    shopify_customer_id: str,
    email: str,
):
    customer = Customer(
        shopify_customer_id=shopify_customer_id,
        email=email,
        current_balance=0,
    )

    db.add(customer)
    db.flush()
    db.refresh(customer)

    return customer


def update_balance(
    db: Session,
    customer: Customer,
    amount: int,
):
    customer.current_balance += amount

    db.flush()
    db.refresh(customer)

    return customer

def deduct_balance(
    db: Session,
    customer: Customer,
    amount: int,
):
    customer.current_balance -= amount

    db.flush()

    db.refresh(customer)

    return customer

def get_by_email(
    db: Session,
    email: str,
):
    return (
        db.query(Customer)
        .filter(Customer.email == email)
        .first()
    )
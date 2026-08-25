from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from repositories.customer_repository import (
    get_for_update_by_shopify_customer_id,
    deduct_balance,
)
from repositories.reward_repository import get_reward_by_id
from repositories.transaction_repository import create_transaction
from repositories.redemption_repository import create_redemption

from enums.transaction_type import TransactionType
from services.email_service import EmailService


def redeem_reward(
    db: Session,
    shopify_customer_id: str,
    reward_id: int,
):
    customer = get_for_update_by_shopify_customer_id(
        db,
        shopify_customer_id,
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    reward = get_reward_by_id(
        db,
        reward_id,
    )

    if not reward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reward not found",
        )

    if customer.current_balance < reward.seed_cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough Seeds",
        )

    # Record the redemption transaction
    create_transaction(
        db=db,
        customer_id=customer.id,
        amount=-reward.seed_cost,
        reason=f"Redeemed {reward.name}",
        transaction_type=TransactionType.REDEEM,
    )

    # Deduct the customer's balance
    deduct_balance(
        db=db,
        customer=customer,
        amount=reward.seed_cost,
    )

    # Create a redemption request
    create_redemption(
        db=db,
        customer_id=customer.id,
        reward_id=reward.id,
        seeds_spent=reward.seed_cost,
    )

    db.commit()
    db.refresh(customer)

    # Send confirmation email to the customer
    EmailService.send_customer_reward_email(
        customer=customer,
        reward=reward,
    )

    # Send notification email to the Terramay admin
    EmailService.send_admin_reward_email(
        customer=customer,
        reward=reward,
    )

    return customer
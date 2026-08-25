from sqlalchemy.orm import Session

from repositories.customer_repository import get_by_shopify_customer_id
from repositories.reward_repository import get_active_rewards
from repositories.transaction_repository import get_customer_transactions


def get_dashboard(
    db: Session,
    shopify_customer_id: str,
):

    customer = get_by_shopify_customer_id(
        db,
        shopify_customer_id,
    )


    if customer is None:
        return None

    rewards = get_active_rewards(db)

    history = get_customer_transactions(
        db,
        customer.id,
    )


    return {
        "customer": customer,
        "rewards": rewards,
        "history": history,
    }
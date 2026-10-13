from sqlalchemy.orm import Session


def process_paid_order(
    db: Session,
    order,
):
    """
    Shopify paid orders are intentionally NOT a Seeds
    awarding source.

    Recharge is the authoritative source for Seeds rewards.
    This prevents a Recharge subscription renewal from being
    rewarded both by Shopify and Recharge.
    """

    return None
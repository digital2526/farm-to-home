from sqlalchemy.orm import Session

from models.reward import Reward


def get_active_rewards(db: Session):
    return (
        db.query(Reward)
        .filter(Reward.active == True)
        .order_by(Reward.seed_cost.asc())
        .all()
    )
    
def get_reward_by_id(
    db: Session,
    reward_id: int,
):
    return (
        db.query(Reward)
        .filter(
            Reward.id == reward_id,
            Reward.active == True,
        )
        .first()
    )
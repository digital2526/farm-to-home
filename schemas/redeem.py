from pydantic import BaseModel


class RedeemRewardRequest(BaseModel):
    reward_id: intx
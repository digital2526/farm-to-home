from database import SessionLocal
from models.reward import Reward

db = SessionLocal()

rewards = db.query(Reward).order_by(Reward.id).all()

print("\nCurrent rewards:\n")

for reward in rewards:
    print("-" * 60)
    print(f"ID: {reward.id}")
    print(f"Name: {reward.name}")
    print(f"Description: {reward.description}")
    print(f"Seeds: {reward.seed_cost}")

db.close()
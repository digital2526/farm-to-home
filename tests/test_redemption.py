import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from config import DATABASE_URL

from models.customer import Customer
from models.reward import Reward
from services.redemption import redeem_reward


TEST_DATABASE_URL = DATABASE_URL.rsplit("/", 1)[0] + "/terramay_seeds_test"

engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_redemption_cannot_spend_more_than_available_balance():
    db = TestingSessionLocal()

    customer = Customer(
        shopify_customer_id="customer-001",
        email="customer@example.com",
        current_balance=100,
    )

    reward = Reward(
        name="Test Reward",
        description="Test reward",
        seed_cost=100,
        reward_type="test",
        reward_value="TEST",
        active=True,
    )

    db.add(customer)
    db.add(reward)
    db.commit()

    customer_id = customer.shopify_customer_id
    reward_id = reward.id

    db.close()

    results = []
    errors = []

    def redeem():
        session = TestingSessionLocal()

        try:
            result = redeem_reward(
                db=session,
                shopify_customer_id=customer_id,
                reward_id=reward_id,
            )
            results.append(result.current_balance)
        except Exception as exc:
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    thread_1 = threading.Thread(target=redeem)
    thread_2 = threading.Thread(target=redeem)

    thread_1.start()
    thread_2.start()

    thread_1.join()
    thread_2.join()

    db = TestingSessionLocal()

    final_customer = (
        db.query(Customer)
        .filter(
            Customer.shopify_customer_id == customer_id
        )
        .first()
    )

    db.close()

    # The customer's balance must never become negative.
    assert final_customer.current_balance >= 0

    # Only one redemption can spend the available 100 Seeds.
    assert len(results) + len(errors) == 2

    successful_redemptions = [
        balance for balance in results
        if balance >= 0
    ]

    assert len(successful_redemptions) <= 1
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
)
from enums.transaction_type import TransactionType
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class SeedTransaction(Base):
    __tablename__ = "seed_transactions"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            name="uq_seed_transaction_order_id",
        ),
        UniqueConstraint(
            "recharge_charge_id",
            name="uq_seed_transaction_recharge_charge_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    transaction_type = Column(
        Enum(TransactionType),
        nullable=False,
    )

    amount = Column(
        Integer,
        nullable=False,
    )

    reason = Column(
        String,
        nullable=False,
    )

    order_id = Column(
        String,
        nullable=True,
    )

    recharge_charge_id = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    customer = relationship(
        "Customer",
        back_populates="transactions",
    )
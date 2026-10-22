from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from marketplace.accounts.models import User, utcnow


class MockBase(DeclarativeBase):
    pass


class Experience(MockBase):
    __tablename__ = "demo_experiences"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id))
    title: Mapped[str] = mapped_column(String(180), default="")
    teaser: Mapped[str] = mapped_column(String(600), default="")
    body: Mapped[str] = mapped_column(Text)
    taxonomy: Mapped[list] = mapped_column(JSONB, default=list)
    price_coins: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    rewarded: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Wallet(MockBase):
    __tablename__ = "demo_wallets"
    __table_args__ = (CheckConstraint("available >= 0 AND reserved >= 0"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id), primary_key=True)
    available: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class Ledger(MockBase):
    __tablename__ = "demo_transactions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id))
    operation: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[str] = mapped_column(String(40))
    coins: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Entitlement(MockBase):
    __tablename__ = "demo_entitlements"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id), primary_key=True)
    experience_id: Mapped[UUID] = mapped_column(ForeignKey(Experience.id), primary_key=True)
    paid_coins: Mapped[int] = mapped_column(Integer)
    purchased_body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Vote(MockBase):
    __tablename__ = "demo_votes"
    __table_args__ = (CheckConstraint("value IN (-1, 1)"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id), primary_key=True)
    experience_id: Mapped[UUID] = mapped_column(ForeignKey(Experience.id), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class MoneyRequest(MockBase):
    __tablename__ = "demo_money_requests"
    __table_args__ = (CheckConstraint("coins > 0"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id))
    kind: Mapped[str] = mapped_column(String(20))
    coins: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    bank_reference: Mapped[str | None] = mapped_column(String(100), unique=True)
    return_experience_id: Mapped[UUID | None] = mapped_column(ForeignKey(Experience.id))
    query_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SearchSession(MockBase):
    __tablename__ = "demo_search_sessions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey(User.__table__.c.id))
    session_digest: Mapped[str] = mapped_column(String(64))
    query: Mapped[str] = mapped_column(String(4000))
    result_ids: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reward(MockBase):
    __tablename__ = "demo_rewards"
    __table_args__ = (UniqueConstraint("author_id", "fingerprint"),)
    experience_id: Mapped[UUID] = mapped_column(ForeignKey(Experience.id), primary_key=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey(User.__table__.c.id))
    fingerprint: Mapped[str] = mapped_column(String(64))

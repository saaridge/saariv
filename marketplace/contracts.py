"""Immutable transport contracts. ORM rows are never public response objects."""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID | None = None
    roles: frozenset[str] = frozenset()

    @property
    def authenticated(self):
        return self.user_id is not None


GUEST = Principal()


def _scalar(value):
    return str(value) if isinstance(value, UUID) else value


def _allow(value, keys):
    if value is None:
        return None
    if isinstance(value, dict):
        return {key: _scalar(value[key]) for key in keys if key in value}
    return {key: _scalar(getattr(value, key)) for key in keys if hasattr(value, key)}


def _taxonomy(value):
    keys = {"domain", "subdomain", "topic", "subtopic", "domain_name", "subdomain_name", "topic_name", "name",
            "domains", "subdomains", "topics", "subtopics"}
    if isinstance(value, dict):
        return {key: _taxonomy(item) for key, item in value.items() if key in keys}
    if isinstance(value, (tuple, list)):
        return [_taxonomy(item) for item in value]
    return value if isinstance(value, str) else None


@dataclass(frozen=True)
class AuthorRating:
    upvotes: int
    downvotes: int
    ranking_score: float

    def to_dict(self):
        return _allow(self, ("upvotes", "downvotes", "ranking_score"))


@dataclass(frozen=True)
class ExperienceCard:
    experience_id: UUID
    title: str
    teaser: str
    taxonomy: dict
    price_coins: int
    author: object | None
    rating: object | None
    unlocked: bool

    def to_dict(self, *, principal=GUEST):
        return {"experience_id": str(self.experience_id), "title": self.title, "teaser": self.teaser,
                "taxonomy": _taxonomy(self.taxonomy), "price_coins": self.price_coins,
                "author": _allow(self.author, ("user_id", "display_name", "avatar_url")) if principal.authenticated else None,
                "rating": _allow(self.rating, ("upvotes", "downvotes", "ranking_score")),
                "unlocked": bool(self.unlocked and principal.authenticated)}


@dataclass(frozen=True)
class SearchPage:
    query_id: str
    items: list[ExperienceCard]
    next_cursor: str | None
    login_required: bool
    retrieval_mode: str

    def to_dict(self, *, principal=GUEST):
        return {"query_id": self.query_id, "items": [item.to_dict(principal=principal) for item in self.items],
                "next_cursor": self.next_cursor if principal.authenticated else None,
                "login_required": self.login_required, "retrieval_mode": self.retrieval_mode}


class Receipt:
    def to_dict(self):
        return {name: _scalar(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class WalletSnapshot(Receipt):
    available_coins: int
    reserved_coins: int
    withdrawable_coins: int


@dataclass(frozen=True)
class UnlockReceipt(Receipt):
    entitlement_id: UUID
    experience_id: UUID
    charged_coins: int
    available_coins: int


@dataclass(frozen=True)
class RequestReceipt(Receipt):
    request_id: UUID
    status: str
    coins: int
    fiat_minor: int
    currency: str
    next_path: str | None


@dataclass(frozen=True)
class ApprovalReceipt(Receipt):
    experience_id: UUID
    revision_id: UUID
    reward_transaction_id: UUID | None
    index_job_id: UUID


class MarketplaceError(Exception):
    def __init__(self, code, message, status=400, *, details=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details = details or {}

    def to_dict(self):
        return {"ok": False, "error": {"code": self.code, "message": self.message, "details": self.details}}

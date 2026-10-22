"""Synthetic-only business flows. No provider, embedding or payment network calls."""
from datetime import timedelta
import hashlib
import re
import secrets
from uuid import UUID, NAMESPACE_URL, uuid5

from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy import select, text

from marketplace.accounts.models import User, OAuthIdentity, utcnow
from marketplace.contracts import MarketplaceError
from marketplace.db import Base
from .models import MockBase, Experience, Wallet, Ledger, Entitlement, Vote, MoneyRequest, SearchSession, Reward


def demo_id(name):
    return uuid5(NAMESPACE_URL, "saariv-local-mock:" + name)


PERSONAS = {
    "reader": {"id": demo_id("reader"), "name": "Alex Reader"},
    "author": {"id": demo_id("author"), "name": "Maya Author"},
    "admin": {"id": demo_id("admin"), "name": "Demo Admin"},
}
TREASURY = demo_id("treasury")
STOPWORDS = set("a an and are as at be been can did do does for from had has have how i in is it me my of on or others our that the their them they this to was were what when where which who why will with would you your about".split())


def as_uuid(value):
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise MarketplaceError("invalid_id", "Choose a valid demo record.") from None


def amount(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,5}", str(value)):
        raise MarketplaceError("invalid_coins", "Choose a positive whole number of demo coins (up to 999999).")
    return int(value)


class DemoService:
    def __init__(self, db, secret):
        self.db = db
        self.signer = URLSafeTimedSerializer(secret, salt="saariv-mock-quote")

    def bootstrap(self):
        Base.metadata.create_all(self.db.engine)
        MockBase.metadata.create_all(self.db.engine)
        with self.db.transaction() as session:
            session.execute(text("SELECT pg_advisory_xact_lock(844203001)"))
            people = {**PERSONAS, "jordan": {"id": demo_id("jordan"), "name": "Jordan Guide"},
                "sam": {"id": demo_id("sam"), "name": "Sam Explorer"},
                "treasury": {"id": TREASURY, "name": "Demo reward treasury"}}
            for key, person in people.items():
                if not session.get(User, person["id"]):
                    session.add(User(id=person["id"], display_name=person["name"], email=key+"@demo.invalid",
                        roles=["admin"] if key == "admin" else [], is_active=key != "treasury"))
                    session.flush()
                    session.add(Wallet(user_id=person["id"], available=10000 if key == "treasury" else 0, reserved=0))
                if key in PERSONAS:
                    for provider in ("google", "linkedin", "facebook"):
                        exists = session.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == provider,
                            OAuthIdentity.subject == "local-mock:"+key))
                        if not exists:
                            session.add(OAuthIdentity(user_id=person["id"], provider=provider, subject="local-mock:"+key))
            samples = [
                ("author", "Finding housing before a city move", "Questions I considered before choosing an apartment.", 25,
                 "I planned on moving to a new city. I asked about housing deposits and compared apartment listings before signing anything. I visited neighbourhoods and checked the commute. These are sample experiences for the local demo."),
                ("jordan", "Comparing neighbourhoods before moving", "A checklist for exploring a new city.", 30,
                 "Before moving to a new city, I compared housing costs, transport links and grocery options. I walked through each neighbourhood at different times. This synthetic story demonstrates local retrieval."),
                ("sam", "Budgeting an apartment deposit", "How I planned the initial costs of housing.", 20,
                 "When planning on moving, I wrote down the housing deposit, first rent payment and furniture costs. I asked the landlord about the deposit terms. This is a synthetic demo experience."),
                ("jordan", "Starting a job in a new city", "Preparing for work while moving home.", 35,
                 "I was moving to a new city for work. I planned temporary housing while learning the commute. I asked my future team about their office days. This sample keeps plans separate from completed actions."),
                ("sam", "Building a support network after moving", "Small steps for getting to know a city.", 15,
                 "After moving to a new city, I joined a neighbourhood walking group and asked neighbours about local events. I planned a weekly call with friends. This is sample content, not a real person's biography."),
                ("author", "Keeping a moving checklist", "Organising the practical details of relocation.", 10,
                 "Before moving to a new city, I created a housing checklist covering utilities, address changes and packing. I asked about rental insurance. I had not yet booked the moving van. This is synthetic demo content."),
            ]
            for n, (author, title, teaser, price, body) in enumerate(samples):
                if not session.get(Experience, demo_id("experience"+str(n))):
                    session.add(Experience(id=demo_id("experience"+str(n)), author_id=people[author]["id"],
                        title=title, teaser=teaser, body=body, taxonomy=["Moving", "Housing"],
                        price_coins=price, status="approved", rewarded=True, fingerprint=self.fingerprint(body)))

    @staticmethod
    def fingerprint(body):
        return hashlib.sha256(" ".join(body.casefold().split()).encode()).hexdigest()

    @staticmethod
    def _wallets(session, *users):
        ids = sorted(set(as_uuid(user) for user in users))
        rows = session.scalars(select(Wallet).where(Wallet.user_id.in_(ids)).order_by(Wallet.user_id).with_for_update()).all()
        if len(rows) != len(ids):
            raise MarketplaceError("missing_persona", "Choose a demo persona first.", 403)
        return {row.user_id: row for row in rows}

    @staticmethod
    def _admin(session, user_id):
        user = session.get(User, as_uuid(user_id))
        if not user or "admin" not in user.roles:
            raise MarketplaceError("access_denied", "Switch to the Demo Admin persona for this action.", 403)

    @staticmethod
    def _entry(session, user, kind, coins, ref, description):
        session.add(Ledger(user_id=user, kind=kind, coins=coins,
            operation=f"{kind}:{ref}:{user}", description=description))

    def wallet(self, user_id):
        with self.db.transaction() as session:
            row = session.get(Wallet, as_uuid(user_id))
            if not row:
                raise MarketplaceError("missing_persona", "Choose a demo persona first.", 403)
            return {"available_coins": row.available, "reserved_coins": row.reserved,
                "withdrawable_coins": max(0, row.available-10)//100*100}

    @staticmethod
    def _rating(session, author):
        votes = session.scalars(select(Vote.value).join(Experience, Vote.experience_id == Experience.id)
            .where(Experience.author_id == author)).all()
        up, down = votes.count(1), votes.count(-1)
        return {"upvotes": up, "downvotes": down, "ranking_score": (up+2)/(up+down+4)}

    def _card(self, session, row, user_id):
        author = session.get(User, row.author_id)
        owned = bool(user_id and (row.author_id == user_id or session.get(Entitlement, (user_id, row.id))))
        return {"experience_id": str(row.id), "title": row.title, "teaser": row.teaser,
            "taxonomy": row.taxonomy, "price_coins": row.price_coins,
            "author": {"display_name": author.display_name} if user_id else None,
            "rating": self._rating(session, row.author_id), "unlocked": owned}

    def search(self, query, user_id, digest, cursor=None):
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise MarketplaceError("invalid_query", "Enter a question of up to 4000 characters.")
        with self.db.transaction() as session:
            offset = 0
            if cursor:
                try:
                    qid, value = cursor.split(":")
                    offset = int(value)
                    if offset < 0 or offset > 10000:
                        raise ValueError()
                except (ValueError, AttributeError):
                    raise MarketplaceError("invalid_cursor", "Search again to refresh these results.") from None
                saved = self._query(session, qid, user_id, digest)
            else:
                terms = set(re.findall(r"[a-z0-9]+", query.casefold()))-STOPWORDS
                ranked = []
                for row in session.scalars(select(Experience).where(Experience.status == "approved")):
                    words = set(re.findall(r"[a-z0-9]+", (row.title+" "+row.teaser+" "+row.body+" "+" ".join(row.taxonomy)).casefold()))
                    score = len(terms & words)
                    if score:
                        ranked.append((self._rating(session, row.author_id)["ranking_score"], score, str(row.id)))
                ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
                saved = SearchSession(id=secrets.token_urlsafe(24), user_id=user_id, session_digest=digest,
                    query=query, result_ids=[row[2] for row in ranked])
                session.add(saved)
            limit = 12 if user_id else 4
            if not user_id:
                offset = 0
            rows = [session.get(Experience, as_uuid(eid)) for eid in saved.result_ids[offset:offset+limit]]
            cards = [self._card(session, row, user_id) for row in rows if row and row.status == "approved"]
            return {"query_id": saved.id, "items": cards, "next_cursor":
                f"{saved.id}:{offset+limit}" if user_id and offset+limit < len(saved.result_ids) else None,
                "login_required": not bool(user_id), "retrieval_mode": "lexical"}

    @staticmethod
    def _query(session, qid, user_id, digest):
        row = session.get(SearchSession, qid)
        owned = row and ((user_id and row.user_id == user_id) or (row.user_id is None and row.session_digest == digest))
        if not owned or row.created_at < utcnow()-timedelta(hours=24):
            raise MarketplaceError("access_denied", "This query is unavailable. Search again.", 403)
        return row

    def claim_query(self, *, principal, query_id, session_digest, session):
        try:
            row = self._query(session, query_id, principal.user_id, session_digest)
        except MarketplaceError:
            return False
        row.user_id = principal.user_id
        return True

    def restored_query(self, qid, user_id, digest):
        with self.db.transaction() as session:
            return self._query(session, qid, user_id, digest).query

    def detail(self, experience_id, user_id, admin=False):
        with self.db.transaction() as session:
            row = session.get(Experience, as_uuid(experience_id))
            if not row or (row.status != "approved" and row.author_id != user_id and not admin):
                raise MarketplaceError("not_found", "This experience is not available.", 404)
            access = "author" if row.author_id == user_id else "admin" if admin else "locked"
            entitlement = session.get(Entitlement, (user_id, row.id)) if user_id else None
            if entitlement and access == "locked":
                access = "unlocked"
            vote = session.get(Vote, (user_id, row.id)) if user_id else None
            return {"experience": self._card(session, row, user_id), "access_state": access,
                "content": {"body": entitlement.purchased_body if entitlement else row.body} if access != "locked" else None,
                "owned_vote": vote.value if vote else 0}

    def quote(self, user_id, experience_id):
        with self.db.transaction() as session:
            row = session.get(Experience, as_uuid(experience_id))
            if not row or row.status != "approved":
                raise MarketplaceError("not_found", "This experience is not available.", 404)
            return {"quote_token": self.signer.dumps({"reader": str(user_id), "experience": str(row.id),
                "price": row.price_coins, "version": row.version}), "price_coins": row.price_coins}

    def unlock(self, user_id, experience_id, quote_token):
        user_id, eid = as_uuid(user_id), as_uuid(experience_id)
        try:
            quote = self.signer.loads(quote_token, max_age=600)
        except (BadSignature, TypeError):
            raise MarketplaceError("stale_quote", "Refresh this experience to confirm its current price.", 409) from None
        with self.db.transaction() as session:
            row = session.get(Experience, eid)
            if not row or row.status != "approved":
                raise MarketplaceError("not_found", "This experience is not available.", 404)
            if row.author_id == user_id:
                raise MarketplaceError("self_purchase", "Authors can read their own stories for free.")
            wallets = self._wallets(session, user_id, row.author_id)
            reader, author = wallets[user_id], wallets[row.author_id]
            if session.get(Entitlement, (user_id, eid)):
                return {"experience_id": str(eid), "charged_coins": 0, "available_coins": reader.available}
            expected = {"reader": str(user_id), "experience": str(eid), "price": row.price_coins, "version": row.version}
            if quote != expected:
                raise MarketplaceError("stale_quote", "Refresh this experience to confirm its current price.", 409)
            if reader.available < row.price_coins:
                raise MarketplaceError("insufficient_coins", "Add demo coins, then return to this experience.", 402,
                    details={"experience_id": str(eid), "required_coins": row.price_coins, "available_coins": reader.available})
            reader.available -= row.price_coins
            author.available += row.price_coins
            session.add(Entitlement(user_id=user_id, experience_id=eid, paid_coins=row.price_coins, purchased_body=row.body))
            self._entry(session, user_id, "purchase", -row.price_coins, eid, "One-time experience unlock")
            self._entry(session, row.author_id, "sale", row.price_coins, f"{eid}:{user_id}", "Experience purchased by a reader")
            return {"experience_id": str(eid), "charged_coins": row.price_coins, "available_coins": reader.available}

    def vote(self, user_id, experience_id, value):
        if isinstance(value, bool) or str(value) not in {"-1", "0", "1"}:
            raise MarketplaceError("invalid_vote", "Choose upvote, downvote, or remove vote.")
        uid, eid = as_uuid(user_id), as_uuid(experience_id)
        with self.db.transaction() as session:
            row = session.get(Experience, eid, with_for_update=True)
            if not row or row.author_id == uid or not session.get(Entitlement, (uid, eid)):
                raise MarketplaceError("access_denied", "Only readers who unlocked this experience can vote.", 403)
            vote = session.get(Vote, (uid, eid))
            if int(value) == 0:
                if vote:
                    session.delete(vote)
            elif vote:
                vote.value = int(value)
            else:
                session.add(Vote(user_id=uid, experience_id=eid, value=int(value)))
            session.flush()
            return self._rating(session, row.author_id)

    @staticmethod
    def _draft(row):
        return {"draft_id": str(row.id), "id": str(row.id), "title": row.title, "teaser": row.teaser,
            "body": row.body, "taxonomy": row.taxonomy, "price_coins": row.price_coins, "status": row.status, "version": row.version}

    def save_draft(self, user_id, payload, draft_id=None):
        if any(key in payload for key in ("author_id", "status", "rewarded", "balance")):
            raise MarketplaceError("access_denied", "Ownership, approval and rewards are server decisions.", 403)
        fields = {name: payload.get(name, "") for name in ("title", "teaser", "body")}
        for key, limit in (("title", 180), ("teaser", 600), ("body", 100000)):
            if not isinstance(fields[key], str) or len(fields[key]) > limit:
                raise MarketplaceError("invalid_draft", "Check the story and public introduction lengths.")
        if not fields["body"].strip():
            raise MarketplaceError("invalid_draft", "Add your story before saving.")
        tags = payload.get("taxonomy", [])
        if not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or len(t) > 100 for t in tags):
            raise MarketplaceError("invalid_draft", "Use a list of short taxonomy topics.")
        price = amount(payload.get("price_coins"))
        with self.db.transaction() as session:
            if draft_id:
                row = session.get(Experience, as_uuid(draft_id), with_for_update=True)
                if not row or row.author_id != user_id:
                    raise MarketplaceError("access_denied", "This private draft belongs to another author.", 403)
                if row.status != "draft" or payload.get("version") != row.version:
                    raise MarketplaceError("version_conflict", "This revision is read-only or changed. Copy your text before reloading.", 409)
                row.version += 1
            else:
                row = Experience(author_id=user_id, version=1, status="draft")
                session.add(row)
            for key, value in fields.items():
                setattr(row, key, value)
            row.taxonomy, row.price_coins = list(dict.fromkeys(tags)), price
            session.flush()
            return self._draft(row)

    def draft(self, user_id, draft_id):
        with self.db.transaction() as session:
            row = session.get(Experience, as_uuid(draft_id))
            if not row or row.author_id != user_id:
                raise MarketplaceError("access_denied", "This private draft belongs to another author.", 403)
            return self._draft(row)

    def submit(self, user_id, draft_id, version):
        with self.db.transaction() as session:
            row = session.get(Experience, as_uuid(draft_id), with_for_update=True)
            if not row or row.author_id != user_id:
                raise MarketplaceError("access_denied", "This private draft belongs to another author.", 403)
            if row.status != "draft" or version != row.version:
                raise MarketplaceError("version_conflict", "This revision changed. Reload it before submitting.", 409)
            if not row.title.strip() or not row.teaser.strip() or not row.taxonomy:
                raise MarketplaceError("invalid_draft", "Add a title, teaser and topic before submitting.")
            row.status, row.version = "submitted", row.version+1
            return self._draft(row)

    def review(self, admin_id, experience_id, approve=True):
        with self.db.transaction() as session:
            self._admin(session, admin_id)
            row = session.get(Experience, as_uuid(experience_id), with_for_update=True)
            if not row:
                raise MarketplaceError("not_found", "Submission not found.", 404)
            if row.status == "approved" and approve:
                return {"status": "approved", "reward_coins": 0}
            if row.status != "submitted":
                raise MarketplaceError("invalid_state", "Only a submitted revision can be reviewed.", 409)
            if not approve:
                row.status = "rejected"
                return {"status": row.status, "reward_coins": 0}
            fingerprint = self.fingerprint(row.body)
            # Serialize rewards for this author before checking for another approved copy.
            wallets = self._wallets(session, TREASURY, row.author_id)
            duplicate = session.scalar(select(Experience.id).where(Experience.author_id == row.author_id,
                Experience.fingerprint == fingerprint, Experience.status == "approved", Experience.id != row.id))
            if duplicate:
                raise MarketplaceError("duplicate_experience", "This author already has an approved copy of this story.", 409)
            treasury, author = wallets[TREASURY], wallets[row.author_id]
            if treasury.available < 10:
                raise MarketplaceError("reward_budget_empty", "The demo reward budget is empty. Approval remains pending.", 409)
            treasury.available -= 10
            author.available += 10
            row.status, row.rewarded, row.fingerprint = "approved", True, fingerprint
            session.add(Reward(experience_id=row.id, author_id=row.author_id, fingerprint=fingerprint))
            self._entry(session, row.author_id, "publication_reward", 10, row.id, "First approved experience reward")
            self._entry(session, TREASURY, "reward_funding", -10, row.id, "Funded publication reward")
            return {"status": "approved", "reward_coins": 10}

    @staticmethod
    def _request(row):
        return {"id": str(row.id), "request_id": str(row.id), "user_id": str(row.user_id),
            "kind": row.kind, "coins": row.coins, "fiat_minor": row.coins, "currency": "USD", "status": row.status,
            "return_experience_id": str(row.return_experience_id) if row.return_experience_id else None,
            "query_id": row.query_id, "created_at": row.created_at}

    def request_funds(self, user_id, coins, kind, return_experience_id=None, query_id=None):
        coins, uid = amount(coins), as_uuid(user_id)
        with self.db.transaction() as session:
            wallets = self._wallets(session, uid)
            wallet = wallets[uid]
            if kind == "withdrawal":
                if coins < 100 or coins % 100 or coins > max(0, wallet.available-10)//100*100:
                    raise MarketplaceError("invalid_withdrawal", "Withdraw at least 100 coins, in multiples of 100, leaving 10 available.")
                wallet.available -= coins
                wallet.reserved += coins
            eid = as_uuid(return_experience_id) if return_experience_id else None
            if eid and not session.get(Experience, eid):
                raise MarketplaceError("not_found", "Return experience not found.", 404)
            row = MoneyRequest(user_id=uid, kind=kind, coins=coins,
                status="pending_payment" if kind == "recharge" else "pending_review", return_experience_id=eid, query_id=query_id)
            session.add(row)
            session.flush()
            if kind == "withdrawal":
                self._entry(session, uid, "withdrawal_reserved", -coins, row.id, "Coins reserved for a simulated payout")
            return self._request(row)

    def money_action(self, actor_id, request_id, action, admin=False):
        uid = as_uuid(actor_id)
        with self.db.transaction() as session:
            if admin:
                self._admin(session, uid)
            row = session.get(MoneyRequest, as_uuid(request_id), with_for_update=True)
            if not row or (not admin and row.user_id != uid):
                raise MarketplaceError("access_denied", "This request is unavailable.", 403)
            wallet = self._wallets(session, row.user_id)[row.user_id]
            if action == "submitted" and not admin and row.kind == "recharge" and row.status in {"pending_payment", "pending_review"}:
                row.status = "pending_review"
            elif action == "approve" and admin and row.kind == "recharge" and row.status in {"pending_review", "credited"}:
                if row.status != "credited":
                    wallet.available += row.coins
                    row.bank_reference = "DEMO-IN-"+str(row.id)
                    self._entry(session, row.user_id, "recharge", row.coins, row.id, "Verified simulated recharge")
                    row.status = "credited"
            elif action == "start" and admin and row.kind == "withdrawal" and row.status in {"pending_review", "processing"}:
                row.status = "processing"
            elif action == "settle" and admin and row.kind == "withdrawal" and row.status in {"processing", "settled"}:
                if row.status != "settled":
                    wallet.reserved -= row.coins
                    row.bank_reference = "DEMO-OUT-"+str(row.id)
                    self._entry(session, row.user_id, "withdrawal_settled", 0, row.id, "Simulated payout settled; reservation consumed")
                    row.status = "settled"
            elif action in {"reject", "cancel"} and (admin or action == "cancel") and row.status in {"pending_payment", "pending_review", "rejected", "cancelled"}:
                if row.status not in {"rejected", "cancelled"}:
                    if row.kind == "withdrawal":
                        wallet.reserved -= row.coins
                        wallet.available += row.coins
                        self._entry(session, row.user_id, "withdrawal_released", row.coins, row.id, "Simulated withdrawal reservation released")
                    row.status = "rejected" if admin else "cancelled"
            else:
                raise MarketplaceError("invalid_state", "This action is unavailable in the request's current state.", 409)
            return self._request(row)

    def request(self, actor_id, request_id, admin=False):
        with self.db.transaction() as session:
            row = session.get(MoneyRequest, as_uuid(request_id))
            if not row or (row.user_id != actor_id and not admin):
                raise MarketplaceError("access_denied", "This request belongs to another persona.", 403)
            result = self._request(row)
            result["owner_name"] = session.get(User, row.user_id).display_name
            return result

    def dashboard(self, user_id, admin=False):
        with self.db.transaction() as session:
            experiences = session.scalars(select(Experience).where(Experience.author_id == user_id).order_by(Experience.created_at.desc())).all()
            requests = session.scalars(select(MoneyRequest).where(MoneyRequest.user_id == user_id).order_by(MoneyRequest.created_at.desc())).all()
            logs = session.scalars(select(Ledger).where(Ledger.user_id == user_id).order_by(Ledger.created_at.desc()).limit(100)).all()
            result = {"experiences": [self._draft(e) for e in experiences], "requests": [self._request(r) for r in requests],
                "transactions": [{"kind": r.kind, "coins": r.coins, "created_at": r.created_at, "description": r.description} for r in logs]}
            if admin:
                self._admin(session, user_id)
                result["submissions"] = [{**self._draft(e), "author_name": session.get(User, e.author_id).display_name}
                    for e in session.scalars(select(Experience).where(Experience.status == "submitted"))]
                result["requests"] = [{**self._request(r), "owner_name": session.get(User, r.user_id).display_name}
                    for r in session.scalars(select(MoneyRequest).order_by(MoneyRequest.created_at.desc()))]
                result["treasury_coins"] = session.get(Wallet, TREASURY).available
            return result

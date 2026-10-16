import datetime
import os
import sqlite3
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_mail import Mail, Message

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "saariv-early-access-secret-key-2025")

# Mail Configuration
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME")
)

mail = Mail(app)
MAIL_TO = os.getenv("MAIL_TO", "mohit.rohatgi.mec10@gmail.com")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "waitlist.db")


def init_db():
    """Initialize SQLite database for early access signups."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS early_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT,
                profile_url TEXT,
                primary_bot TEXT,
                hourly_rate TEXT,
                use_case TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
            """
        )
        conn.commit()


init_db()


def mail_configured() -> bool:
    """Check if valid Gmail SMTP credentials are provided."""
    username = (app.config.get("MAIL_USERNAME") or "").strip()
    password = (app.config.get("MAIL_PASSWORD") or "").strip()
    if not username or not password:
        return False
    placeholders = {
        "your-16-char-app-password",
        "xxxx xxxx xxxx xxxx",
        "changeme",
        "change-me",
    }
    return password.lower() not in placeholders


def send_early_access_notification(data: dict) -> bool:
    """Send email notification to admin upon new early access application."""
    if not mail_configured():
        app.logger.warning("Mail credentials not configured. Skipping email dispatch.")
        return False

    subject = f"🚀 New Saariv Early Access Request: {data.get('name', 'Applicant')} ({data.get('role', 'Advisor')})"
    body = (
        f"A new professional has requested early access to Saariv!\n\n"
        f"----------------------------------------\n"
        f"Full Name:     {data.get('name')}\n"
        f"Email:         {data.get('email')}\n"
        f"Role / Niche:  {data.get('role') or '(not specified)'}\n"
        f"LinkedIn / URL:{data.get('profile_url') or '(not provided)'}\n"
        f"Primary Bot:   {data.get('primary_bot') or 'ChatGPT / Claude / Gemini'}\n"
        f"1:1 Rate:      {data.get('hourly_rate') or '(not specified)'}\n"
        f"Focus / Problem Solved:\n{data.get('use_case') or '(not provided)'}\n"
        f"Submitted At:  {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"----------------------------------------\n\n"
        f"Saariv Platform: Connect AI Chat History -> Monetizable Persona Link."
    )

    try:
        msg = Message(
            subject=subject,
            recipients=[MAIL_TO],
            body=body,
            reply_to=data.get("email"),
        )
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email notification: {e}")
        return False


@app.route("/", methods=["GET"])
def index():
    """Render Saariv Early Access Landing Page."""
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Docker & Northflank."""
    return jsonify(
        status="ok",
        app="saariv",
        version="1.0.0",
        mail_ready=mail_configured(),
    )


@app.route("/api/early-access", methods=["POST"])
@app.route("/waitlist", methods=["POST"])
@app.route("/message", methods=["POST"])
def submit_early_access():
    """Capture early access application from the form or JSON payload."""
    if request.is_json:
        payload = request.get_json() or {}
    else:
        payload = request.form.to_dict()

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    role = (payload.get("role") or "").strip()
    profile_url = (payload.get("profile_url") or "").strip()
    primary_bot = (payload.get("primary_bot") or "").strip()
    hourly_rate = (payload.get("hourly_rate") or "").strip()
    use_case = (payload.get("use_case") or payload.get("message") or "").strip()
    ip_addr = request.remote_addr or ""

    if not name or not email:
        return jsonify(
            ok=False,
            message="Please provide both your name and email address to apply for early access.",
        ), 400

    if "@" not in email or "." not in email:
        return jsonify(
            ok=False,
            message="Please enter a valid email address.",
        ), 400

    applicant_data = {
        "name": name,
        "email": email,
        "role": role,
        "profile_url": profile_url,
        "primary_bot": primary_bot,
        "hourly_rate": hourly_rate,
        "use_case": use_case,
    }

    # Save to SQLite database
    row_id = None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO early_access (name, email, role, profile_url, primary_bot, hourly_rate, use_case, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, email, role, profile_url, primary_bot, hourly_rate, use_case, ip_addr),
            )
            conn.commit()
            row_id = cursor.lastrowid
    except Exception as e:
        app.logger.error(f"Error persisting early access lead: {e}")

    # Dispatch email in background / inline
    email_sent = send_early_access_notification(applicant_data)

    base_count = 148  # Initial early access queue offset
    position = base_count + (row_id or 1)

    return jsonify(
        ok=True,
        message="You're on the early access list! We'll review your profile and send your persona creation invite shortly.",
        waitlist_number=position,
        name=name,
        email_sent=email_sent,
    )


@app.route("/api/waitlist-count", methods=["GET"])
def waitlist_count():
    """Return current waitlist count."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM early_access")
            count = cursor.fetchone()[0]
    except Exception:
        count = 0
    return jsonify(total_advisors=148 + count)


@app.route("/api/simulate-persona", methods=["POST"])
def simulate_persona():
    """Simulate an advisor's AI persona response for the interactive website demo."""
    data = request.get_json() or {}
    persona_id = data.get("persona_id", "elena")
    user_query = (data.get("query") or "").strip()

    # Pre-calibrated mock persona responses demonstrating the distilled knowledge & voice
    personas = {
        "elena": {
            "name": "Elena Rostova",
            "title": "B2B SaaS Growth Consultant",
            "hourly_rate": "$350/hr",
            "source": "1,420+ Claude & ChatGPT Chats ingested",
            "default_response": (
                "Based on the B2B GTM framework I developed through 50+ enterprise rollouts:\n\n"
                "1. **Audit your ACV vs Sales Cycle**: If your contract value is under $12k/yr, ditch outbound SDRs immediately. Transition to product-led onboarding with an automated reverse trial.\n"
                "2. **The 30-Day Churn Diagnostic**: Check week-2 feature adoption. 78% of churn happens because the customer never hit their 'first milestone value' before day 14.\n\n"
                "💡 *Would you like me to analyze your specific pricing tier and generate a customized retention playbook?*"
            ),
        },
        "david": {
            "name": "David Chen",
            "title": "Fractional CTO & Systems Architect",
            "hourly_rate": "$400/hr",
            "source": "2,150+ Gemini & ChatGPT Chats ingested",
            "default_response": (
                "Reviewing this against my distributed architecture principles:\n\n"
                "1. **Premature Microservices Trap**: If your engineering team is under 15 engineers, stay on a modular monolith. Splitting prematurely incurs a 40% network latency tax and massive DevOps overhead.\n"
                "2. **Database Bottlenecks**: Implement read-replicas and Redis caching on write-heavy endpoints before re-architecting your schemas.\n\n"
                "💡 *Want me to review your stack diagram or run an automated latency checklist for your application?*"
            ),
        },
        "marcus": {
            "name": "Marcus Vance",
            "title": "Seed-to-Series A Pitch & GTM Advisor",
            "hourly_rate": "$300/hr",
            "source": "980+ Grok & Claude Chats ingested",
            "default_response": (
                "Here is how tier-1 VCs will evaluate this slide deck:\n\n"
                "1. **The 'Why Now' Anchor**: Never start with TAM slides. Start with the tectonic regulatory or AI shift that makes your solution viable today when it wasn't 18 months ago.\n"
                "2. **Pipeline Velocity**: Show Cohort Net Revenue Retention (NRR). An NRR above 125% beats a flat 20% MoM top-line growth every single time.\n\n"
                "💡 *Upload your deck outline or tell me your current ARR and I'll simulate a 5-question partner meeting interrogation.*"
            ),
        },
    }

    selected = personas.get(persona_id, personas["elena"])

    # If the user typed a specific question, customize the reply
    if user_query:
        reply = (
            f"Regarding: *\"{user_query}\"*\n\n"
            f"Here is how I approach this in my 1-on-1 advisory sessions:\n\n"
            f"• **Core Principle**: Avoid tackling the symptom. Focus on the root constraint where 20% of the friction generates 80% of client hesitation.\n"
            f"• **Actionable Blueprint**: 1) Document your current baseline metrics, 2) Test an asymmetric pilot with 3 pilot clients, 3) Institutionalize the winning playbook.\n\n"
            f"⚡ *This insight was generated from {selected['name']}'s personalized Saariv model. Ready for a tailored deep-dive session?*"
        )
    else:
        reply = selected["default_response"]

    return jsonify(
        name=selected["name"],
        title=selected["title"],
        hourly_rate=selected["hourly_rate"],
        source=selected["source"],
        reply=reply,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(debug=True, host="0.0.0.0", port=port)

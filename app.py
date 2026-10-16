import datetime
import os
import sqlite3

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_mail import Mail, Message

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "saariv-waitlist-secret-key-2025")

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
    """Initialize SQLite database for waitlist signups."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                profile_type TEXT,
                profile_url TEXT,
                primary_bot TEXT,
                story_focus TEXT,
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


def send_waitlist_notification(data: dict) -> bool:
    """Send email notification to admin upon new waitlist signup."""
    if not mail_configured():
        app.logger.warning("Mail credentials not configured. Skipping email dispatch.")
        return False

    subject = f"✨ New Saariv Waitlist Signup: {data.get('name', 'Applicant')} ({data.get('profile_type', 'Creator')})"
    body = (
        f"A new creator has joined the Saariv waitlist!\n\n"
        f"----------------------------------------\n"
        f"Full Name:     {data.get('name')}\n"
        f"Email:         {data.get('email')}\n"
        f"Category:      {data.get('profile_type') or '(not specified)'}\n"
        f"Profile / URL: {data.get('profile_url') or '(not provided)'}\n"
        f"Chatbot(s):    {data.get('primary_bot') or 'ChatGPT / Grok / Gemini / Claude'}\n"
        f"Story / Lived Experience:\n{data.get('story_focus') or '(not provided)'}\n"
        f"Submitted At:  {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"----------------------------------------\n\n"
        f"Saariv: AI Avatars from Lived Experiences & Chat History"
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
    """Render Saariv Waitlist & Interactive Playground."""
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Docker & Northflank."""
    return jsonify(
        status="ok",
        app="saariv",
        version="1.1.0",
        mail_ready=mail_configured(),
    )


@app.route("/api/waitlist", methods=["POST"])
@app.route("/api/early-access", methods=["POST"])
@app.route("/waitlist", methods=["POST"])
def submit_waitlist():
    """Capture waitlist application from form or JSON."""
    if request.is_json:
        payload = request.get_json() or {}
    else:
        payload = request.form.to_dict()

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    profile_type = (payload.get("profile_type") or payload.get("role") or "").strip()
    profile_url = (payload.get("profile_url") or "").strip()
    primary_bot = (payload.get("primary_bot") or "").strip()
    story_focus = (payload.get("story_focus") or payload.get("use_case") or payload.get("message") or "").strip()
    ip_addr = request.remote_addr or ""

    if not name or not email:
        return jsonify(
            ok=False,
            message="Please provide both your name and email address to join the waitlist.",
        ), 400

    if "@" not in email or "." not in email:
        return jsonify(
            ok=False,
            message="Please enter a valid email address.",
        ), 400

    applicant_data = {
        "name": name,
        "email": email,
        "profile_type": profile_type,
        "profile_url": profile_url,
        "primary_bot": primary_bot,
        "story_focus": story_focus,
    }

    # Save to SQLite database
    row_id = None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO waitlist (name, email, profile_type, profile_url, primary_bot, story_focus, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, email, profile_type, profile_url, primary_bot, story_focus, ip_addr),
            )
            conn.commit()
            row_id = cursor.lastrowid
    except Exception as e:
        app.logger.error(f"Error persisting waitlist entry: {e}")

    # Dispatch email
    email_sent = send_waitlist_notification(applicant_data)

    base_count = 340  # Realistic waitlist offset
    position = base_count + (row_id or 1)

    return jsonify(
        ok=True,
        message="You are on the waitlist! We will notify you as soon as your batch is unlocked.",
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
            cursor.execute("SELECT COUNT(*) FROM waitlist")
            count = cursor.fetchone()[0]
    except Exception:
        count = 0
    return jsonify(total_creators=340 + count)


@app.route("/api/simulate-persona", methods=["POST"])
def simulate_persona():
    """Simulate avatar responses in the Saariv Playground."""
    data = request.get_json() or {}
    avatar_id = data.get("persona_id", "aarav")
    user_query = (data.get("query") or "").strip()

    # Pre-calibrated avatars representing Founders, Migrants (out of India), and Consultants
    avatars = {
        "aarav": {
            "name": "Aarav Sharma",
            "tagline": "Migrated from Pune to Amsterdam • Senior Tech Lead",
            "category": "Global Expat & Migration Story",
            "fee_per_q": "$8.00 / question",
            "chats_source": "Synthesized from 1,120 ChatGPT & Claude chats on EU Blue Card, housing & salary negotiations",
            "default_response": (
                "Here is my direct experience relocating from Pune to Amsterdam on an EU Blue Card:\n\n"
                "1. **Job Hunting Strategy**: Skip LinkedIn 'Easy Apply'. Target Dutch companies registered with IND as Recognized Sponsors. Highlight your distributed system ownership—European engineering managers care deeply about async communication and unit test discipline.\n\n"
                "2. **The 30% Ruling Reality**: Apply immediately upon signing the contract. It increases your net take-home by ~25%, which is critical because Amsterdam rental deposits often require 2 months upfront plus guarantor proof.\n\n"
                "3. **What I wish I knew earlier**: Don't rent inside the canal ring initially. Look at Haarlem, Utrecht, or Amstelveen—commutes on the NS train are 18 minutes and you save €600/month."
            ),
        },
        "pooja": {
            "name": "Pooja Mehra",
            "tagline": "D2C Founder • Scaled Organic Wellness from 0 to ₹8 Cr ARR",
            "category": "Founder Journey & Living Biography",
            "fee_per_q": "$12.00 / question",
            "chats_source": "Synthesized from 840 Gemini & ChatGPT chats on vendor negotiations, CAC hurdles & angel rounds",
            "default_response": (
                "From our journey bootstrapping from a Delhi apartment to ₹8 Cr ARR:\n\n"
                "1. **Our Worst Manufacturing Mistake**: In year 1, we ordered ₹15L of custom glass packaging from a single vendor with zero SLA penalties. When 40% cracked during monsoon transit, our margins collapsed. Always split batch manufacturing 60/40 across two independent suppliers.\n\n"
                "2. **Meta CAC Survival**: When our Blended CAC spiked from ₹220 to ₹580 post-iOS14, we stopped running broad video ads. We built a WhatsApp replenishment engine for 60-day reorders. Repeat purchase rate went from 14% to 38%.\n\n"
                "3. **Angel Pitch Reality**: Indian angel syndicates care about gross margin after courier COD returns. If your RTO (Return to Origin) is above 18%, fix logistics before pitching."
            ),
        },
        "kabir": {
            "name": "Dr. Kabir Sen",
            "tagline": "Healthcare Digital Transformation Consultant • Ex-NHS Advisor",
            "category": "Independent Specialist Consultant",
            "fee_per_q": "$25.00 / consultation",
            "chats_source": "Synthesized from 1,600 Claude & Grok chats on clinical workflow compliance & HL7/FHIR integration",
            "default_response": (
                "My advisory framework for hospitals digitizing patient intake:\n\n"
                "1. **The Clinician Adoption Hurdle**: Never impose digital documentation that adds more than 3 clicks per patient chart. Doctors will simply create paper workarounds.\n\n"
                "2. **FHIR Interoperability Pitfall**: Legacy EHR systems charge extortionate API integration fees. Require vendors to sign open standard compliance before signing multi-year licenses.\n\n"
                "3. **Risk Containment**: Conduct a 30-day shadow pilot in one ambulatory ward before rolling out hospital-wide."
            ),
        },
    }

    selected = avatars.get(avatar_id, avatars["aarav"])

    if user_query:
        reply = (
            f"Answering your question based on my real journey (*\"{user_query}\"*):\n\n"
            f"• **Direct Takeaway**: In my own experience navigating this exact situation, the biggest trap was overcomplicating the first move. Focus on the core bottleneck first.\n"
            f"• **How I Handled It**: I documented baseline numbers, reached out directly to 3 peers who had done it 12 months before me, and negotiated terms before committing capital or moving cities.\n\n"
            f"💡 *This response was generated from {selected['name']}'s personal AI avatar. In the live version, users pay {selected['fee_per_q']} to ask deeper questions, deposited directly to {selected['name']}.*"
        )
    else:
        reply = selected["default_response"]

    return jsonify(
        name=selected["name"],
        tagline=selected["tagline"],
        category=selected["category"],
        fee_per_q=selected["fee_per_q"],
        chats_source=selected["chats_source"],
        reply=reply,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(debug=True, host="0.0.0.0", port=port)

import datetime
import json
import os
import re
import sqlite3
from typing import Any, Dict, List

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from flask_mail import Mail, Message

from knowledge.answers import answer_from_sources
from knowledge.onboarding import export_sources, import_additional, import_story
from knowledge.web import get_service, initialize_knowledge

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "saariv-stepper-rag-secret-2025")

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
def get_openai_api_key() -> str:
    """Read OpenAI API key from environment."""
    return os.getenv("OPENAI_API_KEY", "").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "waitlist.db")
TMP_DIR = os.path.join(BASE_DIR, "tmp_profiles")
QUESTIONS_LOG_PATH = os.path.join(BASE_DIR, "tmp", "user_questions.jsonl")
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(QUESTIONS_LOG_PATH), exist_ok=True)

initialize_knowledge(app)


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


def log_user_question(session_id: str, question: str, retrieved_topic: str = ""):
    """Log user question to a JSONL file with automatic cleanup of old entries."""
    try:
        # Create log entry
        log_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "session_id": session_id,
            "question": question,
            "retrieved_topic": retrieved_topic
        }
        
        # Append to JSONL file (one JSON object per line)
        with open(QUESTIONS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        # Clean up old entries (older than 1 week)
        cleanup_old_questions()
        
    except Exception as e:
        app.logger.warning(f"Failed to log user question: {e}")


def cleanup_old_questions():
    """Remove questions older than 1 week from the log file."""
    if not os.path.exists(QUESTIONS_LOG_PATH):
        return
    
    try:
        # Read all questions
        with open(QUESTIONS_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            return
        
        # Filter out questions older than 1 week
        one_week_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        recent_lines = []
        
        for line in lines:
            try:
                entry = json.loads(line.strip())
                timestamp_str = entry.get("timestamp", "")
                if timestamp_str:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if timestamp >= one_week_ago:
                        recent_lines.append(line)
            except Exception:
                # Keep malformed entries to avoid data loss
                recent_lines.append(line)
        
        # Write back only recent questions
        with open(QUESTIONS_LOG_PATH, "w", encoding="utf-8") as f:
            f.writelines(recent_lines)
            
    except Exception as e:
        app.logger.warning(f"Failed to cleanup old questions: {e}")


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

    subject = f"✨ New Saariv Living Biography Creator: {data.get('name', 'Applicant')} ({data.get('profile_type', 'Creator')})"
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
        f"Saariv: Living Biographies & AI Avatars from Lived Experiences."
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


# ==========================================
# RAG (Retrieval-Augmented Generation) Core
# ==========================================

def experiences_from_story(story: str, selected_items: Dict[str, Any]) -> Dict[str, Any]:
    """Keep narrative text intact and use optional headings for retrieval sections."""
    selected_topics = selected_items.get("topics", [])
    title = selected_topics[0] if len(selected_topics) == 1 else "Experience Story"
    topics = []
    body = []
    fence = ""

    def save_section():
        text = "\n".join(body).strip()
        if text:
            topics.append({
                "topic": title,
                "experience": text,
                "unique_angle": "",
                "period": "unknown",
                "subtopics": [],
            })
        body.clear()

    for line in story.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            body.append(line)
            continue
        heading = None if fence else re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            save_section()
            title = heading.group(1)
        else:
            body.append(line)
    save_section()

    return {"domains": [{
        "domain": "Experience Stories",
        "subdomains": [{"subdomain": "Selected Topics", "topics": topics}],
    }]}


def index_experiences_from_json(exp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and index atomic experience chunks for search."""
    chunks = []
    domains = exp_data.get("domains", [])
    for d in domains:
        domain_name = d.get("domain", "General")
        for sd in d.get("subdomains", []):
            subdomain_name = sd.get("subdomain", "General")
            for t in sd.get("topics", []):
                topic_name = t.get("topic", "")
                exp_text = t.get("experience", "")
                unique_angle = t.get("unique_angle", "")
                period = t.get("period", "unknown")
                subtopics = t.get("subtopics", [])
                
                # Combine all text for robust retrieval
                subtopic_text = " ".join([
                    f"{st.get('subtopic', '')}: {st.get('experience', '')}"
                    for st in subtopics if isinstance(st, dict)
                ])

                full_searchable = f"{domain_name} {subdomain_name} {topic_name} {exp_text} {unique_angle} {subtopic_text}".lower()

                chunks.append({
                    "id": f"{domain_name}::{subdomain_name}::{topic_name}",
                    "domain": domain_name,
                    "subdomain": subdomain_name,
                    "topic": topic_name,
                    "experience": exp_text,
                    "unique_angle": unique_angle,
                    "period": period,
                    "subtopics": subtopics,
                    "searchable_text": full_searchable,
                })
    return chunks


def retrieve_relevant_experience(query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compatibility helper for old exports; the app queries the knowledge service."""
    tokens = set(re.findall(r"\w+", query.lower()))
    ranked = sorted(((sum(token in chunk["searchable_text"] for token in tokens), chunk)
                     for chunk in chunks), key=lambda pair: pair[0], reverse=True)
    return [chunk for score, chunk in ranked if score > 0][:2]


@app.route("/", methods=["GET"])
def index():
    """Render Saariv Living Biography Landing Page."""
    return render_template("index.html")


@app.route("/try", methods=["GET"])
def try_saariv():
    """Render the dedicated Try Saariv Onboarding & Playground page."""
    return render_template("try.html")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Docker & Northflank."""
    return jsonify(
        status="ok",
        app="saariv",
        version="1.2.0",
        mail_ready=mail_configured(),
        openai_configured=bool(get_openai_api_key()),
        rag_ready=True,
        embeddings_configured=bool(get_service().provider),
        embedding_provider=get_service().settings.embedding_provider,
    )


@app.route("/api/onboarding/step1", methods=["POST"])
def onboarding_step1():
    """Save Step 1 basic details to tmp_profiles folder."""
    data = request.get_json() or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    linkedin_url = (data.get("linkedin_url") or "").strip()

    if not first_name or not email:
        return jsonify(ok=False, message="Please provide your First Name and Email Address."), 400

    session_id = g.knowledge_owner
    user_folder = os.path.join(TMP_DIR, session_id)
    os.makedirs(user_folder, exist_ok=True)

    profile_payload = {
        "session_id": session_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "linkedin_url": linkedin_url,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    with open(os.path.join(user_folder, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile_payload, f, indent=2)

    # Send notification email about new trial user (silently, don't affect response)
    if mail_configured():
        try:
            subject = f"🎯 New Saariv Trial: {first_name} {last_name}"
            body = (
                f"Someone just tried Saariv!\n\n"
                f"----------------------------------------\n"
                f"Name:   {first_name} {last_name}\n"
                f"Email:  {email}\n"
                f"LinkedIn: {linkedin_url or '(not provided)'}\n"
                f"Time:   {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Session ID: {session_id}\n"
                f"----------------------------------------\n"
            )
            msg = Message(
                subject=subject,
                recipients=[MAIL_TO],
                body=body,
            )
            mail.send(msg)
        except Exception as e:
            app.logger.warning(f"Failed to send trial notification email: {e}")

    return jsonify(ok=True, session_id=session_id, profile=profile_payload)


@app.route("/api/onboarding/step2", methods=["POST"])
def onboarding_step2():
    """Receive and parse Prompt 1 taxonomy output."""
    data = request.get_json() or {}
    session_id = g.knowledge_owner
    taxonomy_raw = data.get("taxonomy_json")

    user_folder = os.path.join(TMP_DIR, session_id)
    os.makedirs(user_folder, exist_ok=True)

    if isinstance(taxonomy_raw, str):
        try:
            taxonomy_obj = json.loads(taxonomy_raw)
        except Exception as e:
            return jsonify(ok=False, message=f"Invalid JSON provided. Please ensure your chatbot output is valid JSON ({e})."), 400
    elif isinstance(taxonomy_raw, dict):
        taxonomy_obj = taxonomy_raw
    else:
        return jsonify(ok=False, message="Please paste the JSON output from your chatbot."), 400

    with open(os.path.join(user_folder, "taxonomy.json"), "w", encoding="utf-8") as f:
        json.dump(taxonomy_obj, f, indent=2)

    # Extract clean list of topics with hierarchy
    domains = taxonomy_obj.get("domains", [])
    extracted_topics = []
    for d in domains:
        domain_name = d.get("domain", "")
        for sd in d.get("subdomains", []):
            subdomain_name = sd.get("subdomain", "")
            for t in sd.get("topics", []):
                extracted_topics.append({
                    "domain": domain_name,
                    "subdomain": subdomain_name,
                    "topic": t.get("topic", ""),
                    "evidence": t.get("evidence", ""),
                    "period": t.get("period", ""),
                    "subtopics": t.get("subtopics", [])
                })

    return jsonify(
        ok=True,
        session_id=session_id,
        total_topics=len(extracted_topics),
        topics=extracted_topics,
        raw_domains=domains
    )


@app.route("/api/onboarding/step4", methods=["POST"])
def onboarding_step4():
    """Persist and index the narrative, retaining legacy JSON import support."""
    try:
        return jsonify(import_story(request.get_json(), TMP_DIR, experiences_from_story, index_experiences_from_json))
    except Exception as e:
        error_msg = str(e)
        # Handle reindex requirement gracefully
        if "Reindex" in error_msg or "Embedding configuration changed" in error_msg:
            from knowledge.service import ReindexRequired
            # Force reindex and try again
            owner = g.knowledge_owner
            try:
                get_service().reindex(owner)
                return jsonify(import_story(request.get_json(), TMP_DIR, experiences_from_story, index_experiences_from_json))
            except Exception as retry_error:
                return jsonify(ok=False, message=f"Failed to reindex: {retry_error}"), 500
        return jsonify(ok=False, message=error_msg), 500


def cleanup_old_sessions():
    """Knowledge and profiles persist until explicitly deleted."""
    return 0


@app.route("/api/onboarding/step5", methods=["POST"])
def onboarding_step5():
    return jsonify(import_additional(request.get_json(), TMP_DIR, experiences_from_story, index_experiences_from_json))


@app.route("/api/onboarding/step5-files", methods=["POST"])
def onboarding_step5_files():
    return jsonify(import_additional(request.form, TMP_DIR, experiences_from_story, index_experiences_from_json, files=True))


@app.route("/api/reindex", methods=["POST"])
def reindex_knowledge():
    """Reindex all documents with current embedding configuration."""
    owner = g.knowledge_owner
    try:
        result = get_service().reindex(owner)
        return jsonify(ok=True, message="Reindex completed successfully", **result)
    except Exception as e:
        return jsonify(ok=False, message=f"Reindex failed: {e}"), 500


@app.route("/api/playground/rag-query", methods=["POST"])
def playground_rag_query():
    """Retrieve source evidence through the same service exposed to external agents."""
    data = request.get_json()
    owner = g.knowledge_owner
    query = data.get("query", "")
    retrieved = get_service().search(owner, query, limit=5)
    profile_path = os.path.join(TMP_DIR, owner, "profile.json")
    profile = {}
    if os.path.exists(profile_path):
        try:
            with open(profile_path, encoding="utf-8") as stream:
                profile = json.load(stream)
        except (ValueError, OSError):
            pass
    answer = answer_from_sources(query, retrieved["results"], profile)
    # When the answer is "insufficient", the retrieved chunks did not actually answer
    # the question, so no experience story should be shown alongside that reply.
    sources = [] if answer.get("answer_mode") == "insufficient" else retrieved["results"]
    topic = sources[0]["source"]["section"] if sources else ""
    log_user_question(owner, query, topic)
    return jsonify(ok=True, **answer, sources=sources,
                   retrieval_mode=retrieved["mode"], retrieval_timings_ms=retrieved["timings_ms"],
                   warnings=retrieved["warnings"], retrieved_topic=topic, unique_angle="",
                   chunks_found=len(sources),
                   avatar_name=" ".join(str(profile.get(key, "")) for key in ("first_name", "last_name")).strip() or "Your Avatar")


app.config["KNOWLEDGE_EXPORTER"] = lambda owner: export_sources(
    owner, TMP_DIR, experiences_from_story, index_experiences_from_json)


@app.route("/api/waitlist", methods=["POST"])
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

    email_sent = send_waitlist_notification(applicant_data)

    base_count = 340
    position = base_count + (row_id or 1)

    return jsonify(
        ok=True,
        message="You are on the waitlist! We will notify you as soon as your batch is unlocked.",
        waitlist_number=position,
        name=name,
        email_sent=email_sent,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(debug=True, host="0.0.0.0", port=port)

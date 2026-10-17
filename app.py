import datetime
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_mail import Mail, Message

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
    """RAG retrieval: Rank chunks by relevance to query."""
    if not chunks:
        return []

    # Clean query tokens
    stop_words = {"what", "how", "why", "when", "did", "you", "your", "my", "is", "are", "about", "the", "a", "an", "in", "on", "for", "with", "to", "and", "tell", "me"}
    tokens = [w for w in re.findall(r'\b[a-zA-Z0-9_\-]+\b', query.lower()) if w not in stop_words]

    if not tokens:
        tokens = query.lower().split()

    scored = []
    for chunk in chunks:
        score = 0
        topic_lower = chunk["topic"].lower()
        search_text = chunk["searchable_text"]

        # Exact phrase or topic title matches get high priority
        if query.lower() in search_text:
            score += 15
        if any(token in topic_lower for token in tokens):
            score += 10

        # Token matching
        for token in tokens:
            if token in topic_lower:
                score += 5
            if token in search_text:
                score += 2

        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Return top 2 matching chunks
    top_matches = [item[1] for item in scored if item[0] > 0]
    if not top_matches and chunks:
        # Fallback to first chunk if no strong match
        top_matches = [chunks[0]]
    return top_matches[:2]


def generate_rag_answer(query: str, retrieved_chunks: List[Dict[str, Any]], profile: Dict[str, Any]) -> str:
    """Generate answer grounded strictly in retrieved experience."""
    if not retrieved_chunks:
        return "I haven't documented specific lived experience on that exact topic in my chatbot archives yet. Ask me about the topics I have lived experience in!"

    creator_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or "Creator"
    primary_chunk = retrieved_chunks[0]

    api_key = get_openai_api_key()
    is_real_openai_key = (
        api_key
        and not api_key.startswith("mock-")
        and len(api_key) > 20
    )

    if is_real_openai_key:
        try:
            # Call OpenAI Chat Completion
            context_str = "\n\n".join([
                f"Topic: {c['topic']}\nPeriod: {c['period']}\nExperience: {c['experience']}\nUnique Angle: {c['unique_angle']}"
                for c in retrieved_chunks
            ])
            system_prompt = (
                f"You are the verified personal AI Avatar and Living Biography of {creator_name}. "
                f"Answer the user's question directly in first-person ('I did...', 'In my experience...'). "
                f"Ground your answer STRICTLY in the following lived experience. Do not invent details not present in the context:\n\n"
                f"{context_str}"
            )

            req_data = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.4
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                return res_body["choices"][0]["message"]["content"]
        except Exception as e:
            app.logger.warning(f"OpenAI API call failed ({e}). Falling back to internal RAG synthesizer.")

    # High-fidelity Grounded Internal Synthesizer (Works 100% offline & with mock keys)
    topic = primary_chunk.get("topic", "")
    exp = primary_chunk.get("experience", "")
    angle = primary_chunk.get("unique_angle", "")
    subtopics = primary_chunk.get("subtopics", [])
    period = primary_chunk.get("period", "my career")

    subtopic_points = ""
    if subtopics:
        subtopic_points = "\n\nSpecific decisions and sub-experiences:\n" + "\n".join([
            f"• **{st.get('subtopic', '')}**: {st.get('experience', '')}"
            for st in subtopics[:3] if isinstance(st, dict)
        ])

    answer = (
        f"Based on my personal experience with **{topic}** (around {period}):\n\n"
        f"{exp}\n\n"
        f"💡 **What made this distinct**: {angle}"
        f"{subtopic_points}\n\n"
        f"*(Answered by {creator_name}'s Living Biography Avatar • Retrieved from private chat history)*"
    )
    return answer


# ==========================================
# Routes
# ==========================================

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

    session_id = data.get("session_id") or uuid.uuid4().hex[:12]
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
    session_id = data.get("session_id", "demo-session")
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
    """Receive and save Prompt 2 unique experiences JSON, then index for RAG."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "demo-session")
    experiences_raw = data.get("experiences_json")
    selected_items = data.get("selected_items", {})
    
    # Support both old format (selected_topics) and new format (selected_items)
    if not selected_items:
        # Backward compatibility: convert old selected_topics to new format
        selected_topics = data.get("selected_topics", [])
        selected_items = {
            "domains": [],
            "subdomains": [],
            "topics": selected_topics,
            "subtopics": []
        }

    user_folder = os.path.join(TMP_DIR, session_id)
    os.makedirs(user_folder, exist_ok=True)

    if isinstance(experiences_raw, str):
        try:
            experiences_obj = json.loads(experiences_raw)
        except Exception as e:
            return jsonify(ok=False, message=f"Invalid JSON provided for experiences ({e})."), 400
    elif isinstance(experiences_raw, dict):
        experiences_obj = experiences_raw
    else:
        return jsonify(ok=False, message="Please paste the JSON experience output from your chatbot."), 400

    # Save to tmp storage
    with open(os.path.join(user_folder, "experiences.json"), "w", encoding="utf-8") as f:
        json.dump(experiences_obj, f, indent=2)

    with open(os.path.join(user_folder, "selected_items.json"), "w", encoding="utf-8") as f:
        json.dump(selected_items, f, indent=2)

    # Index chunks
    chunks = index_experiences_from_json(experiences_obj)
    with open(os.path.join(user_folder, "chunks_index.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    return jsonify(
        ok=True,
        session_id=session_id,
        indexed_count=len(chunks),
        sample_topics=[c["topic"] for c in chunks[:5]]
    )


def cleanup_old_sessions():
    """Delete session folders created before today."""
    today = datetime.datetime.now(datetime.timezone.utc).date()
    deleted_count = 0
    
    if not os.path.exists(TMP_DIR):
        return deleted_count
    
    for session_name in os.listdir(TMP_DIR):
        session_path = os.path.join(TMP_DIR, session_name)
        if not os.path.isdir(session_path):
            continue
        
        try:
            # Check the profile.json creation date
            profile_file = os.path.join(session_path, "profile.json")
            if os.path.exists(profile_file):
                with open(profile_file, "r", encoding="utf-8") as f:
                    profile_data = json.load(f)
                    created_at_str = profile_data.get("created_at", "")
                    if created_at_str:
                        created_at = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        created_date = created_at.date()
                        if created_date < today:
                            # Delete the entire session folder
                            import shutil
                            shutil.rmtree(session_path)
                            deleted_count += 1
        except Exception as e:
            app.logger.warning(f"Error checking session {session_name}: {e}")
            continue
    
    return deleted_count


@app.route("/api/onboarding/step5", methods=["POST"])
def onboarding_step5():
    """Add unique experience via text or file upload."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "demo-session")
    custom_experience = data.get("custom_experience", "")
    topic_tag = data.get("topic_tag", "Unique Experience")

    if not custom_experience:
        return jsonify(ok=True, message="No unique experience provided, continuing to playground.")

    # Clean up old sessions before adding new data
    deleted_count = cleanup_old_sessions()
    app.logger.info(f"Cleaned up {deleted_count} old session(s)")

    user_folder = os.path.join(TMP_DIR, session_id)
    os.makedirs(user_folder, exist_ok=True)

    # Load existing experiences
    exp_file = os.path.join(user_folder, "experiences.json")
    if os.path.exists(exp_file):
        try:
            with open(exp_file, "r", encoding="utf-8") as f:
                exp_data = json.load(f)
        except Exception:
            exp_data = {"domains": []}
    else:
        exp_data = {"domains": []}

    # Add unique experience as a new domain/topic
    custom_domain = {
        "domain": "Unique Experiences",
        "subdomains": [
            {
                "subdomain": topic_tag,
                "topics": [
                    {
                        "topic": topic_tag,
                        "experience": custom_experience,
                        "unique_angle": "Manually added by user",
                        "period": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m"),
                        "confidence": "high",
                        "subtopics": []
                    }
                ]
            }
        ]
    }

    # Check if Unique Experiences domain already exists
    found = False
    for domain in exp_data.get("domains", []):
        if domain.get("domain") == "Unique Experiences":
            # Add to existing domain
            domain["subdomains"].append(custom_domain["subdomains"][0])
            found = True
            break
    
    if not found:
        exp_data["domains"].append(custom_domain)

    # Save updated experiences
    with open(exp_file, "w", encoding="utf-8") as f:
        json.dump(exp_data, f, indent=2)

    # Re-index chunks
    chunks = index_experiences_from_json(exp_data)
    with open(os.path.join(user_folder, "chunks_index.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    return jsonify(
        ok=True,
        session_id=session_id,
        message="Unique experience added successfully.",
        indexed_count=len(chunks)
    )


def extract_text_from_docx(file_path: str) -> str:
    """Extract text content from a DOCX file."""
    try:
        from docx import Document
        doc = Document(file_path)
        text_parts = []
        for para in doc.paragraphs:
            text_parts.append(para.text)
        return "\n".join(text_parts)
    except Exception as e:
        app.logger.warning(f"Failed to extract DOCX text: {e}")
        return ""


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception as e:
        app.logger.warning(f"Failed to extract PDF text: {e}")
        return ""


@app.route("/api/onboarding/step5-files", methods=["POST"])
def onboarding_step5_files():
    """Handle file uploads for unique experiences (DOCX, PDF, etc.)."""
    session_id = request.form.get("session_id", "demo-session")
    topic_tag = request.form.get("topic_tag", "Unique Experience")
    custom_text = request.form.get("custom_experience", "")

    # Clean up old sessions
    cleanup_old_sessions()

    user_folder = os.path.join(TMP_DIR, session_id)
    os.makedirs(user_folder, exist_ok=True)

    # Process uploaded files
    all_text = custom_text
    uploaded_files = request.files.getlist("files")
    
    for file in uploaded_files:
        if not file.filename:
            continue
        
        # Save temporarily to extract text
        temp_path = os.path.join(user_folder, f"temp_{file.filename}")
        file.save(temp_path)
        
        ext = file.filename.split('.')[-1].lower()
        extracted = ""
        
        if ext == "docx" or ext == "doc":
            extracted = extract_text_from_docx(temp_path)
        elif ext == "pdf":
            extracted = extract_text_from_pdf(temp_path)
        else:
            # Try to read as text
            try:
                with open(temp_path, "r", encoding="utf-8") as f:
                    extracted = f.read()
            except Exception:
                pass
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except Exception:
            pass
        
        if extracted:
            all_text += f"\n\n--- Content from {file.filename} ---\n{extracted}"

    if not all_text.strip():
        return jsonify(ok=True, message="No content extracted from files.")

    # Load existing experiences
    exp_file = os.path.join(user_folder, "experiences.json")
    if os.path.exists(exp_file):
        try:
            with open(exp_file, "r", encoding="utf-8") as f:
                exp_data = json.load(f)
        except Exception:
            exp_data = {"domains": []}
    else:
        exp_data = {"domains": []}

    # Add unique experience
    custom_domain = {
        "domain": "Unique Experiences",
        "subdomains": [
            {
                "subdomain": topic_tag,
                "topics": [
                    {
                        "topic": topic_tag,
                        "experience": all_text,
                        "unique_angle": "Uploaded from files",
                        "period": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m"),
                        "confidence": "high",
                        "subtopics": []
                    }
                ]
            }
        ]
    }

    # Check if Unique Experiences domain already exists
    found = False
    for domain in exp_data.get("domains", []):
        if domain.get("domain") == "Unique Experiences":
            domain["subdomains"].append(custom_domain["subdomains"][0])
            found = True
            break
    
    if not found:
        exp_data["domains"].append(custom_domain)

    # Save and index
    with open(exp_file, "w", encoding="utf-8") as f:
        json.dump(exp_data, f, indent=2)

    chunks = index_experiences_from_json(exp_data)
    with open(os.path.join(user_folder, "chunks_index.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    return jsonify(
        ok=True,
        session_id=session_id,
        message="Files processed successfully.",
        indexed_count=len(chunks)
    )


@app.route("/api/playground/rag-query", methods=["POST"])
def playground_rag_query():
    """Query the user's RAG avatar using experiences saved in tmp_profiles folder."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "demo-session")
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify(ok=False, message="Please enter a question to ask the avatar."), 400

    user_folder = os.path.join(TMP_DIR, session_id)
    exp_file = os.path.join(user_folder, "experiences.json")
    profile_file = os.path.join(user_folder, "profile.json")

    # If no custom session file exists yet, load default sample experiences
    if not os.path.exists(exp_file):
        profile = {"first_name": "Aarav", "last_name": "Sharma"}
        sample_data = {
            "domains": [
                {
                    "domain": "Global Career & Tech Leadership",
                    "subdomains": [
                        {
                            "subdomain": "EU Relocation & Systems",
                            "topics": [
                                {
                                  "topic": "Google L5 Software Engineer Interview Loop",
                                  "experience": "You prepared extensively for distributed systems and system design interviews, focusing on Google-specific L5 rubric evaluation. You navigated 5 interview rounds with an emphasis on trade-off clarity and asynchronous consensus.",
                                  "unique_angle": "Focus on distributed consensus tradeoffs and real-world failure domain handling rather than theoretical algorithm memorization.",
                                  "period": "2023-08",
                                  "subtopics": [
                                      {"subtopic": "System Design", "experience": "Engineered multi-region failover architecture for cloud services."}
                                  ]
                                },
                                {
                                  "topic": "Saariv Development & Strategy",
                                  "experience": "You conceptualized Saariv to allow professionals, immigrants, and founders to monetize their chat history without giving up calendar hours. You designed the 2-prompt extraction workflow to distill knowledge safely.",
                                  "unique_angle": "Architected zero-upfront commission model with persistent RAG retrieval over past chat sessions.",
                                  "period": "2025-01",
                                  "subtopics": [
                                      {"subtopic": "2-Prompt Workflow", "experience": "Created taxonomy discovery prompt followed by deep experience extraction."}
                                  ]
                                },
                                {
                                  "topic": "Flight Ticketing & Aggregation Systems",
                                  "experience": "You analyzed low-cost carrier booking engines and global distribution systems (GDS) API caching mechanisms. You evaluated latency bottlenecks in real-time seat inventory querying.",
                                  "unique_angle": "Overcame NDC protocol synchronization hurdles across international airline ticketing feeds.",
                                  "period": "2024-03",
                                  "subtopics": [
                                      {"subtopic": "GDS Integration", "experience": "Tested latency across Sabre and Amadeus APIs."}
                                  ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        chunks = index_experiences_from_json(sample_data)
    else:
        profile = {}
        if os.path.exists(profile_file):
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    profile = json.load(f)
            except Exception:
                profile = {}

        try:
            with open(exp_file, "r", encoding="utf-8") as f:
                exp_data = json.load(f)
            chunks = index_experiences_from_json(exp_data)
        except Exception as e:
            return jsonify(ok=False, message=f"Failed to read experience data: {e}"), 500

    # Execute RAG retrieval
    top_chunks = retrieve_relevant_experience(query, chunks)
    answer = generate_rag_answer(query, top_chunks, profile)

    retrieved_topic = top_chunks[0]["topic"] if top_chunks else "General Knowledge"
    unique_angle = top_chunks[0].get("unique_angle", "") if top_chunks else ""

    # Log the user question
    log_user_question(session_id, query, retrieved_topic)

    return jsonify(
        ok=True,
        reply=answer,
        retrieved_topic=retrieved_topic,
        unique_angle=unique_angle,
        chunks_found=len(top_chunks),
        avatar_name=f"{profile.get('first_name', 'Living')} {profile.get('last_name', 'Biography')}".strip()
    )


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

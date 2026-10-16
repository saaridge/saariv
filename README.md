# Saariv (Early Access)

> **Turn Your AI Chat History into a Monetizable Persona Link.**  
> Create your digital persona using your chats from **ChatGPT, Claude, Gemini, Grok**, and get a shareable personal link (`saariv.com/@yourname`) to post on LinkedIn and marketing bios to earn 24/7 without burning out on 1-on-1 calls.

---

## 💡 About Saariv

High-value professionals (**executive coaches, business consultants, technical advisors, startup mentors**) spend hundreds of hours sharing frameworks and answering questions inside AI chat tools. **Saariv** distills those conversations into an interactive, monetizable AI Persona.

### Key Value Pillars
- **Zero Upfront Cost**: We never ask for payment upfront or monthly SaaS subscriptions.
- **Pure Revenue Share**: We only take a modest platform commission when a client pays for an advisory session with your Persona.
- **Hands-Free Scaling**: Monetize followers and prospective clients globally without scheduling or repeating the same 1:1 Zoom sessions.
- **Built for Advisory Professionals**: Tailored for coaches, consultants, advisors, and mentors who solve problems on a one-on-one basis.

---

## 🚀 Quick Start (Local Run)

### 1. Prerequisites
- Python 3.11+ (Python 3.12 / 3.13 supported)
- Virtual environment (`venv`)

### 2. Setup & Run

```bash
# Navigate to the repo
cd saariv

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (credentials copied from saariv-1)
# cp .env.example .env (if setting up fresh)

# Run the development server
python3 app.py
```

Open your browser at **[http://127.0.0.1:8080](http://127.0.0.1:8080)**.

To run with **Gunicorn** (production WSGI):
```bash
chmod +x entrypoint.sh
./entrypoint.sh
```

---

## 🐳 Docker Deployment

The Docker setup uses the same Docker Hub repository and settings as `saariv-1` (`saaridge/saariv`).

### 1. Build Docker Image Locally
```bash
docker build -t saaridge/saariv:latest .
```

### 2. Run Container Locally
```bash
docker run -d \
  --name saariv \
  -p 8080:8080 \
  --env-file .env \
  saaridge/saariv:latest
```

Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)**.  
Check health status: **[http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)**.

To stop the container:
```bash
docker stop saariv && docker rm saariv
```

### 3. Build & Push to Docker Hub (`saaridge/saariv`) for Cloud / Northflank
For cloud hosts like Northflank, Render, or Railway (cross-compiling for `linux/amd64` from Mac Apple Silicon):

```bash
docker login
docker buildx build --platform linux/amd64 \
  -t saaridge/saariv:latest \
  -t saaridge/saariv:v0.1.0 \
  --push .
```

On **Northflank**:
1. Service image: `saaridge/saariv:latest`
2. Port: `8080`
3. Health check path: `GET /health`
4. Set environment variables from `.env` in the cloud dashboard.

---

## ⚙️ Configuration & Credentials

Configured via `.env` (credentials match `saariv-1`):

```env
FLASK_SECRET_KEY=change-me-to-a-long-random-string
PORT=8080

# Gmail SMTP Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=mohit.rohatgi2@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=mohit.rohatgi2@gmail.com

# Destination address for early access applications
MAIL_TO=mohit.rohatgi.mec10@gmail.com
```

> **Note on Gmail App Password**:  
> In Google Account → Security → 2-Step Verification → App Passwords, generate a 16-character password and set it as `MAIL_PASSWORD`.

---

## 🌟 What's Included in this Early Access Website

1. **Hero & Value Proposition**:
   - Clear explanation of chatbot export (ChatGPT, Claude, Gemini, Grok) -> Persona link.
   - Highlights the 0-upfront fee and commission-on-success model.

2. **Interactive Persona Simulator**:
   - Live interactive demo with 3 pre-calibrated advisor personas (Elena Rostova - SaaS Growth, David Chen - Fractional CTO, Marcus Vance - Pitch/GTM).
   - Allows users to test simulated prompts and view how the AI twin responds and prompts booking.

3. **Interactive Passive Income & Commission Calculator**:
   - Sliders for current 1:1 hourly rate, monthly profile views, and micro-advisory session fees.
   - Automatically computes projected monthly passive revenue, hours saved, and commission breakdown.

4. **Audience Breakdown**:
   - Executive Coaches, Business Consultants, Technical Advisors, Startup Mentors.

5. **Early Access Application Engine**:
   - Full form collecting name, email, specialty/role, profile URL, preferred chatbot, and advisory problems solved.
   - **Dual persistence**: Saves immediately to local SQLite (`waitlist.db`) for guaranteed zero-lead loss, and dispatches email notification to `MAIL_TO`.

6. **System Health Check**:
   - `GET /health` endpoint reporting operational status, app name, and SMTP readiness.

---

## 📂 Project Structure

```
saariv/
├── .dockerignore
├── .env                  # Environment secrets (copied from saariv-1)
├── .env.example          # Template environment file
├── .gitignore
├── Dockerfile            # Production container configuration
├── README.md             # Documentation & commands
├── app.py                # Flask application & API routes
├── entrypoint.sh         # Production Gunicorn runner
├── requirements.txt      # Python dependencies
├── waitlist.db           # SQLite database for lead capture
├── static/
│   ├── css/
│   │   └── styles.css    # Custom styles & animations
│   └── js/
│       └── main.js       # Simulator, calculator & form logic
└── templates/
    └── index.html        # High-converting landing page
```

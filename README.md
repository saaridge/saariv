# Saariv (Waitlist & AI Avatar Playground)

> **Turn Your Lived Experience into an AI Avatar That Answers Questions & Earns For You.**  
> Built for **founders, people who migrated out of India, consultants, and living biographies**. Turn your chats from **ChatGPT, Claude, Gemini, and Grok** into an interactive avatar that people can ask questions to—and earn without being deeply involved.

---

## 💡 What is Saariv?

People who have lived unique journeys (scaling a startup, migrating out of India to build a life abroad, or consulting enterprise clients) receive constant DMs on LinkedIn, Twitter, and WhatsApp asking for advice, playbooks, and lessons.

**Saariv** extracts your authentic stories from your everyday AI chat history and creates an interactive personal avatar. You can share your link (`saariv.com/@yourname`) as an interactive **advisory link** or as a **Living Biography** where people directly ask questions about your journey—and you get paid per question with **zero upfront cost**.

### Key Highlights
- **Audience Scope**:
  - **Founders & Operators**: Share war stories, supplier mistakes, CAC lessons, angel fundraising playbooks.
  - **People Who Migrated Out of India (Global NRIs & Expats)**: Share visa hurdles, 30% tax ruling, rental search, and European/US tech hiring bars.
  - **Specialist Consultants**: Provide paid micro-advisory from real client engagements.
  - **Interactive Living Biographies**: Allow peers, mentees, and community members to explore your life story through interactive conversations.
- **Zero Upfront Cost / Revenue Share**: We don't charge subscription fees. We take a modest commission only when customers pay to ask questions.
- **The Private Playground**: Test your avatar, ask it questions, and verify its voice before going live.

---

## 🔄 The Exact Process to Create an AI Avatar

1. **Step 1: Get the Saariv Discovery Prompt**  
   Saariv provides a tailored Discovery Prompt.
2. **Step 2: Run in your Chatbots**  
   Paste the prompt into the chatbots you use (ChatGPT, Claude, Gemini, Grok, etc.).
3. **Step 3: Paste Output into Saariv**  
   The prompt scans your chats and generates the topics and subtopics over which you've had deep chats eligible for consultation and storytelling.
4. **Step 4: Curate & Select Topics**  
   Select the specific topics and subtopics you want to provide to users.
5. **Step 5: Run Deep Extraction Prompt**  
   Saariv generates a second prompt to extract all detailed anecdotes, nuances, and frameworks about these topics.
6. **Step 6: Paste Output Back into Saariv**  
   Copy the output from your chatbots and paste it into the provided Saariv space.
7. **Step 7: Test in the Playground**  
   Enter the **Saariv Playground** to ask your own avatar questions on your experiences, check tone, and verify answers.
8. **Step 8: Go Live & Earn**  
   Click "Go Live" to get your shareable link (`saariv.com/@yourname`) for LinkedIn, X (Twitter), or your bio!

---

## 🚀 Quick Start (Local Run)

```bash
cd /Users/mohitrohatgi/Documents/workspace/saariv

# Activate virtual environment
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run website locally
python3 app.py
```

Open your browser at **[http://127.0.0.1:8080](http://127.0.0.1:8080)**.

To run with **Gunicorn** (production WSGI):
```bash
./entrypoint.sh
```

---

## 🐳 Docker Deployment

Uses the same Docker Hub repository as `saariv-1` (`saaridge/saariv`).

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

- Open: **[http://127.0.0.1:8080](http://127.0.0.1:8080)**
- Health check: **[http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)**
- Stop container: `docker stop saariv && docker rm saariv`

### 3. Build & Push to Docker Hub for Cloud / Northflank
```bash
docker login
docker buildx build --platform linux/amd64 \
  -t saaridge/saariv:latest \
  -t saaridge/saariv:v0.2.0 \
  --push .
```

---

## 📂 Project Structure

```
saariv/
├── .dockerignore
├── .env                  # Environment secrets (copied from saariv-1)
├── .env.example          # Template environment file
├── .gitignore
├── Dockerfile            # Production container configuration
├── README.md             # Documentation & instructions
├── app.py                # Flask app, playground API & waitlist database engine
├── entrypoint.sh         # Production WSGI runner
├── requirements.txt      # Python dependencies
├── waitlist.db           # SQLite database for waitlist entries
├── static/
│   ├── css/
│   │   └── styles.css    # Custom styles & live transaction animations
│   └── js/
│       └── main.js       # Playground logic & live inquiry-earnings animation
└── templates/
    └── index.html        # Waitlist, Playground & Experience-to-Earnings page
```

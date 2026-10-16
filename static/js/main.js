// Saariv — Playground & Lived Experience Earnings Engine

// 1. Avatars for the Saariv Playground
const avatars = {
  aarav: {
    id: "aarav",
    name: "Aarav Sharma",
    tagline: "Migrated from Pune to Amsterdam • Senior Tech Lead",
    category: "Global Expat & Migration Story",
    handle: "saariv.com/@aarav-sharma",
    feePerQuestion: "$8.00",
    source: "Trained on 1,120 ChatGPT & Claude chats on EU Blue Card, relocation & tech hiring",
    prompts: [
      "How did you find housing in Amsterdam without local Dutch credit history?",
      "How did you negotiate the 30% tax ruling with your employer?",
      "What was your tech interview preparation strategy from India?"
    ],
    initialResponse: `[Aarav Sharma • Living Biography & Relocation Experience]

1. Housing in the Netherlands:
Skip Funda agencies that demand 3x gross salary guarantees initially. Look at corporate housing brokers or short-stay serviced apartments in Haarlem or Amstelveen for your first 60 days. Once you have a BSN and first Dutch payslip, local landlords take your application seriously.

2. The 30% Ruling:
Ensure your employment contract explicitly states you were recruited from more than 150km outside the Dutch border. This single clause saves you ~25% in net income taxes.

3. Tech Hiring Bar:
European engineering teams prioritize async architectural writing and testing discipline over raw competitive programming speed. Show production incident handling on your CV.`
  },
  pooja: {
    id: "pooja",
    name: "Pooja Mehra",
    tagline: "Bootstrapped D2C Founder • Scaled from 0 to ₹8 Cr ARR",
    category: "Founder Journey & Living Biography",
    handle: "saariv.com/@pooja-mehra",
    feePerQuestion: "$12.00",
    source: "Trained on 840 Gemini & ChatGPT chats on vendor contracts, CAC spikes & angel pitches",
    prompts: [
      "What was your single worst packaging mistake and how did you survive it?",
      "How did you bring Meta CAC down when broad targeting failed?",
      "What metrics do Indian angels actually care about before investing?"
    ],
    initialResponse: `[Pooja Mehra • Founder War Stories & Operating Playbook]

1. Packaging & Supply Chain Trap:
Never give 100% of custom tooling or bottling to a single vendor. In year 1, our monsoon shipment cracked in transit and cost us ₹15 Lakhs. We survived by immediately negotiating a 60/40 volume split across two manufacturers with strict SLA damage clauses.

2. Surviving Post-iOS Meta CAC:
When customer acquisition cost jumped from ₹220 to ₹580, we stopped burning money on broad top-of-funnel ads. We implemented a 60-day WhatsApp replenishment sequence that lifted repeat orders from 14% to 38%.

3. Pitching Angels:
Show your Net RTO (Return to Origin) on COD orders. If courier returns are above 20%, investors know your gross margin will evaporate regardless of marketing spend.`
  },
  kabir: {
    id: "kabir",
    name: "Dr. Kabir Sen",
    tagline: "Healthcare Systems Consultant • Ex-NHS Digital Advisor",
    category: "Specialist Advisory & Consulting",
    handle: "saariv.com/@dr-kabir",
    feePerQuestion: "$25.00",
    source: "Trained on 1,600 Claude & Grok chats on clinical workflow compliance & FHIR",
    prompts: [
      "How do we overcome clinician resistance when deploying electronic records?",
      "What is the biggest hidden cost in hospital EHR vendor contracts?",
      "How should a digital health startup structure a hospital pilot?"
    ],
    initialResponse: `[Dr. Kabir Sen • Healthcare Advisory Framework]

1. Clinician Adoption Rule:
If a digital chart requires more than 3 extra clicks during patient intake, physicians will revert to paper workarounds. Involve nurses and senior registrars during UX drafting, not just the hospital board.

2. Hidden Integration Fees:
Legacy hospital software vendors routinely charge $40k+ for simple HL7/FHIR API access. Include unencumbered API interoperability clauses before executing initial multi-year software agreements.

3. Pilot Containment:
Run a 30-day shadow workflow in a single outpatient ward before attempting a facility-wide cutover.`
  }
};

let activeAvatarId = "aarav";

// Switch Avatar in Playground
function selectPlaygroundAvatar(avatarId) {
  if (!avatars[avatarId]) return;
  activeAvatarId = avatarId;

  // Update tabs
  document.querySelectorAll(".avatar-tab").forEach(tab => {
    tab.classList.remove("active", "border-white", "bg-zinc-900/60", "text-white");
    tab.classList.add("text-zinc-400");
  });

  const activeTab = document.getElementById(`tab-${avatarId}`);
  if (activeTab) {
    activeTab.classList.add("active", "border-white", "bg-zinc-900/60", "text-white");
    activeTab.classList.remove("text-zinc-400");
  }

  const a = avatars[avatarId];
  document.getElementById("playground-name").textContent = a.name;
  document.getElementById("playground-tagline").textContent = a.tagline;
  document.getElementById("playground-category").textContent = a.category;
  document.getElementById("playground-handle").textContent = a.handle;
  document.getElementById("playground-source").textContent = a.source;
  document.getElementById("playground-fee").textContent = a.feePerQuestion;
  document.getElementById("playground-response-box").textContent = a.initialResponse;

  // Prompt suggestions
  const chipsContainer = document.getElementById("prompt-chips");
  chipsContainer.innerHTML = a.prompts.map(prompt => 
    `<button type="button" onclick="askPlayground('${prompt.replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-300 transition-colors">"${prompt}"</button>`
  ).join("");

  if (window.lucide) {
    lucide.createIcons();
  }
}

function askPlayground(promptText) {
  const input = document.getElementById("playground-input");
  input.value = promptText;
  handlePlaygroundSubmit(new Event("submit"));
}

async function handlePlaygroundSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("playground-input");
  const query = input.value.trim();
  const responseBox = document.getElementById("playground-response-box");
  const submitBtn = document.getElementById("playground-submit-btn");

  responseBox.innerHTML = `<span class="text-zinc-400 font-mono text-xs">Simulating query against ${avatars[activeAvatarId].name}'s playground avatar...</span>`;
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/simulate-persona", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona_id: activeAvatarId, query: query })
    });
    const data = await res.json();
    responseBox.textContent = `[${data.name} Avatar Playground • Lived Experience Query]\n\n${data.reply}`;
  } catch (err) {
    responseBox.textContent = avatars[activeAvatarId].initialResponse;
  } finally {
    submitBtn.disabled = false;
    input.value = "";
  }
}

function openGoLiveModal() {
  const current = avatars[activeAvatarId];
  alert(`🚀 Ready to Go Live!\n\nYour avatar will be published at:\n${current.handle}\n\nShare this link on LinkedIn, X (Twitter), or your bio. Anyone can ask questions about your journey and you earn ${current.feePerQuestion} per question with zero upfront fees!`);
}

// 2. Experience-to-Earnings Live Interactive Animation
const sampleInquiries = [
  {
    sender: "Rohan K. (Pune, India)",
    question: "How did you find housing in Amsterdam without local Dutch credit history?",
    fee: 8.00,
    time: "2 mins ago"
  },
  {
    sender: "Ananya M. (Bengaluru, India)",
    question: "What is the interview format for senior engineers at Booking.com?",
    fee: 12.00,
    time: "5 mins ago"
  },
  {
    sender: "Vikram S. (Hyderabad, India)",
    question: "How did you negotiate the 30% tax ruling before signing the contract?",
    fee: 8.00,
    time: "11 mins ago"
  },
  {
    sender: "Sneha P. (Delhi, India)",
    question: "What was your exact monthly living expense before your first European paycheck?",
    fee: 10.00,
    time: "18 mins ago"
  },
  {
    sender: "Karthik R. (Chennai, India)",
    question: "Can my spouse work immediately on the EU Blue Card dependent visa?",
    fee: 8.00,
    time: "24 mins ago"
  }
];

let currentInquiryIndex = 0;
let totalEarnings = 348.00;
let totalAnswered = 42;

function triggerNextInquiry() {
  currentInquiryIndex = (currentInquiryIndex + 1) % sampleInquiries.length;
  const inq = sampleInquiries[currentInquiryIndex];

  totalEarnings += inq.fee;
  totalAnswered += 1;

  // Update DOM
  const questionEl = document.getElementById("anim-question");
  const senderEl = document.getElementById("anim-sender");
  const feeEl = document.getElementById("anim-fee");
  const earningsEl = document.getElementById("anim-total-earnings");
  const answeredEl = document.getElementById("anim-total-answered");
  const cardEl = document.getElementById("anim-inquiry-card");
  const toastEl = document.getElementById("anim-payout-toast");

  if (questionEl) questionEl.textContent = `"${inq.question}"`;
  if (senderEl) senderEl.textContent = `Asked by ${inq.sender} • ${inq.time}`;
  if (feeEl) feeEl.textContent = `+$${inq.fee.toFixed(2)}`;
  if (earningsEl) earningsEl.textContent = `$${totalEarnings.toFixed(2)}`;
  if (answeredEl) answeredEl.textContent = `${totalAnswered} questions`;

  // Flash animation
  if (cardEl) {
    cardEl.classList.remove("animate-income-flash");
    void cardEl.offsetWidth; // trigger reflow
    cardEl.classList.add("animate-income-flash");
  }

  if (toastEl) {
    toastEl.textContent = `💰 +$${inq.fee.toFixed(2)} credited from ${inq.sender.split(" ")[0]} via Saariv`;
    toastEl.classList.remove("hidden");
    setTimeout(() => {
      if (toastEl) toastEl.classList.add("hidden");
    }, 3000);
  }
}

// Auto-cycle inquiries
setInterval(() => {
  triggerNextInquiry();
}, 5000);

// 3. Process Steps Interactive Switcher
function showProcessStep(stepNum) {
  document.querySelectorAll(".process-step-btn").forEach((btn, idx) => {
    if (idx + 1 === stepNum) {
      btn.classList.add("border-white", "bg-zinc-900", "text-white");
      btn.classList.remove("border-zinc-800", "text-zinc-500");
    } else {
      btn.classList.remove("border-white", "bg-zinc-900", "text-white");
      btn.classList.add("border-zinc-800", "text-zinc-500");
    }
  });

  const stepDetails = [
    {
      title: "Step 1 & 2: Get Saariv Discovery Prompt & Run in Chatbots",
      desc: "Saariv generates a specialized discovery prompt. You copy it and paste it into whichever chatbots you regularly use (ChatGPT, Claude, Gemini, Grok, etc.). The prompt commands the LLM to scan your conversational context and synthesize topics.",
      snippet: `[Saariv Discovery Prompt Preview]
"Analyze our entire conversation history across all threads. Identify all major topics, frameworks, personal milestones, migration journeys, career pivots, and business lessons where I shared deep domain knowledge or lived experience. Output as a clean structured list of Topics & Subtopics eligible for advisory."`
    },
    {
      title: "Step 3 & 4: Paste Output in Saariv & Select Published Topics",
      desc: "Copy the chatbot's output and paste it into Saariv. Saariv organizes the generated topics and subtopics into a selectable dashboard. You curate and check off exactly what you want the public to be able to ask your avatar (e.g. 'EU Blue Card Journey', 'Bootstrapping D2C', 'Tech Architecture').",
      snippet: `[Extracted Topics Dashboard]
✓ Moving from Pune to Amsterdam (Visa, Tax, Remittance, Rental Search)
✓ Software Engineering Interviews at European Tech Hubs
✓ Bootstrapped Manufacturing & Packaging Pitfalls (Hidden Costs)
✗ Personal Family Travel (Unselected / Kept Private)`
    },
    {
      title: "Step 5 & 6: Run Deep Extraction Prompt & Paste Back",
      desc: "Based on your selected topics, Saariv generates a second deep-extraction prompt. Paste this into your chatbots to extract all rich details, anecdotes, and nuances. Copy the output and paste it back into Saariv's secure space to build your avatar.",
      snippet: `[Saariv Deep Extraction Prompt Preview]
"For the selected topics [EU Blue Card, Housing, Tech Interviews], extract all specific anecdotes, concrete mistakes made, financial figures, company names, and chronological lessons I shared. Maintain my natural voice, candid tone, and first-person perspective."`
    },
    {
      title: "Step 7 & 8: Test in Playground & Go Live with Your Link",
      desc: "Before making your avatar public, open the Saariv Playground! Ask your own avatar tough questions to verify its advice, tone, and accuracy. When satisfied, click 'Go Live' to generate your custom link (saariv.com/@yourname) to share on LinkedIn, X, or your bio.",
      snippet: `[Live Persona Link Ready]
URL: saariv.com/@aarav-sharma
Status: Live & Monetizing
Pricing: $8.00 per question
Model: Zero upfront fees • You keep 88% of every question fee deposited to your bank`
    }
  ];

  const current = stepDetails[stepNum - 1];
  if (current) {
    document.getElementById("step-title").textContent = current.title;
    document.getElementById("step-desc").textContent = current.desc;
    document.getElementById("step-snippet").textContent = current.snippet;
  }
}

// 4. Waitlist Form Submission
async function handleWaitlistSubmit(e) {
  e.preventDefault();
  const form = document.getElementById("waitlist-form");
  const submitBtn = document.getElementById("waitlist-submit-btn");
  const btnText = document.getElementById("waitlist-btn-text");
  const successBox = document.getElementById("waitlist-success");
  const errorBox = document.getElementById("waitlist-error");
  const errorMsg = document.getElementById("waitlist-error-message");

  errorBox.classList.add("hidden");
  btnText.textContent = "Joining Waitlist...";
  submitBtn.disabled = true;

  const formData = new FormData(form);

  try {
    const res = await fetch("/api/waitlist", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (res.ok && data.ok) {
      form.classList.add("hidden");
      successBox.classList.remove("hidden");
      document.getElementById("waitlist-success-msg").textContent = data.message || "You are on the waitlist! We will notify you as soon as your batch is unlocked.";
      if (data.waitlist_number) {
        document.getElementById("waitlist-queue-num").textContent = data.waitlist_number;
      }
      successBox.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      errorBox.classList.remove("hidden");
      errorMsg.textContent = data.message || "Unable to join waitlist. Please check required fields.";
    }
  } catch (err) {
    errorBox.classList.remove("hidden");
    errorMsg.textContent = "Network error. Please try again shortly.";
  } finally {
    btnText.textContent = "Join Waitlist";
    submitBtn.disabled = false;
    if (window.lucide) {
      lucide.createIcons();
    }
  }
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  selectPlaygroundAvatar("aarav");
  showProcessStep(1);
});

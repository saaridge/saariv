// Saariv Advisory Terminal & Economics Engine

const personas = {
  elena: {
    name: "Elena Rostova",
    title: "B2B SaaS Growth & GTM",
    slug: "elena-rostova",
    hourlyRate: "$350/hr",
    asyncFee: "$45",
    source: "Knowledge Base: 1,420 Claude & ChatGPT sessions synthesized",
    prompts: [
      "Diagnosing our 4.2% monthly logo churn on $50/mo ACV",
      "Transitioning from founder-led sales to PLG onboarding",
      "Evaluating pricing tiers for multi-seat enterprise pilot"
    ],
    initialResponse: `[Elena Rostova Advisory Synthesis • Grounded in 14 Client Deployments]

1. ACV vs. Friction Analysis:
If annual contract value is below $12,000, dedicated outbound SDRs introduce negative unit economics. Transition immediately to product-led onboarding with reverse-trial checkpoints.

2. Week-2 Retention Heuristic:
78% of enterprise logo churn correlates directly with failing to achieve first milestone value by day 14. Track activation milestones rather than raw login frequency.

3. Actionable Next Step:
Audit your onboarding funnel for the single bottleneck step where drop-off exceeds 35%.`
  },
  david: {
    name: "David Chen",
    title: "Fractional CTO & Systems Architecture",
    slug: "david-chen",
    hourlyRate: "$400/hr",
    asyncFee: "$55",
    source: "Knowledge Base: 2,150 Gemini & ChatGPT architectural reviews synthesized",
    prompts: [
      "Evaluating migration from monolithic Rails to Go microservices",
      "Remediating database read bottlenecks without schema downtime",
      "Architecting event-driven pipelines for 50k req/sec"
    ],
    initialResponse: `[David Chen Advisory Synthesis • Grounded in Distributed Systems Patterns]

1. The Premature Microservices Penalty:
For engineering organizations under 20 engineers, microservices typically impose a 30-40% coordination latency overhead without developer velocity gains. Maintain a modular monolith with strict domain boundaries.

2. Persistence Layer Remediation:
Before executing schema refactors, deploy read replicas and Redis write-behind caching on hot query paths. This resolves 80% of read saturation.

3. Actionable Next Step:
Profile p99 latency distributions across top 5 database endpoints to isolate unindexed JOIN operations.`
  },
  marcus: {
    name: "Marcus Vance",
    title: "Venture Strategy & Pitch Counsel",
    slug: "marcus-vance",
    hourlyRate: "$300/hr",
    asyncFee: "$40",
    source: "Knowledge Base: 980 Grok & Claude venture memos synthesized",
    prompts: [
      "Structuring the 10-slide Seed-to-Series A pitch deck",
      "Defending AI workflow defensibility to tier-1 venture partners",
      "Evaluating SAFE notes vs. priced preferred equity round"
    ],
    initialResponse: `[Marcus Vance Advisory Synthesis • Grounded in Tier-1 Venture Rubrics]

1. The 'Why Now' Anchor:
Never open partner meetings with generic TAM calculations. Lead with the regulatory, infrastructural, or architectural dislocation that makes your company possible today when it was non-viable 18 months ago.

2. Net Revenue Retention (NRR) Over Top-Line Growth:
Early-stage institutional partners prioritize cohort retention above 120% over brute-force customer acquisition. Defensible moats are revealed in expansion curves, not top-of-funnel ad spend.

3. Actionable Next Step:
Restructure your executive summary slide to highlight organic cohort retention within the first 6 months.`
  }
};

let activePersonaId = "elena";

function selectPersona(personaId) {
  if (!personas[personaId]) return;
  activePersonaId = personaId;

  // Update tabs
  document.querySelectorAll(".persona-tab").forEach(tab => {
    tab.classList.remove("active", "border-white", "bg-zinc-900/40", "text-white");
    tab.classList.add("text-zinc-400");
  });

  const activeTab = document.getElementById(`tab-${personaId}`);
  if (activeTab) {
    activeTab.classList.add("active", "border-white", "bg-zinc-900/40", "text-white");
    activeTab.classList.remove("text-zinc-400");
  }

  const p = personas[personaId];
  document.getElementById("terminal-url").textContent = `saariv.com/advisory/${p.slug}`;
  document.getElementById("persona-source").textContent = p.source;
  document.getElementById("persona-rate").textContent = p.hourlyRate;
  document.getElementById("persona-async-fee").textContent = p.asyncFee;
  document.getElementById("persona-response-box").textContent = p.initialResponse;

  // Populate prompts
  const chipsContainer = document.getElementById("prompt-chips");
  chipsContainer.innerHTML = p.prompts.map(prompt => 
    `<button type="button" onclick="applyPrompt('${prompt.replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-300 transition-colors">"${prompt}"</button>`
  ).join("");

  if (window.lucide) {
    lucide.createIcons();
  }
}

function applyPrompt(promptText) {
  const input = document.getElementById("sim-input");
  input.value = promptText;
  handleSimulatorSubmit(new Event("submit"));
}

async function handleSimulatorSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("sim-input");
  const query = input.value.trim();
  const responseBox = document.getElementById("persona-response-box");
  const submitBtn = document.getElementById("sim-submit-btn");

  responseBox.innerHTML = `<span class="text-zinc-400 font-mono text-xs">Querying distilled knowledge index for ${personas[activePersonaId].name}...</span>`;
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/simulate-persona", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona_id: activePersonaId, query: query })
    });
    const data = await res.json();
    responseBox.textContent = `[${data.name} Advisory Counsel • Verified Persona]\n\n${data.reply}`;
  } catch (err) {
    responseBox.textContent = personas[activePersonaId].initialResponse;
  } finally {
    submitBtn.disabled = false;
    input.value = "";
  }
}

function calculateEarnings() {
  const hourlyRate = parseInt(document.getElementById("slider-hourly-rate").value) || 250;
  const views = parseInt(document.getElementById("slider-views").value) || 2500;
  const sessionFee = parseInt(document.getElementById("slider-session-fee").value) || 45;

  document.getElementById("val-hourly-rate").textContent = `$${hourlyRate} / hr`;
  document.getElementById("val-views").textContent = `${views.toLocaleString()} visits`;
  document.getElementById("val-session-fee").textContent = `$${sessionFee} / session`;

  // Conservative 1.6% conversion on high-intent inbound visitors
  const monthlyInquiries = Math.round(views * 0.016);
  const gross = monthlyInquiries * sessionFee;
  const platformFee = Math.round(gross * 0.12);
  const net = gross - platformFee;
  const hoursSaved = Math.round((monthlyInquiries * 25) / 60);

  document.getElementById("calc-inquiries").textContent = `${monthlyInquiries} consultations`;
  document.getElementById("calc-gross").textContent = `$${gross.toLocaleString()}.00`;
  document.getElementById("calc-fee").textContent = `-$${platformFee.toLocaleString()}.00`;
  document.getElementById("calc-earnings").textContent = `$${net.toLocaleString()}.00`;
  document.getElementById("calc-hours-saved").textContent = `~${hoursSaved} hours`;
}

async function handleFormSubmit(e) {
  e.preventDefault();
  const form = document.getElementById("early-access-form");
  const submitBtn = document.getElementById("submit-btn");
  const btnText = document.getElementById("btn-text");
  const successBox = document.getElementById("form-success");
  const errorBox = document.getElementById("form-error");
  const errorMsg = document.getElementById("error-message");

  errorBox.classList.add("hidden");
  btnText.textContent = "Submitting Application...";
  submitBtn.disabled = true;

  const formData = new FormData(form);

  try {
    const res = await fetch("/api/early-access", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (res.ok && data.ok) {
      form.classList.add("hidden");
      successBox.classList.remove("hidden");
      document.getElementById("success-message").textContent = data.message || "We will review your practice details and issue your private ingestion invitation.";
      if (data.waitlist_number) {
        document.getElementById("queue-num").textContent = data.waitlist_number;
      }
      successBox.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      errorBox.classList.remove("hidden");
      errorMsg.textContent = data.message || "Unable to submit application. Please review required fields.";
    }
  } catch (err) {
    errorBox.classList.remove("hidden");
    errorMsg.textContent = "Network error. Please try again shortly.";
  } finally {
    btnText.textContent = "Submit Partner Application";
    submitBtn.disabled = false;
    if (window.lucide) {
      lucide.createIcons();
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  selectPersona("elena");
  calculateEarnings();
});

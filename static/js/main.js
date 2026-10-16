// Saariv Interactive Frontend Logic

// Persona Data for Live Simulator
const personas = {
  elena: {
    name: "Elena Rostova",
    title: "• B2B SaaS Growth Consultant",
    hourlyRate: "$350/hr",
    source: "Trained on 1,420+ Claude & ChatGPT Chats ingested",
    prompts: [
      "How do I reduce churn for our $50/mo SaaS?",
      "Should we hire outbound SDRs or invest in PLG?",
      "Enterprise pilot pricing strategies?"
    ],
    initialResponse: `Based on the B2B GTM framework I developed through 50+ enterprise rollouts:

1. **Audit your ACV vs Sales Cycle**: If your contract value is under $12k/yr, ditch outbound SDRs immediately. Transition to product-led onboarding with an automated reverse trial.
2. **The 30-Day Churn Diagnostic**: Check week-2 feature adoption. 78% of churn happens because the customer never hit their 'first milestone value' before day 14.

💡 *Would you like me to analyze your specific pricing tier and generate a customized retention playbook?*`
  },
  david: {
    name: "David Chen",
    title: "• Fractional CTO & Systems Architect",
    hourlyRate: "$400/hr",
    source: "Trained on 2,150+ Gemini & ChatGPT Chats ingested",
    prompts: [
      "When should we migrate from a Monolith to Microservices?",
      "How do I cut our AWS bill by 30% without downtime?",
      "Evaluating tech stack for high-throughput WebSocket events?"
    ],
    initialResponse: `Reviewing this against my distributed architecture principles:

1. **Premature Microservices Trap**: If your engineering team is under 15 engineers, stay on a modular monolith. Splitting prematurely incurs a 40% network latency tax and massive DevOps overhead.
2. **Database Bottlenecks**: Implement read-replicas and Redis caching on write-heavy endpoints before re-architecting your schemas.

💡 *Want me to review your stack diagram or run an automated latency checklist for your application?*`
  },
  marcus: {
    name: "Marcus Vance",
    title: "• Seed-to-Series A Pitch & GTM Mentor",
    hourlyRate: "$300/hr",
    source: "Trained on 980+ Grok & Claude Chats ingested",
    prompts: [
      "How do I answer 'What is your defensible AI moat' to VCs?",
      "Review our 10-slide pitch deck flow",
      "Should we raise SAFE notes or priced equity in 2025?"
    ],
    initialResponse: `Here is how tier-1 VCs will evaluate this slide deck:

1. **The 'Why Now' Anchor**: Never start with TAM slides. Start with the tectonic regulatory or AI shift that makes your solution viable today when it wasn't 18 months ago.
2. **Pipeline Velocity**: Show Cohort Net Revenue Retention (NRR). An NRR above 125% beats a flat 20% MoM top-line growth every single time.

💡 *Upload your deck outline or tell me your current ARR and I'll simulate a 5-question partner meeting interrogation.*`
  }
};

let activePersonaId = "elena";

// Select Persona tab in simulator
function selectPersona(personaId) {
  if (!personas[personaId]) return;
  activePersonaId = personaId;

  // Update tabs
  document.querySelectorAll(".persona-tab").forEach(tab => {
    tab.classList.remove("active", "border-indigo-500", "bg-indigo-950/20", "text-white");
    tab.classList.add("border-transparent", "text-slate-400");
  });

  const activeTab = document.getElementById(`tab-${personaId}`);
  if (activeTab) {
    activeTab.classList.add("active", "border-indigo-500", "bg-indigo-950/20", "text-white");
    activeTab.classList.remove("border-transparent", "text-slate-400");
  }

  const p = personas[personaId];
  document.getElementById("persona-name").textContent = p.name;
  document.getElementById("persona-title").textContent = p.title;
  document.getElementById("persona-rate").textContent = p.hourlyRate;
  document.getElementById("persona-source").innerHTML = `<i data-lucide="database" class="w-3.5 h-3.5"></i> ${p.source}`;
  document.getElementById("persona-response-box").textContent = p.initialResponse;

  // Update prompt chips
  const chipsContainer = document.getElementById("prompt-chips");
  chipsContainer.innerHTML = p.prompts.map(prompt => 
    `<button type="button" onclick="applyPrompt('${prompt.replace(/'/g, "\\'")}')" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs text-slate-200 transition-colors">"${prompt}"</button>`
  ).join("");

  if (window.lucide) {
    lucide.createIcons();
  }
}

// Click on sample prompt
function applyPrompt(promptText) {
  const input = document.getElementById("sim-input");
  input.value = promptText;
  handleSimulatorSubmit(new Event("submit"));
}

// Handle question submission to persona
async function handleSimulatorSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("sim-input");
  const query = input.value.trim();
  const responseBox = document.getElementById("persona-response-box");
  const submitBtn = document.getElementById("sim-submit-btn");

  responseBox.innerHTML = `<span class="inline-flex items-center gap-2 text-indigo-400"><svg class="animate-spin h-4 w-4 text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg> Analyzing query against persona's distilled chat history...</span>`;
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/simulate-persona", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona_id: activePersonaId, query: query })
    });
    const data = await res.json();
    responseBox.textContent = data.reply;
  } catch (err) {
    responseBox.textContent = "Unable to connect to persona simulator. Running fallback sample response.";
  } finally {
    submitBtn.disabled = false;
    input.value = "";
  }
}

// Interactive Earnings Calculator
function calculateEarnings() {
  const hourlyRate = parseInt(document.getElementById("slider-hourly-rate").value) || 250;
  const views = parseInt(document.getElementById("slider-views").value) || 3500;
  const sessionFee = parseInt(document.getElementById("slider-session-fee").value) || 39;

  document.getElementById("val-hourly-rate").textContent = `$${hourlyRate} / hr`;
  document.getElementById("val-views").textContent = `${views.toLocaleString()} views`;
  document.getElementById("val-session-fee").textContent = `$${sessionFee} / session`;

  // Realistic conversion: ~1.8% of high-intent visitors engage with accessible micro-advisory
  const monthlySessions = Math.round(views * 0.018);
  const gross = monthlySessions * sessionFee;
  // Net earnings keeping 85% (Saariv 15% revenue share)
  const netEarnings = Math.round(gross * 0.85);

  // Time saved compared to doing 1:1 calls for those questions (~25 mins per session equivalent)
  const hoursSaved = Math.round((monthlySessions * 25) / 60);

  document.getElementById("calc-earnings").textContent = `$${netEarnings.toLocaleString()} / mo`;
  document.getElementById("calc-hours-saved").textContent = `~${hoursSaved} hrs/month`;
}

// Early Access Form Handler
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
      document.getElementById("success-message").textContent = data.message || "We received your details and will send your persona setup link soon.";
      if (data.waitlist_number) {
        document.getElementById("queue-num").textContent = data.waitlist_number;
      }
      successBox.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      errorBox.classList.remove("hidden");
      errorMsg.textContent = data.message || "Failed to submit. Please check your inputs and try again.";
    }
  } catch (err) {
    errorBox.classList.remove("hidden");
    errorMsg.textContent = "Network error. Please try again shortly.";
  } finally {
    btnText.textContent = "Apply for Early Access";
    submitBtn.disabled = false;
    if (window.lucide) {
      lucide.createIcons();
    }
  }
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  calculateEarnings();
});

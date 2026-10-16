// Saariv — Onboarding Stepper, Knowledge Grounding & Living Biography Engine

let onboardingState = {
  sessionId: localStorage.getItem("saariv_session_id") || "session_" + Math.random().toString(36).substring(2, 10),
  firstName: "",
  lastName: "",
  email: "",
  linkedinUrl: "",
  taxonomyData: null,
  selectedItems: {
    domains: new Set(),
    subdomains: new Set(),
    topics: new Set(),
    subtopics: new Set()
  },
  indexedCount: 0
};

// ==========================================
// STEPPER NAVIGATION & BACK BUTTONS
// ==========================================
function goToStep(stepNum) {
  // Hide all panels
  for (let i = 1; i <= 5; i++) {
    const panel = document.getElementById(`step-panel-${i}`);
    const tab = document.getElementById(`stepper-tab-${i}`);
    if (panel) panel.classList.add("hidden");
    if (tab) {
      tab.classList.remove("border-white", "bg-zinc-900", "text-white");
      tab.classList.add("border-zinc-800", "text-zinc-500");
    }
  }

  // Activate target panel
  const activePanel = document.getElementById(`step-panel-${stepNum}`);
  const activeTab = document.getElementById(`stepper-tab-${stepNum}`);
  if (activePanel) {
    activePanel.classList.remove("hidden");
    activePanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  if (activeTab) {
    activeTab.classList.add("border-white", "bg-zinc-900", "text-white");
    activeTab.classList.remove("border-zinc-800", "text-zinc-500");
  }

  if (window.lucide) {
    lucide.createIcons();
  }
}

// Copy prompt helper
function copyPrompt(elementId, btnId) {
  const content = document.getElementById(elementId).innerText;
  navigator.clipboard.writeText(content).then(() => {
    const btn = document.getElementById(btnId);
    if (btn) {
      const originalHTML = btn.innerHTML;
      btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i> Copied!`;
      if (window.lucide) lucide.createIcons();
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        if (window.lucide) lucide.createIcons();
      }, 2000);
    }
  });
}

// ==========================================
// STEP 1: BASIC DETAILS
// ==========================================
async function handleStep1Submit(e) {
  e.preventDefault();
  const firstName = document.getElementById("step1_first_name").value.trim();
  const lastName = document.getElementById("step1_last_name").value.trim();
  const email = document.getElementById("step1_email").value.trim();
  const linkedinUrl = document.getElementById("step1_linkedin").value.trim();

  onboardingState.firstName = firstName;
  onboardingState.lastName = lastName;
  onboardingState.email = email;
  onboardingState.linkedinUrl = linkedinUrl;

  try {
    const res = await fetch("/api/onboarding/step1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: onboardingState.sessionId,
        first_name: firstName,
        last_name: lastName,
        email: email,
        linkedin_url: linkedinUrl
      })
    });
    const data = await res.json();
    if (data.session_id) {
      onboardingState.sessionId = data.session_id;
      localStorage.setItem("saariv_session_id", data.session_id);
    }
  } catch (err) {
    console.warn("Saved locally:", err);
  }

  goToStep(2);
}

// ==========================================
// STEP 2: PROMPT 1 (TAXONOMY)
// ==========================================
function loadSampleTaxonomy() {
  const sampleTaxonomy = {
    "metadata": {
      "generated_on": "2025-01-15",
      "source_scope": "Full conversation history across persistent memory and active chats",
      "coverage_notes": "None",
      "total_domains": 2,
      "total_topics": 5
    },
    "domains": [
      {
        "domain": "Software Engineering & Systems Architecture",
        "subdomains": [
          {
            "subdomain": "Travel & Distributed Booking Infrastructure",
            "topics": [
              {
                "topic": "Hotel Research",
                "evidence": "Analyzed luxury and boutique property discovery APIs, caching models, and user review aggregators",
                "period": "2024-05",
                "frequency": "occasional",
                "confidence": "high",
                "subtopics": ["Property Caching", "Amenity Tag Extraction", "Review Sentiment"]
              },
              {
                "topic": "Flight Ticketing & Aggregation Systems",
                "evidence": "Explored low-cost carrier APIs, GDS integration latency, and fare calendar caching architectures",
                "period": "2024-02",
                "frequency": "recurring",
                "confidence": "high",
                "subtopics": ["GDS Sabre/Amadeus Connectivity", "Multi-City Fare Graph", "Real-Time Seat Hold Locks"]
              }
            ]
          },
          {
            "subdomain": "Interviewing & Career Progression",
            "topics": [
              {
                "topic": "Google L5 Software Engineer Interview Loop",
                "evidence": "Prepared for distributed systems interview rounds, trade-off communication, and system design rubrics",
                "period": "2023-08",
                "frequency": "recurring",
                "confidence": "high",
                "subtopics": ["Distributed Key-Value Store Design", "Behavioral Leadership Signals", "Code Quality & Testing"]
              },
              {
                "topic": "Global Technical Leadership Opportunities",
                "evidence": "Evaluated relocation packages, Staff+ engineering compensation bands across Amsterdam, London, and Zurich",
                "period": "2024-09",
                "frequency": "occasional",
                "confidence": "medium",
                "subtopics": ["EU Relocation Tax Benefits", "Staff SWE Compensation Bands", "Remote vs In-Office Bands"]
              }
            ]
          }
        ]
      },
      {
        "domain": "Venture & Product Strategy",
        "subdomains": [
          {
            "subdomain": "AI Avatars & Creator Monetization",
            "topics": [
              {
                "topic": "Saariv Development & Strategy",
                "evidence": "Architected the 2-prompt taxonomy and experience extraction pipeline for Living Biographies",
                "period": "2025-01",
                "frequency": "recurring",
                "confidence": "high",
                "subtopics": ["2-Prompt Knowledge Distillation", "Zero-Upfront Revenue Share", "Privacy Isolation"]
              }
            ]
          }
        ]
      }
    ]
  };

  document.getElementById("step2_pasted_json").value = JSON.stringify(sampleTaxonomy, null, 2);
}

async function handleStep2Submit() {
  const errorDiv = document.getElementById("step2_error");
  errorDiv.classList.add("hidden");

  const rawJson = document.getElementById("step2_pasted_json").value.trim();
  if (!rawJson) {
    errorDiv.textContent = "Please paste the chatbot's JSON output or click 'Load Sample Output'.";
    errorDiv.classList.remove("hidden");
    return;
  }

  let parsed;
  try {
    parsed = JSON.parse(rawJson);
  } catch (err) {
    errorDiv.textContent = `JSON Syntax Error: ${err.message}. Please verify the output is valid JSON.`;
    errorDiv.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch("/api/onboarding/step2", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: onboardingState.sessionId,
        taxonomy_json: parsed
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      errorDiv.textContent = data.message || "Failed to process taxonomy.";
      errorDiv.classList.remove("hidden");
      return;
    }

    onboardingState.taxonomyData = parsed;
    renderHierarchicalChecklist(parsed.domains || []);
    goToStep(3);
  } catch (err) {
    onboardingState.taxonomyData = parsed;
    renderHierarchicalChecklist(parsed.domains || []);
    goToStep(3);
  }
}

// ==========================================
// STEP 3: HIERARCHICAL SELECTION (DOMAINS, SUBDOMAINS, TOPICS, SUBTOPICS)
// ==========================================
function renderHierarchicalChecklist(domains) {
  const container = document.getElementById("topics-checklist");
  container.innerHTML = "";

  domains.forEach((d, dIdx) => {
    const domainId = `domain_${dIdx}`;
    const domainName = d.domain || `Domain ${dIdx + 1}`;

    const domainCard = document.createElement("div");
    domainCard.className = "p-4 rounded border border-zinc-800 bg-zinc-950/70 space-y-3";

    let subdomainsHtml = "";
    (d.subdomains || []).forEach((sd, sdIdx) => {
      const subdomainId = `subdomain_${dIdx}_${sdIdx}`;
      const subdomainName = sd.subdomain || `Subdomain ${sdIdx + 1}`;

      let topicsHtml = "";
      (sd.topics || []).forEach((t, tIdx) => {
        const topicId = `topic_${dIdx}_${sdIdx}_${tIdx}`;
        const topicName = t.topic || `Topic ${tIdx + 1}`;

        let subtopicsHtml = "";
        (t.subtopics || []).forEach((st, stIdx) => {
          const subtopicId = `subtopic_${dIdx}_${sdIdx}_${tIdx}_${stIdx}`;
          const stName = typeof st === 'string' ? st : st.subtopic || `Subtopic ${stIdx + 1}`;

          subtopicsHtml += `
            <label class="flex items-center gap-2 py-1 px-2 rounded hover:bg-zinc-900 cursor-pointer text-[11px] text-zinc-300">
              <input type="checkbox" checked id="${subtopicId}" data-type="subtopic" data-topic-id="${topicId}" data-name="${encodeURIComponent(stName)}" onchange="onSubtopicToggle('${subtopicId}', '${topicId}')" class="item-checkbox accent-white w-3.5 h-3.5 cursor-pointer">
              <span>${stName}</span>
            </label>
          `;
        });

        topicsHtml += `
          <div class="ml-4 pl-3 border-l border-zinc-800 py-1.5 space-y-1">
            <label class="flex items-start gap-2.5 cursor-pointer">
              <input type="checkbox" checked id="${topicId}" data-type="topic" data-subdomain-id="${subdomainId}" data-name="${encodeURIComponent(topicName)}" onchange="onTopicToggle('${topicId}', '${subdomainId}')" class="item-checkbox mt-0.5 accent-white w-4 h-4 cursor-pointer">
              <div>
                <span class="text-xs font-semibold text-white">${topicName}</span>
                ${t.period ? `<span class="text-[10px] font-mono text-zinc-500 ml-2">(${t.period})</span>` : ''}
                ${t.evidence ? `<p class="text-[11px] text-zinc-400 mt-0.5">${t.evidence}</p>` : ''}
              </div>
            </label>

            <!-- Subtopics List -->
            ${subtopicsHtml ? `
              <div class="ml-6 pl-2 pt-1 border-l border-zinc-800/80 space-y-0.5">
                <span class="text-[10px] font-mono uppercase text-zinc-500 block">Subtopics:</span>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-1">${subtopicsHtml}</div>
              </div>
            ` : ''}
          </div>
        `;
      });

      subdomainsHtml += `
        <div class="ml-3 pl-3 border-l border-zinc-800/90 py-2 space-y-2">
          <label class="flex items-center gap-2 cursor-pointer font-medium text-xs text-zinc-200">
            <input type="checkbox" checked id="${subdomainId}" data-type="subdomain" data-domain-id="${domainId}" data-name="${encodeURIComponent(subdomainName)}" onchange="onSubdomainToggle('${subdomainId}', '${domainId}')" class="item-checkbox accent-white w-4 h-4 cursor-pointer">
            <span class="font-semibold text-zinc-100">${subdomainName}</span>
          </label>
          <div class="space-y-2">${topicsHtml}</div>
        </div>
      `;
    });

    domainCard.innerHTML = `
      <div class="border-b border-zinc-800/90 pb-2.5">
        <label class="flex items-center gap-2.5 cursor-pointer">
          <input type="checkbox" checked id="${domainId}" data-type="domain" data-name="${encodeURIComponent(domainName)}" onchange="onDomainToggle('${domainId}')" class="item-checkbox accent-white w-4 h-4 cursor-pointer">
          <span class="text-xs font-mono font-bold text-white uppercase tracking-wider">${domainName}</span>
        </label>
      </div>
      <div class="space-y-2">${subdomainsHtml}</div>
    `;

    container.appendChild(domainCard);
  });

  updateSelectedItemsHierarchy();
}

// Cascading Toggle Handlers
function onDomainToggle(domainId) {
  const domainCb = document.getElementById(domainId);
  const isChecked = domainCb.checked;
  // Toggle all children subdomains, topics, and subtopics inside this card
  const card = domainCb.closest(".p-4");
  card.querySelectorAll(".item-checkbox").forEach(cb => {
    cb.checked = isChecked;
  });
  updateSelectedItemsHierarchy();
}

function onSubdomainToggle(subdomainId, domainId) {
  const subdomainCb = document.getElementById(subdomainId);
  const isChecked = subdomainCb.checked;
  const container = subdomainCb.closest(".py-2");
  container.querySelectorAll(".item-checkbox").forEach(cb => {
    cb.checked = isChecked;
  });

  // Check parent domain if child is checked
  if (isChecked) {
    document.getElementById(domainId).checked = true;
  }
  updateSelectedItemsHierarchy();
}

function onTopicToggle(topicId, subdomainId) {
  const topicCb = document.getElementById(topicId);
  const isChecked = topicCb.checked;
  const container = topicCb.closest(".py-1\\.5");
  if (container) {
    container.querySelectorAll('input[data-type="subtopic"]').forEach(cb => {
      cb.checked = isChecked;
    });
  }

  // Check parents
  if (isChecked) {
    const subdomainCb = document.getElementById(subdomainId);
    if (subdomainCb) {
      subdomainCb.checked = true;
      const domainId = subdomainCb.getAttribute("data-domain-id");
      if (domainId) document.getElementById(domainId).checked = true;
    }
  }
  updateSelectedItemsHierarchy();
}

function onSubtopicToggle(subtopicId, topicId) {
  const subtopicCb = document.getElementById(subtopicId);
  if (subtopicCb.checked) {
    const topicCb = document.getElementById(topicId);
    if (topicCb) {
      topicCb.checked = true;
      const subdomainId = topicCb.getAttribute("data-subdomain-id");
      if (subdomainId) {
        const subdomainCb = document.getElementById(subdomainId);
        if (subdomainCb) {
          subdomainCb.checked = true;
          const domainId = subdomainCb.getAttribute("data-domain-id");
          if (domainId) document.getElementById(domainId).checked = true;
        }
      }
    }
  }
  updateSelectedItemsHierarchy();
}

function toggleAllCheckboxes(checked) {
  document.querySelectorAll(".item-checkbox").forEach(cb => {
    cb.checked = checked;
  });
  updateSelectedItemsHierarchy();
}

function updateSelectedItemsHierarchy() {
  onboardingState.selectedItems.domains.clear();
  onboardingState.selectedItems.subdomains.clear();
  onboardingState.selectedItems.topics.clear();
  onboardingState.selectedItems.subtopics.clear();

  document.querySelectorAll(".item-checkbox:checked").forEach(cb => {
    const type = cb.getAttribute("data-type");
    const name = decodeURIComponent(cb.getAttribute("data-name"));
    if (type === "domain") onboardingState.selectedItems.domains.add(name);
    else if (type === "subdomain") onboardingState.selectedItems.subdomains.add(name);
    else if (type === "topic") onboardingState.selectedItems.topics.add(name);
    else if (type === "subtopic") onboardingState.selectedItems.subtopics.add(name);
  });

  const counter = document.getElementById("selected-counter");
  if (counter) {
    const tCount = onboardingState.selectedItems.topics.size;
    const stCount = onboardingState.selectedItems.subtopics.size;
    const dCount = onboardingState.selectedItems.domains.size;
    counter.textContent = `${tCount} topics & ${stCount} subtopics selected across ${dCount} domains`;
  }
}

function handleStep3Submit() {
  if (onboardingState.selectedItems.topics.size === 0) {
    alert("Please select at least one topic to continue.");
    return;
  }

  // Format topics list with full hierarchy
  const topicsArray = Array.from(onboardingState.selectedItems.topics);
  const subtopicsArray = Array.from(onboardingState.selectedItems.subtopics);

  let formattedTopics = topicsArray.join(", ");
  if (subtopicsArray.length > 0) {
    formattedTopics += ` (Focus areas & subtopics: ${subtopicsArray.slice(0, 10).join(", ")})`;
  }

  // Construct Prompt 2
  const prompt2Template = `You will receive a list of topics (possibly nested as domains, subdomains, topics, and subtopics) after the line "TOPICS:". For each one, describe the unique experience I had with it, meaning what I specifically asked, tried, struggled with, decided, or learned, rather than a general description of the topic. Return everything as a single JSON object.

EVIDENCE SOURCES
- Use only the evidence in the pasted topics (such as evidence notes, periods, and subtopics) and, if you have access to it, my actual conversation history with you.
- Do not use general knowledge about the topic to fill gaps. A textbook explanation of the topic is not an experience.

VERBOSITY
- Medium means 3 to 5 sentences (about 50 to 100 words) per topic.
- Cover, where the evidence supports it: the situation or goal that prompted it, what I specifically did or asked, any problem, constraint, or decision involved, the outcome or what I took away, and what made this experience distinct from a generic version of the topic.
- Write in second person ("You asked...", "You were deciding between...") or neutral past tense. Do not use first person.

RULES
1. Cover every item in the input. Do not skip, merge, rename, or add topics.
2. Preserve the original hierarchy (domain > subdomain > topic > subtopic). If the input is a flat list, keep it flat.
3. Describe the experience for each topic and each subtopic. Keep subtopic experiences to 1 to 2 sentences.
4. Never invent details, outcomes, emotions, motivations, or events. If the evidence only shows that I asked a question, say that and stop. Do not infer how it turned out or how I felt.
5. If there is not enough evidence to describe a real experience, set "experience_available" to false, write a one-sentence statement of what is known (for example, "Only a single question about X is recorded"), and explain the gap in "note". Do not pad.
6. Mark how well each experience is supported in "confidence": "high", "medium", or "low".
7. Include the period if known, otherwise "unknown".
8. Do not include personal identifiers (passwords, API keys, phone numbers, addresses, full names of private individuals).
9. Output ONLY valid JSON. No markdown fences, no commentary before or after. Escape quotes and newlines properly, and use no trailing commas.

OUTPUT FORMAT
{
  "metadata": {
    "verbosity": "medium",
    "total_topics_described": 0,
    "topics_without_sufficient_evidence": 0
  },
  "domains": [
    {
      "domain": "Domain name",
      "subdomains": [
        {
          "subdomain": "Subdomain name",
          "topics": [
            {
              "topic": "Topic name",
              "experience_available": true,
              "experience": "3-5 sentence account of what I specifically did, asked, decided, or learned in this topic",
              "unique_angle": "One sentence on what made this experience distinct",
              "period": "YYYY-MM or range or unknown",
              "confidence": "high | medium | low",
              "subtopics": [
                {
                  "subtopic": "Subtopic name",
                  "experience": "1-2 sentence account of what I did or asked here"
                }
              ],
              "note": "Optional. Use only for evidence gaps or ambiguity, otherwise an empty string."
            }
          ]
        }
      ]
    }
  ]
}

Before finalizing, check that every input item appears exactly once, the hierarchy matches the input, every experience is grounded in the supplied evidence, the metadata counts are correct, and the JSON is valid.

TOPICS:
${formattedTopics}`;

  document.getElementById("prompt2-content").innerText = prompt2Template;
  goToStep(4);
}

// ==========================================
// STEP 4: PROMPT 2 (UNIQUE EXPERIENCES)
// ==========================================
function loadSampleExperiences() {
  const sampleExp = {
    "metadata": {
      "verbosity": "medium",
      "total_topics_described": 5,
      "topics_without_sufficient_evidence": 0
    },
    "domains": [
      {
        "domain": "Software Engineering & Systems Architecture",
        "subdomains": [
          {
            "subdomain": "Travel & Distributed Booking Infrastructure",
            "topics": [
              {
                "topic": "Hotel Research",
                "experience_available": true,
                "experience": "You explored the technical integration of boutique and luxury hotel inventory feeds across global aggregators. You focused on optimizing Redis caching strategies to prevent stale room availability while keeping latency under 120ms. You evaluated whether room amenity attributes should be pre-computed or extracted via vector embeddings.",
                "unique_angle": "Resolved room availability cache invalidation race conditions across distributed booking engines.",
                "period": "2024-05",
                "confidence": "high",
                "subtopics": [
                  {
                    "subtopic": "Property Caching",
                    "experience": "Implemented write-behind cache warming for peak morning booking traffic."
                  }
                ],
                "note": ""
              },
              {
                "topic": "Flight Ticketing & Aggregation Systems",
                "experience_available": true,
                "experience": "You analyzed real-time flight inventory synchronization across low-cost carriers and legacy GDS feeds (Sabre and Amadeus). You encountered significant latency bottlenecks when aggregating multi-city flight graphs during fare sales. You designed an asynchronous polling architecture that decoupled user pricing queries from synchronous airline booking holds.",
                "unique_angle": "Handled NDC API protocol inconsistencies without degrading search responsiveness.",
                "period": "2024-02",
                "confidence": "high",
                "subtopics": [
                  {
                    "subtopic": "GDS Sabre/Amadeus Connectivity",
                    "experience": "Benchmarked XML vs JSON transmission overhead across legacy reservation protocols."
                  }
                ],
                "note": ""
              }
            ]
          },
          {
            "subdomain": "Interviewing & Career Progression",
            "topics": [
              {
                "topic": "Google L5 Software Engineer Interview Loop",
                "experience_available": true,
                "experience": "You prepared extensively for distributed systems and system design interviews, focusing on Google-specific L5 rubric evaluation. You navigated 5 interview rounds with an emphasis on trade-off clarity, failure domain containment, and asynchronous consensus. You specifically practiced designing globally distributed key-value stores under network partition scenarios.",
                "unique_angle": "Focused on real-world operational fault tolerance and team leadership signals rather than pure algorithmic speed.",
                "period": "2023-08",
                "confidence": "high",
                "subtopics": [
                  {
                    "subtopic": "Distributed Key-Value Store Design",
                    "experience": "Analyzed Paxos vs Raft consensus trade-offs under high write contention."
                  }
                ],
                "note": ""
              },
              {
                "topic": "Global Technical Leadership Opportunities",
                "experience_available": true,
                "experience": "You evaluated international relocation packages and Staff+ engineering compensation bands across Amsterdam, London, and Zurich. You analyzed the Dutch 30% tax ruling requirements and compared net take-home pay against Swiss tax structures. You weighed the pros and cons of equity vesting schedules during European macroeconomic downturns.",
                "unique_angle": "Created a multi-currency tax and net disposable income model comparing NL, UK, and CH.",
                "period": "2024-09",
                "confidence": "high",
                "subtopics": [
                  {
                    "subtopic": "EU Relocation Tax Benefits",
                    "experience": "Verified recruitment radius eligibility rules for Dutch 30% ruling contracts."
                  }
                ],
                "note": ""
              }
            ]
          }
        ]
      },
      {
        "domain": "Venture & Product Strategy",
        "subdomains": [
          {
            "subdomain": "AI Avatars & Creator Monetization",
            "topics": [
              {
                "topic": "Saariv Development & Strategy",
                "experience_available": true,
                "experience": "You conceptualized Saariv to allow founders, immigrants, and advisors to monetize their chat history without giving up calendar hours. You designed the 2-prompt extraction workflow to distill knowledge safely from conversational logs. You engineered the grounding pipeline to anchor responses in authentic lived experiences rather than generic chatbot answers.",
                "unique_angle": "Pioneered the zero-upfront commission model coupled with private session sandboxing.",
                "period": "2025-01",
                "confidence": "high",
                "subtopics": [
                  {
                    "subtopic": "2-Prompt Knowledge Distillation",
                    "experience": "Refined the prompt taxonomy to isolate unique decisions and lessons."
                  }
                ],
                "note": ""
              }
            ]
          }
        ]
      }
    ]
  };

  document.getElementById("step4_pasted_json").value = JSON.stringify(sampleExp, null, 2);
}

async function handleStep4Submit() {
  const errorDiv = document.getElementById("step4_error");
  errorDiv.classList.add("hidden");
  const btn = document.getElementById("build-avatar-btn");

  const rawJson = document.getElementById("step4_pasted_json").value.trim();
  if (!rawJson) {
    errorDiv.textContent = "Please paste the chatbot's experience JSON output or click 'Load Sample Experience'.";
    errorDiv.classList.remove("hidden");
    return;
  }

  let parsed;
  try {
    parsed = JSON.parse(rawJson);
  } catch (err) {
    errorDiv.textContent = `JSON Syntax Error: ${err.message}. Please verify the output is valid JSON.`;
    errorDiv.classList.remove("hidden");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Initializing Avatar...`;

  try {
    const res = await fetch("/api/onboarding/step4", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: onboardingState.sessionId,
        selected_topics: Array.from(onboardingState.selectedItems.topics),
        experiences_json: parsed
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      errorDiv.textContent = data.message || "Failed to index experiences.";
      errorDiv.classList.remove("hidden");
      btn.disabled = false;
      btn.innerHTML = `<span>Build My Avatar & Open Playground</span>`;
      return;
    }

    onboardingState.indexedCount = data.indexed_count || 5;
    setupPlayground(data.sample_topics || Array.from(onboardingState.selectedItems.topics));
    goToStep(5);
  } catch (err) {
    setupPlayground(Array.from(onboardingState.selectedItems.topics));
    goToStep(5);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Build My Avatar & Open Playground</span>`;
  }
}

// ==========================================
// STEP 5: PERSONAL PLAYGROUND (CLEAN UI, NO RAG WORD, WITH BACK CONTROLS)
// ==========================================
function setupPlayground(topics) {
  const name = `${onboardingState.firstName || 'Creator'} ${onboardingState.lastName || ''}`.trim();
  
  const titleEl = document.getElementById("avatar-title");
  if (titleEl) titleEl.textContent = `${name}'s Living Biography Avatar`;

  const creatorNameEl = document.getElementById("playground-creator-name");
  if (creatorNameEl) creatorNameEl.textContent = name;

  const indexedSummaryEl = document.getElementById("playground-indexed-summary");
  if (indexedSummaryEl) {
    const count = onboardingState.indexedCount || topics.length;
    indexedSummaryEl.textContent = `${count} lived experiences indexed and ready for testing.`;
  }

  const chipsContainer = document.getElementById("playground-prompt-chips");
  if (chipsContainer) {
    chipsContainer.innerHTML = topics.slice(0, 4).map(t => {
      const topicTitle = typeof t === 'string' ? t : t.topic || '';
      return `<button type="button" onclick="askPlaygroundQuestion('Tell me about your experience with ${topicTitle.replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-300 transition-colors">"Tell me about ${topicTitle}"</button>`;
    }).join("");
  }

  if (window.lucide) {
    lucide.createIcons();
  }
}

function askPlaygroundQuestion(q) {
  const input = document.getElementById("playground-query-input");
  if (input) {
    input.value = q;
    handlePlaygroundQuery(new Event("submit"));
  }
}

async function handlePlaygroundQuery(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("playground-query-input");
  if (!input) return;
  const query = input.value.trim();
  if (!query) return;

  const responseBox = document.getElementById("playground-response-box");
  const btn = document.getElementById("playground-query-btn");
  const retrievedBadge = document.getElementById("retrieved-badge");
  const topicNameSpan = document.getElementById("retrieved-topic-name");

  responseBox.innerHTML = `<span class="text-zinc-400 font-mono text-xs">Finding relevant experience and generating answer...</span>`;
  btn.disabled = true;

  try {
    const res = await fetch("/api/playground/rag-query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: onboardingState.sessionId,
        query: query
      })
    });
    const data = await res.json();
    responseBox.textContent = data.reply;

    if (data.retrieved_topic) {
      topicNameSpan.textContent = data.retrieved_topic;
      retrievedBadge.classList.remove("hidden");
    }
  } catch (err) {
    responseBox.textContent = "Unable to connect to search endpoint. Please verify server status.";
  } finally {
    btn.disabled = false;
    input.value = "";
  }
}

// ==========================================
// ANIMATED EXPERIENCE-TO-EARNINGS TICKER (FOR HOMEPAGE)
// ==========================================
const sampleInquiries = [
  {
    sender: "Rohan K. (Pune, India)",
    question: "How did you find housing in Amsterdam without local Dutch credit history?",
    fee: 8.00,
    time: "2 mins ago"
  },
  {
    sender: "Ananya M. (Bengaluru, India)",
    question: "What was your preparation strategy for the Google L5 system design loop?",
    fee: 12.00,
    time: "5 mins ago"
  },
  {
    sender: "Vikram S. (Hyderabad, India)",
    question: "How did you handle the 30% tax ruling paperwork before signing your offer?",
    fee: 8.00,
    time: "11 mins ago"
  },
  {
    sender: "Sneha P. (Delhi, India)",
    question: "How did you resolve room availability cache invalidation in your travel systems?",
    fee: 15.00,
    time: "18 mins ago"
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

  if (cardEl) {
    cardEl.classList.remove("animate-income-flash");
    void cardEl.offsetWidth;
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

if (document.getElementById("anim-question")) {
  setInterval(triggerNextInquiry, 5500);
}

// ==========================================
// WAITLIST SUBMISSION
// ==========================================
async function handleWaitlistSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("wl_name").value.trim();
  const email = document.getElementById("wl_email").value.trim();
  const successBox = document.getElementById("waitlist-success");

  try {
    const res = await fetch("/api/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, email: email, profile_type: "Living Biography Waitlist" })
    });
    const data = await res.json();
    if (successBox) successBox.classList.remove("hidden");
  } catch (err) {
    if (successBox) successBox.classList.remove("hidden");
  }
}

// On Page Load: Initialize stepper if try.html panel is present
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("step-panel-1")) {
    goToStep(1);
  }
});

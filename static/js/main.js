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
// STEPPER NAVIGATION & PROGRESS BAR
// ==========================================
function goToStep(stepNum) {
  // Hide all panels
  for (let i = 1; i <= 6; i++) {
    const panel = document.getElementById(`step-panel-${i}`);
    if (panel) panel.classList.add("hidden");
  }

  // Show target panel
  const activePanel = document.getElementById(`step-panel-${stepNum}`);
  if (activePanel) {
    activePanel.classList.remove("hidden");
    activePanel.classList.add("animate-fade-in");
    activePanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Update progress bar
  updateProgressBar(stepNum);

  // Reset loader states when navigating
  resetLoaderStates();

  if (window.lucide) {
    lucide.createIcons();
  }
}

function resetLoaderStates() {
  // Reset Step 1 loader
  const step1Btn = document.getElementById("step1-submit-btn");
  const step1Text = document.getElementById("step1-btn-text");
  const step1Loader = document.getElementById("step1-btn-loader");
  const step1Arrow = document.getElementById("step1-btn-arrow");
  if (step1Btn) step1Btn.disabled = false;
  if (step1Text) step1Text.classList.remove("hidden");
  if (step1Loader) step1Loader.classList.add("hidden");
  if (step1Arrow) step1Arrow.classList.remove("hidden");

  // Reset Step 5 loader
  const step5Btn = document.getElementById("step5-submit-btn");
  const step5Text = document.getElementById("step5-btn-text");
  const step5Loader = document.getElementById("step5-btn-loader");
  const step5Arrow = document.getElementById("step5-btn-arrow");
  if (step5Btn) step5Btn.disabled = false;
  if (step5Text) step5Text.classList.remove("hidden");
  if (step5Loader) step5Loader.classList.add("hidden");
  if (step5Arrow) step5Arrow.classList.remove("hidden");
}

function updateProgressBar(currentStep) {
  const percentage = Math.round((currentStep / 6) * 100);
  
  const progressBarFill = document.getElementById("progress-bar-fill");
  const progressPercentage = document.getElementById("progress-percentage");
  
  if (progressBarFill) {
    progressBarFill.style.width = `${percentage}%`;
  }
  
  if (progressPercentage) {
    progressPercentage.textContent = `${percentage}%`;
  }

  // Update step indicators
  for (let i = 1; i <= 6; i++) {
    const stepEl = document.querySelector(`.progress-step:nth-child(${i})`);
    if (stepEl) {
      stepEl.classList.remove("active", "completed");
      if (i < currentStep) {
        stepEl.classList.add("completed");
      } else if (i === currentStep) {
        stepEl.classList.add("active");
      }
    }
  }
}

// Copy prompt helper
function copyPrompt(elementId, btnId) {
  const content = document.getElementById(elementId).innerText;
  navigator.clipboard.writeText(content).then(() => {
    const btn = document.getElementById(btnId);
    if (btn) {
      const originalHTML = btn.innerHTML;
      btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-green-600"></i> Copied!`;
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

  // Show loader
  const submitBtn = document.getElementById("step1-submit-btn");
  const btnText = document.getElementById("step1-btn-text");
  const btnLoader = document.getElementById("step1-btn-loader");
  const btnArrow = document.getElementById("step1-btn-arrow");
  
  if (submitBtn) submitBtn.disabled = true;
  if (btnText) btnText.classList.add("hidden");
  if (btnLoader) btnLoader.classList.remove("hidden");
  if (btnArrow) btnArrow.classList.add("hidden");

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
  } finally {
    // Hide loader
    if (submitBtn) submitBtn.disabled = false;
    if (btnText) btnText.classList.remove("hidden");
    if (btnLoader) btnLoader.classList.add("hidden");
    if (btnArrow) btnArrow.classList.remove("hidden");
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
    domainCard.className = "hierarchy-domain";

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
            <label class="flex items-center gap-2 py-1.5 px-3 rounded-md hover:bg-white cursor-pointer text-xs text-gray-700 transition-colors">
              <input type="checkbox" checked id="${subtopicId}" data-type="subtopic" data-topic-id="${topicId}" data-name="${encodeURIComponent(stName)}" onchange="onSubtopicToggle('${subtopicId}', '${topicId}')" class="item-checkbox accent-blue-600 w-4 h-4 cursor-pointer rounded">
              <span class="font-medium">${stName}</span>
            </label>
          `;
        });

        topicsHtml += `
          <div class="ml-4 pl-4 border-l-2 border-gray-300 py-2 space-y-2">
            <label class="flex items-start gap-3 cursor-pointer group">
              <input type="checkbox" checked id="${topicId}" data-type="topic" data-subdomain-id="${subdomainId}" data-name="${encodeURIComponent(topicName)}" onchange="onTopicToggle('${topicId}', '${subdomainId}')" class="item-checkbox mt-1 accent-blue-600 w-4 h-4 cursor-pointer rounded">
              <div class="flex-1">
                <span class="text-sm font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">${topicName}</span>
                ${t.period ? `<span class="text-xs font-mono text-gray-500 ml-2 bg-gray-200 px-2 py-0.5 rounded">${t.period}</span>` : ''}
                ${t.evidence ? `<p class="text-xs text-gray-600 mt-1 leading-relaxed">${t.evidence}</p>` : ''}
              </div>
            </label>

            ${subtopicsHtml ? `
              <div class="ml-6 mt-3 space-y-1">
                <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-2">Subtopics</span>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-1">${subtopicsHtml}</div>
              </div>
            ` : ''}
          </div>
        `;
      });

      subdomainsHtml += `
        <div class="ml-3 pl-4 border-l-2 border-blue-200 py-3 space-y-3">
          <label class="flex items-center gap-3 cursor-pointer group">
            <input type="checkbox" checked id="${subdomainId}" data-type="subdomain" data-domain-id="${domainId}" data-name="${encodeURIComponent(subdomainName)}" onchange="onSubdomainToggle('${subdomainId}', '${domainId}')" class="item-checkbox accent-blue-600 w-4 h-4 cursor-pointer rounded">
            <span class="text-sm font-bold text-gray-900 group-hover:text-blue-600 transition-colors">${subdomainName}</span>
          </label>
          <div class="space-y-3">${topicsHtml}</div>
        </div>
      `;
    });

    domainCard.innerHTML = `
      <div class="hierarchy-domain-header">
        <input type="checkbox" checked id="${domainId}" data-type="domain" data-name="${encodeURIComponent(domainName)}" onchange="onDomainToggle('${domainId}')" class="item-checkbox accent-blue-600 w-5 h-5 cursor-pointer rounded">
        <span class="hierarchy-domain-label">${domainName}</span>
      </div>
      <div class="space-y-4">${subdomainsHtml}</div>
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
    const dCount = onboardingState.selectedItems.domains.size;
    const sdCount = onboardingState.selectedItems.subdomains.size;
    const tCount = onboardingState.selectedItems.topics.size;
    const stCount = onboardingState.selectedItems.subtopics.size;
    
    const totalSelected = dCount + sdCount + tCount + stCount;
    
    if (totalSelected === 0) {
      counter.textContent = "No items selected";
    } else {
      const parts = [];
      if (dCount > 0) parts.push(`${dCount} domain${dCount !== 1 ? 's' : ''}`);
      if (sdCount > 0) parts.push(`${sdCount} subdomain${sdCount !== 1 ? 's' : ''}`);
      if (tCount > 0) parts.push(`${tCount} topic${tCount !== 1 ? 's' : ''}`);
      if (stCount > 0) parts.push(`${stCount} subtopic${stCount !== 1 ? 's' : ''}`);
      
      counter.textContent = parts.join(", ") + " selected";
    }
  }
}

function handleStep3Submit() {
  // Check if at least one item is selected from any category
  const totalSelected = 
    onboardingState.selectedItems.topics.size + 
    onboardingState.selectedItems.subtopics.size + 
    onboardingState.selectedItems.domains.size + 
    onboardingState.selectedItems.subdomains.size;
  
  if (totalSelected === 0) {
    alert("Please select at least one domain, subdomain, topic, or subtopic to continue.");
    return;
  }

  // Format topics list with full hierarchy
  const topicsArray = Array.from(onboardingState.selectedItems.topics);
  const subtopicsArray = Array.from(onboardingState.selectedItems.subtopics);
  const domainsArray = Array.from(onboardingState.selectedItems.domains);
  const subdomainsArray = Array.from(onboardingState.selectedItems.subdomains);

  // Build a comprehensive list including all selected items
  let formattedTopics = "";
  
  // Include domains if no specific topics/subtopics selected
  if (topicsArray.length === 0 && subtopicsArray.length === 0) {
    // Use domains and subdomains
    formattedTopics = domainsArray.join(", ");
    if (subdomainsArray.length > 0) {
      formattedTopics += (formattedTopics ? ", " : "") + subdomainsArray.join(", ");
    }
  } else {
    // Use topics and subtopics
    formattedTopics = topicsArray.join(", ");
    if (subtopicsArray.length > 0) {
      formattedTopics += ` (Focus areas & subtopics: ${subtopicsArray.slice(0, 10).join(", ")})`;
    }
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

  // Collect all selected items
  const allSelectedItems = {
    domains: Array.from(onboardingState.selectedItems.domains),
    subdomains: Array.from(onboardingState.selectedItems.subdomains),
    topics: Array.from(onboardingState.selectedItems.topics),
    subtopics: Array.from(onboardingState.selectedItems.subtopics)
  };

  try {
    const res = await fetch("/api/onboarding/step4", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: onboardingState.sessionId,
        selected_items: allSelectedItems,
        experiences_json: parsed
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      errorDiv.textContent = data.message || "Failed to index experiences.";
      errorDiv.classList.remove("hidden");
      return;
    }

    onboardingState.indexedCount = data.indexed_count || 5;
    goToStep(5); // Go to unique experience step
  } catch (err) {
    goToStep(5); // Go to unique experience step
  }
}

// ==========================================
// STEP 5: UNIQUE EXPERIENCE (TEXT OR FILE)
// ==========================================

// Store uploaded files content
let uploadedFilesContent = [];

async function handleFileUpload(event) {
  const files = Array.from(event.target.files);
  if (!files.length) return;

  const filenamesContainer = document.getElementById("step5_filenames");
  filenamesContainer.innerHTML = "";
  uploadedFilesContent = [];

  for (const file of files) {
    const ext = file.name.split('.').pop().toLowerCase();
    let text = "";

    try {
      if (ext === 'pdf') {
        text = await extractTextFromPDF(file);
      } else if (ext === 'docx' || ext === 'doc') {
        // Mark DOCX files for server processing - can't read client-side
        text = "[DOCX_FILE]";
      } else {
        // Text files (.txt, .md, .json, .rtf)
        text = await file.text();
      }

      uploadedFilesContent.push({
        filename: file.name,
        content: text,
        type: ext
      });

      // Show file name with checkmark
      const fileEl = document.createElement("div");
      fileEl.className = "flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-md";
      const icon = (ext === 'docx' || ext === 'doc') ? 'file-text' : 'check-circle';
      fileEl.innerHTML = `
        <i data-lucide="${icon}" class="w-4 h-4"></i>
        <span>${file.name}</span>
        <span class="text-xs text-gray-500">(${(file.size / 1024).toFixed(1)} KB)</span>
      `;
      filenamesContainer.appendChild(fileEl);
    } catch (err) {
      const errorEl = document.createElement("div");
      errorEl.className = "flex items-center gap-2 text-sm text-red-700 bg-red-50 px-3 py-1.5 rounded-md";
      errorEl.innerHTML = `
        <i data-lucide="alert-circle" class="w-4 h-4"></i>
        <span>Failed to read ${file.name}</span>
      `;
      filenamesContainer.appendChild(errorEl);
    }
  }

  // Refresh icons
  if (window.lucide) lucide.createIcons();
}

async function extractTextFromPDF(file) {
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  
  let fullText = "";
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const textContent = await page.getTextContent();
    const pageText = textContent.items.map(item => item.str).join(" ");
    fullText += pageText + "\n";
  }
  
  return fullText;
}

async function handleStep5Submit() {
  const errorDiv = document.getElementById("step5_error");
  errorDiv.classList.add("hidden");

  const customText = document.getElementById("step5_custom_text").value.trim();
  const topicTag = document.getElementById("step5_topic_tag").value.trim() || "Unique Experience";

  // Show loader
  const submitBtn = document.getElementById("step5-submit-btn");
  const btnText = document.getElementById("step5-btn-text");
  const btnLoader = document.getElementById("step5-btn-loader");
  const btnArrow = document.getElementById("step5-btn-arrow");
  
  if (submitBtn) submitBtn.disabled = true;
  if (btnText) btnText.classList.add("hidden");
  if (btnLoader) btnLoader.classList.remove("hidden");
  if (btnArrow) btnArrow.classList.add("hidden");

  // Get all selected items for playground
  const allSelectedItems = [
    ...Array.from(onboardingState.selectedItems.domains),
    ...Array.from(onboardingState.selectedItems.subdomains),
    ...Array.from(onboardingState.selectedItems.topics),
    ...Array.from(onboardingState.selectedItems.subtopics)
  ];

  // Check if we have DOCX files that need server processing
  const hasDocxFiles = uploadedFilesContent.some(f => f.type === 'docx' || f.type === 'doc');
  const docxFiles = uploadedFilesContent.filter(f => f.type === 'docx' || f.type === 'doc');
  const otherContent = uploadedFilesContent.filter(f => f.type !== 'docx' && f.type !== 'doc');

  // Combine custom text and non-DOCX file contents
  let combinedExperience = customText;
  
  if (otherContent.length > 0) {
    const fileContents = otherContent.map(f => `\n\n--- Content from ${f.filename} ---\n${f.content}`).join("");
    combinedExperience += fileContents;
  }

  // It's okay to skip this step - just proceed to playground
  if (!combinedExperience && docxFiles.length === 0) {
    setupPlayground(allSelectedItems);
    goToStep(6);
    return;
  }

  try {
    // If we have DOCX files, send via FormData
    if (docxFiles.length > 0) {
      const fileInput = document.getElementById('step5_file_upload');
      const formData = new FormData();
      formData.append("session_id", onboardingState.sessionId);
      formData.append("custom_experience", combinedExperience);
      formData.append("topic_tag", topicTag);
      
      // Append the actual DOCX files from the file input
      const allFiles = Array.from(fileInput.files);
      for (const file of allFiles) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext === 'docx' || ext === 'doc') {
          formData.append("files", file);
        }
      }
      
      const res = await fetch("/api/onboarding/step5-files", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.message || "Failed to process files");
      }
      onboardingState.indexedCount = data.indexed_count || allSelectedItems.length;
    } else {
      // Regular text/PDF content - send as JSON
      const res = await fetch("/api/onboarding/step5", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: onboardingState.sessionId,
          custom_experience: combinedExperience,
          topic_tag: topicTag
        })
      });
      const data = await res.json();
      onboardingState.indexedCount = data.indexed_count || allSelectedItems.length;
    }

    setupPlayground(allSelectedItems);
    goToStep(6);
  } catch (err) {
    setupPlayground(allSelectedItems);
    goToStep(6);
  } finally {
    // Hide loader
    if (submitBtn) submitBtn.disabled = false;
    if (btnText) btnText.classList.remove("hidden");
    if (btnLoader) btnLoader.classList.add("hidden");
    if (btnArrow) btnArrow.classList.remove("hidden");
  }
}

// ==========================================
// STEP 6: PERSONAL PLAYGROUND (CHATGPT-STYLE UI WITH TOPICS SIDEBAR)
// ==========================================
function setupPlayground(topics) {
  const name = `${onboardingState.firstName || 'Creator'} ${onboardingState.lastName || ''}`.trim();
  const initials = name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
  
  // Update avatar initials
  const avatarInitialEl = document.getElementById("chat-avatar-initial");
  if (avatarInitialEl) avatarInitialEl.textContent = initials;
  
  const welcomeInitialEl = document.getElementById("chat-welcome-initial");
  if (welcomeInitialEl) welcomeInitialEl.textContent = initials;

  const creatorNameEl = document.getElementById("chat-creator-name");
  if (creatorNameEl) creatorNameEl.textContent = name;

  // Populate topics sidebar
  const topicsListEl = document.getElementById("playground-topics-list");
  const topicsCountBadge = document.getElementById("topics-count-badge");
  
  if (topicsListEl && topics.length > 0) {
    // Organize topics by domain/subdomain/topic hierarchy
    const allTopics = [
      ...Array.from(onboardingState.selectedItems.domains).map(d => ({ name: d, type: 'domain' })),
      ...Array.from(onboardingState.selectedItems.subdomains).map(s => ({ name: s, type: 'subdomain' })),
      ...Array.from(onboardingState.selectedItems.topics).map(t => ({ name: t, type: 'topic' })),
      ...Array.from(onboardingState.selectedItems.subtopics).map(st => ({ name: st, type: 'subtopic' }))
    ];
    
    if (topicsCountBadge) {
      topicsCountBadge.textContent = `${allTopics.length} topic${allTopics.length !== 1 ? 's' : ''}`;
    }
    
    topicsListEl.innerHTML = allTopics.map(item => {
      const typeIcon = item.type === 'domain' ? 'folder' : 
                       item.type === 'subdomain' ? 'folder-open' : 
                       item.type === 'topic' ? 'message-square' : 'corner-down-right';
      const typeColor = item.type === 'domain' ? 'text-blue-600 bg-blue-50' : 
                        item.type === 'subdomain' ? 'text-purple-600 bg-purple-50' : 
                        item.type === 'topic' ? 'text-gray-600 bg-gray-100' : 'text-gray-500 bg-gray-50';
      
      return `
        <button 
          type="button"
          onclick="askPlaygroundQuestion('Tell me about your experience with ${item.name.replace(/'/g, "\\'")}')"
          class="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white transition-colors text-left group"
        >
          <div class="w-6 h-6 rounded flex items-center justify-center ${typeColor} flex-shrink-0">
            <i data-lucide="${typeIcon}" class="w-3 h-3"></i>
          </div>
          <span class="text-xs text-gray-700 group-hover:text-gray-900 truncate flex-1">${item.name}</span>
          <i data-lucide="chevron-right" class="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"></i>
        </button>
      `;
    }).join("");
  } else if (topicsListEl) {
    topicsListEl.innerHTML = `
      <div class="text-center py-8">
        <i data-lucide="info" class="w-8 h-8 text-gray-300 mx-auto mb-2"></i>
        <p class="text-xs text-gray-500">No topics selected</p>
      </div>
    `;
    if (topicsCountBadge) topicsCountBadge.textContent = "0 topics";
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

function handleChatKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handlePlaygroundQuery(event);
  }
}

function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}

async function handlePlaygroundQuery(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("playground-query-input");
  if (!input) return;
  const query = input.value.trim();
  if (!query) return;

  const messagesContainer = document.getElementById("chat-messages");
  const btn = document.getElementById("playground-query-btn");
  const name = `${onboardingState.firstName || 'Creator'} ${onboardingState.lastName || ''}`.trim();
  const initials = name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);

  btn.disabled = true;

  // Add user message
  const userMsgHtml = `
    <div class="flex gap-3 justify-end">
      <div class="flex-1 max-w-2xl">
        <div class="bg-gray-900 text-white rounded-2xl rounded-tr-md px-4 py-3">
          <p class="text-sm leading-relaxed">${query.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>
        </div>
      </div>
    </div>
  `;
  messagesContainer.querySelector('.space-y-4').insertAdjacentHTML('beforeend', userMsgHtml);

  // Add loading message
  const loadingMsgHtml = `
    <div class="flex gap-3" id="loading-message">
      <div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 mt-1">
        <span>${initials}</span>
      </div>
      <div class="flex-1 bg-white rounded-2xl rounded-tl-md px-4 py-3 border border-gray-200 shadow-sm">
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style="animation-delay: 0ms"></div>
          <div class="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style="animation-delay: 150ms"></div>
          <div class="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style="animation-delay: 300ms"></div>
        </div>
      </div>
    </div>
  `;
  messagesContainer.querySelector('.space-y-4').insertAdjacentHTML('beforeend', loadingMsgHtml);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

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

    // Remove loading message
    const loadingMsg = document.getElementById("loading-message");
    if (loadingMsg) loadingMsg.remove();

    // Add assistant response
    const replyHtml = `
      <div class="flex gap-3">
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 mt-1">
          <span>${initials}</span>
        </div>
        <div class="flex-1 bg-white rounded-2xl rounded-tl-md px-4 py-3 border border-gray-200 shadow-sm">
          <p class="text-gray-800 text-sm leading-relaxed">${data.reply.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')}</p>
          ${data.retrieved_topic ? `
            <div class="mt-2 pt-2 border-t border-gray-100">
              <span class="text-xs text-gray-500">Retrieved from: <span class="font-medium text-gray-700">${data.retrieved_topic}</span></span>
            </div>
          ` : ''}
        </div>
      </div>
    `;
    messagesContainer.querySelector('.space-y-4').insertAdjacentHTML('beforeend', replyHtml);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

  } catch (err) {
    // Remove loading message
    const loadingMsg = document.getElementById("loading-message");
    if (loadingMsg) loadingMsg.remove();

    // Add error message
    const errorMsgHtml = `
      <div class="flex gap-3">
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 mt-1">
          <span>${initials}</span>
        </div>
        <div class="flex-1 bg-red-50 border border-red-200 rounded-2xl rounded-tl-md px-4 py-3">
          <p class="text-red-800 text-sm">Unable to connect to the avatar. Please check your connection and try again.</p>
        </div>
      </div>
    `;
    messagesContainer.querySelector('.space-y-4').insertAdjacentHTML('beforeend', errorMsgHtml);
  } finally {
    btn.disabled = false;
    input.value = "";
    input.style.height = 'auto';
    if (window.lucide) lucide.createIcons();
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
  const submitBtn = document.getElementById("waitlist-submit-btn");
  const btnText = document.getElementById("waitlist-btn-text");
  const btnLoader = document.getElementById("waitlist-btn-loader");
  
  if (!name || !email) {
    return;
  }

  // Show loader
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  if (btnText) {
    btnText.classList.add("hidden");
  }
  if (btnLoader) {
    btnLoader.classList.remove("hidden");
  }

  try {
    const res = await fetch("/api/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        name: name, 
        email: email, 
        profile_type: "Living Biography Waitlist" 
      })
    });
    const data = await res.json();
    
    // Show success message
    if (successBox) {
      successBox.classList.remove("hidden");
      successBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    
    // Clear form
    document.getElementById("wl_name").value = "";
    document.getElementById("wl_email").value = "";
    
  } catch (err) {
    // Show success message even on error (fail gracefully)
    if (successBox) {
      successBox.classList.remove("hidden");
    }
  } finally {
    // Hide loader
    if (submitBtn) {
      submitBtn.disabled = false;
    }
    if (btnText) {
      btnText.classList.remove("hidden");
    }
    if (btnLoader) {
      btnLoader.classList.add("hidden");
    }
  }
}

// On Page Load: Initialize stepper if try.html panel is present
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("step-panel-1")) {
    goToStep(1);
  }
});

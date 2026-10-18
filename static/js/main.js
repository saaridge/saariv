// Saariv — Onboarding Stepper, Knowledge Grounding & Living Biography Engine

let onboardingState = {
  sessionId: localStorage.getItem("saariv_session_id") || null,
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

  if (stepNum === 6) refreshKnowledgeStatus();

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

        first_name: firstName,
        last_name: lastName,
        email: email,
        linkedin_url: linkedinUrl
      })
    });
    const data = await res.json();
    if (data.ok && data.session_id) adoptServerSession(data);
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
    "domains": [
      {
        "domain": "Software Engineering & Systems Architecture",
        "subdomains": [
          {
            "subdomain": "Travel & Distributed Booking Infrastructure",
            "topics": [
              {
                "topic": "Hotel Research",
                "subtopics": ["Property Caching", "Amenity Tag Extraction", "Review Sentiment"]
              },
              {
                "topic": "Flight Ticketing & Aggregation Systems",
                "subtopics": ["GDS Sabre/Amadeus Connectivity", "Multi-City Fare Graph", "Real-Time Seat Hold Locks"]
              }
            ]
          },
          {
            "subdomain": "Interviewing & Career Progression",
            "topics": [
              {
                "topic": "Google L5 Software Engineer Interview Loop",
                "subtopics": ["Distributed Key-Value Store Design", "Behavioral Leadership Signals", "Code Quality & Testing"]
              },
              {
                "topic": "Global Technical Leadership Opportunities",
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

        taxonomy_json: parsed
      })
    });
    const data = await res.json();
    if (data.ok && data.session_id) adoptServerSession(data);
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
      formattedTopics += ` (Focus areas & subtopics: ${subtopicsArray.join(", ")})`;
    }
  }

  // Construct Prompt 2
  const prompt2Template = `You will receive a list of topics (possibly nested as domains, subdomains, topics, and subtopics) after the line "TOPICS:". For each one, extract all relevant information I personally shared in messages I wrote. Capture what I said, asked, described, tried, struggled with, planned, decided, or explicitly reported learning. The output must contain my contributions, not the chatbot's answers. Tell it as a readable, factual story in prose instead of JSON.

EVIDENCE SOURCES
- Use ONLY messages authored by me (the user) in the conversation history you can actually access, or original user messages I paste with the topics.
- Exclude ALL assistant-authored content, including ChatGPT's replies, advice, explanations, examples, proposed plans, generated stories, and summaries. Apply this rule to every chatbot, including Claude, Gemini, and Grok.
- Never attribute something the assistant said to me. An assistant's suggestion is not evidence that I tried it, agreed with it, learned it, or achieved its predicted outcome. Include an action or outcome only when I explicitly reported it in my own words.
- Topic names, taxonomy evidence notes, and chatbot-generated summaries are organizational aids, not proof of what I said. Use them to locate original user messages; do not copy unsupported claims from them.
- Do not fill gaps with general knowledge, inferred beliefs, or assistant replies. If original user messages are unavailable, mark the evidence gap instead of reconstructing them.

VERBOSITY
- Be comprehensive: preserve every distinct, relevant detail from my messages for each selected topic and subtopic. Use as much space as needed; do not impose a sentence or word limit that drops information.
- Include my stated context, questions, requests, opinions, preferences, goals, constraints, attempts, decisions, corrections, and explicitly reported outcomes. Preserve chronology and changes in my position where known.
- Combine repeated statements only when no distinct information is lost. A question establishes only that I asked it, not that I knew the answer or followed the assistant's advice.
- Write in the first person, in my own voice ("I asked...", "I was deciding between...", "My main concern was..."), as if I am recounting my own experience. Do not use second person ("you") or third person.

RULES
1. Cover every selected topic and subtopic. Do not add unrelated topics or omit distinct details I shared.
2. Write connected story paragraphs. Use a simple heading such as "## Topic name" when changing topics; weave the related subtopics into the narrative.
3. Tell what I actually said, asked, tried, planned, decided, or explicitly reported learning. Preserve the sequence of events only when my messages establish it.
4. Never invent details, outcomes, emotions, motivations, or events. If I only asked a question, describe that question without adding the assistant's answer or implying I acted on it.
5. If original user messages are unavailable for a topic, say so briefly in that section. Do not fill the gap with chatbot content.
6. Include dates or periods naturally in the story only when I stated them. Do not add confidence scores, metadata, or evidence tables.
7. Do not include personal identifiers (passwords, API keys, phone numbers, addresses, full names of private individuals).
8. Output only the story, optionally with topic headings. No JSON, code fences around the story, bullet-point summaries, or commentary before or after it.

OUTPUT STYLE
## Topic name
Write the complete story of what I shared about this topic in connected paragraphs, in my own first-person voice ("I ..."), including the related subtopic details. Use as many paragraphs as needed to preserve my contributions.

Before finalizing, check that every selected topic and subtopic is covered, the whole story is written in the first person in my own voice, every factual claim comes from an original user-authored message, no distinct relevant user information was omitted, and no assistant-authored content was included or attributed to me.

TOPICS:
${formattedTopics}`;

  document.getElementById("prompt2-content").innerText = prompt2Template;
  goToStep(4);
}

// ==========================================
// STEP 4: PROMPT 2 (UNIQUE EXPERIENCES)
// ==========================================
function loadSampleExperiences() {
  const sampleStory = `## Hotel Research
I asked about integrating boutique and luxury hotel inventory feeds. My main concerns were stale room availability and the latency of property searches. I explored Redis caching and asked whether room amenities should be prepared in advance or extracted when needed.

## Flight Ticketing & Aggregation Systems
I compared low-cost carrier APIs with legacy GDS feeds. I described slow searches across multi-city routes and asked how to keep pricing queries responsive while managing seat holds. My questions included Sabre and Amadeus connectivity and differences between reservation protocols.

## Google L5 Software Engineer Interview Loop
I said I was preparing for system design interviews. I asked about distributed key-value stores, failure handling, and explaining engineering trade-offs. I also wanted to practice communicating leadership decisions during the interview.

## Global Technical Leadership Opportunities
I compared engineering opportunities in Amsterdam, London, and Zurich. I asked about relocation packages, compensation, and the effect of different tax arrangements on take-home pay. I was weighing these factors before making a decision; no final choice was recorded.

## Saariv Development & Strategy
I described an idea for turning my own chatbot conversations into an avatar that could share my experiences. I asked for separate prompts to identify topics and extract what I had personally said. I wanted to choose which topics to share and test the avatar privately first.`;

  document.getElementById("step4_story").value = sampleStory;
}

async function handleStep4Submit() {
  const errorDiv = document.getElementById("step4_error");
  errorDiv.classList.add("hidden");

  const story = document.getElementById("step4_story").value.trim();
  if (!story) {
    errorDiv.textContent = "Please paste your experience story or click 'Load Sample'.";
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

  const saveButton = document.getElementById("step4-submit-btn");
  const indexStatus = document.getElementById("step4-index-status");
  if (saveButton) saveButton.disabled = true;
  if (indexStatus) indexStatus.textContent = "Saving and indexing your story…";
  try {
    const res = await fetch("/api/onboarding/step4", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({

        selected_items: allSelectedItems,
        experience_story: story
      })
    });
    const data = await res.json();
    if (data.ok && data.session_id) adoptServerSession(data);
    if (!res.ok || !data.ok) {
      errorDiv.textContent = data.message || "Could not save your story.";
      errorDiv.classList.remove("hidden");
      return;
    }

    onboardingState.indexedCount = data.indexed_count || 0;
    goToStep(5); // Go to unique experience step
  } catch (err) {
    errorDiv.textContent = "Could not save your story. Please try again.";
    errorDiv.classList.remove("hidden");
  } finally {
    if (saveButton) saveButton.disabled = false;
    if (indexStatus) indexStatus.textContent = "";
  }
}

// ==========================================
// STEP 5: UNIQUE EXPERIENCE (TEXT OR FILE)
// ==========================================

// Store uploaded files content

async function handleFileUpload(event) {
  const files = Array.from(event.target.files || []);
  const container = document.getElementById("step5_filenames");
  container.textContent = "";
  for (const file of files) {
    const row = document.createElement("div");
    row.className = "text-sm text-gray-700 bg-gray-50 px-3 py-2 rounded-md";
    row.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    container.appendChild(row);
  }
}

async function handleStep5Submit() {
  const error = document.getElementById("step5_error");
  error.classList.add("hidden");
  const customText = document.getElementById("step5_custom_text").value.trim();
  const topicTag = document.getElementById("step5_topic_tag").value.trim() || "Unique Experience";
  const files = Array.from(document.getElementById("step5_file_upload")?.files || []);
  const button = document.getElementById("step5-submit-btn");
  const buttonText = document.getElementById("step5-btn-text");
  const loader = document.getElementById("step5-btn-loader");
  const arrow = document.getElementById("step5-btn-arrow");
  const selected = Object.values(onboardingState.selectedItems).flatMap(items => Array.from(items));
  if (button) button.disabled = true;
  if (buttonText) buttonText.classList.add("hidden");
  if (loader) loader.classList.remove("hidden");
  if (arrow) arrow.classList.add("hidden");
  try {
    if (customText || files.length) {
      let response;
      if (files.length) {
        const body = new FormData();
        body.append("custom_experience", customText);
        body.append("topic_tag", topicTag);
        for (const file of files) body.append("files", file);
        response = await fetch("/api/onboarding/step5-files", { method: "POST", body });
      } else {
        response = await fetch("/api/onboarding/step5", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({  custom_experience: customText, topic_tag: topicTag })
        });
      }
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || "Could not index your sources.");
      adoptServerSession(data);
      onboardingState.indexedCount = data.indexed_count || 0;
    }
    setupPlayground(selected);
    goToStep(6);
  } catch (failure) {
    error.textContent = failure.message || "Could not save your sources. Please try again.";
    error.classList.remove("hidden");
  } finally {
    if (button) button.disabled = false;
    if (buttonText) buttonText.classList.remove("hidden");
    if (loader) loader.classList.add("hidden");
    if (arrow) arrow.classList.remove("hidden");
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

        query: query
      })
    });
    const data = await res.json();
    if (data.ok && data.session_id) adoptServerSession(data);

    // Remove loading message
    const loadingMsg = document.getElementById("loading-message");
    if (loadingMsg) loadingMsg.remove();

    if (!res.ok || !data.ok) throw new Error(data.message || "Could not search your sources.");
    appendPlaygroundAnswer(messagesContainer.querySelector('.space-y-4'), data, initials);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

  } catch (err) {
    // Remove loading message
    const loadingMsg = document.getElementById("loading-message");
    if (loadingMsg) loadingMsg.remove();

    appendPlaygroundAnswer(messagesContainer.querySelector('.space-y-4'), {
      reply: err.message || "Unable to connect to the avatar. Please try again.", sources: [], answer_mode: "error"
    }, initials);
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
    if (data.ok && data.session_id) adoptServerSession(data);

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


// Knowledge retrieval returns ordinary text and citations usable by any connected agent.
function adoptServerSession(data) {
  if (data.session_id) {
    onboardingState.sessionId = data.session_id;
    localStorage.setItem("saariv_session_id", data.session_id);
  }
}

function appendKnowledgeSources(parent, sources) {
  for (const source of sources || []) {
    const details = document.createElement("details");
    details.className = "mt-3 border-t border-gray-100 pt-2";
    const summary = document.createElement("summary");
    summary.className = "cursor-pointer text-xs text-gray-600";
    const reference = source.source || {};
    let location = reference.title || "Saved source";
    if (reference.section && reference.section !== reference.title) location += ` — ${reference.section}`;
    if (reference.page_start) location += ` · page ${reference.page_start}${reference.page_end !== reference.page_start ? "–" + reference.page_end : ""}`;
    summary.textContent = `[${source.citation_id}] ${location}`;
    const excerpt = document.createElement("p");
    excerpt.className = "mt-2 whitespace-pre-wrap text-xs text-gray-600";
    excerpt.textContent = source.text;
    details.appendChild(summary);
    details.appendChild(excerpt);
    parent.appendChild(details);
  }
}

function appendPlaygroundAnswer(parent, data, initials) {
  const row = document.createElement("div");
  row.className = "flex gap-3";
  const avatar = document.createElement("div");
  avatar.className = "w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm flex-shrink-0";
  avatar.textContent = initials;
  const bubble = document.createElement("div");
  bubble.className = "flex-1 bg-white rounded-2xl rounded-tl-md px-4 py-3 border border-gray-200 shadow-sm";
  const answer = document.createElement("p");
  answer.className = "text-gray-800 text-sm leading-relaxed whitespace-pre-wrap";
  answer.textContent = data.reply || "No answer was returned.";
  bubble.appendChild(answer);
  if (data.answer_mode === "extractive") {
    const label = document.createElement("p");
    label.className = "mt-2 text-xs text-gray-500";
    label.textContent = "Showing original source excerpts.";
    bubble.appendChild(label);
  }
  appendKnowledgeSources(bubble, data.sources);
  row.appendChild(avatar);
  row.appendChild(bubble);
  parent.appendChild(row);
}

async function refreshKnowledgeStatus() {
  const label = document.getElementById("knowledge-status");
  if (!label) return;
  try {
    const response = await fetch("/api/knowledge/status");
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    label.textContent = data.needs_reindex ? "Rebuild the index to use the new embedding model." :
      data.maintenance_pending ? data.warnings.join(" ") :
      `${data.documents_count} saved sources · ${data.embedding_enabled ? "Semantic + keyword search" : "Keyword search; embeddings not configured"}`;
    const rebuild = document.getElementById("knowledge-reindex-btn");
    if (rebuild) rebuild.classList.toggle("hidden", !data.needs_reindex && !data.maintenance_pending);
  } catch (error) {
    label.textContent = error.message || "Could not load source status.";
  }
}

async function rebuildKnowledgeIndex() {
  const button = document.getElementById("knowledge-reindex-btn");
  button.disabled = true;
  try {
    const response = await fetch("/api/knowledge/reindex", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    await refreshKnowledgeStatus();
  } catch (error) {
    document.getElementById("knowledge-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function createAgentAccessToken() {
  const status = document.getElementById("agent-token-status");
  try {
    const response = await fetch("/api/knowledge/token", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    const input = document.getElementById("agent-access-token");
    input.value = data.token;
    input.classList.remove("hidden");
    document.getElementById("agent-token-copy").classList.remove("hidden");
    status.textContent = "Read-only access key created. Valid for 30 days.";
  } catch (error) {
    status.textContent = error.message || "Could not create an access key.";
  }
}

async function copyAgentAccessToken() {
  const input = document.getElementById("agent-access-token");
  try {
    await navigator.clipboard.writeText(input.value);
    document.getElementById("agent-token-status").textContent = "Access key copied.";
  } catch (error) {
    input.type = "text";
    input.select();
    document.getElementById("agent-token-status").textContent = "Select and copy the access key.";
  }
}

async function revokeAgentAccessTokens() {
  const response = await fetch("/api/knowledge/token", { method: "DELETE" });
  const status = document.getElementById("agent-token-status");
  if (response.ok) {
    document.getElementById("agent-access-token").value = "";
    status.textContent = "All access keys for this avatar have been revoked.";
  } else {
    status.textContent = "Could not revoke access keys. Please try again.";
  }
}

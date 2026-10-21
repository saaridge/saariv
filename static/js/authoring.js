/* Private drafts stay in the authoring DOM; publication and rewards remain server decisions. */
(function (global) {
  "use strict";
  const { DictationInput, postJSON, RequestError } = global.SaarivMarketplace;

  class EditorController {
    constructor({ document, window = global.window, fetch = global.fetch?.bind(global), csrfToken, Recognition, draft = null }) {
      Object.assign(this, { document, fetch, csrfToken });
      this.id = draft?.draft_id || null;
      this.version = draft?.version || null;
      this.state = draft?.status || "draft";
      this.pending = false;
      this.submitting = false;
      this.conflict = false;
      this.dirty = false;
      const get = id => document.getElementById(id);
      this.fields = Object.fromEntries(["title", "teaser", "taxonomy", "price", "body"].map(key => [key, get(`draft-${key}`)]));
      if (draft) {
        for (const key of ["title", "teaser", "body"]) this.fields[key].value = draft[key] || "";
        this.fields.taxonomy.value = Array.isArray(draft.taxonomy) ? draft.taxonomy.join(", ") : "";
        this.fields.price.value = String(draft.price_coins ?? "");
      }
      get("draft-conflict").hidden = true;
      this.dictation = new DictationInput({ document, window, Recognition, input: this.fields.body,
        toggle: get("story-dictation-toggle"), label: get("story-dictation-label"),
        status: get("story-dictation-status"), cancel: get("story-dictation-cancel"),
        blocked: () => this.pending || this.state !== "draft", onChange: () => this.changed() });
      Object.values(this.fields).forEach(field => field.addEventListener("input", () => this.changed()));
      get("draft-form").addEventListener("submit", event => { event.preventDefault(); return this.perform(false); });
      get("draft-submit").addEventListener("click", () => this.perform(true));
      window?.addEventListener("beforeunload", event => {
        if (this.dirty || this.pending) { event.preventDefault(); event.returnValue = ""; }
      });
      this.preview();
      this.updateControls();
      this.status(this.state === "submitted" ? "Submitted for review. This revision is awaiting a decision."
        : this.state === "draft" ? "Private draft. Save when you are ready." : "This revision is read-only. Its status comes from review.");
    }

    status(message, error = false) {
      const element = this.document.getElementById("draft-status");
      element.textContent = message;
      element.setAttribute("data-tone", error ? "error" : "muted");
    }

    changed() {
      this.dirty = true;
      this.preview();
      if (!this.pending && !this.conflict) this.status("Unsaved changes. Your draft is private.");
    }

    values() {
      return { title: this.fields.title.value, teaser: this.fields.teaser.value,
        taxonomy: [...new Set(this.fields.taxonomy.value.split(",").map(tag => tag.trim()).filter(Boolean))],
        price_coins: Number(this.fields.price.value), body: this.fields.body.value };
    }

    preview() {
      const values = this.values();
      for (const [id, text] of Object.entries({ "preview-title": values.title || "Your title",
        "preview-teaser": values.teaser || "Your public teaser appears here.",
        "preview-taxonomy": values.taxonomy.join(" · "), "preview-body": values.body,
        "preview-price": /^[1-9]\d*$/.test(this.fields.price.value) && Number.isSafeInteger(values.price_coins)
          ? `${values.price_coins} coins · one-time` : "Choose a coin price" })) {
        this.document.getElementById(id).textContent = text;
      }
    }

    updateControls() {
      const locked = this.state !== "draft" || this.submitting;
      this.document.getElementById("draft-save").disabled = this.pending || this.conflict || locked;
      this.document.getElementById("draft-submit").disabled = this.pending || this.conflict || locked;
      this.document.getElementById("draft-form").setAttribute("aria-busy", String(this.pending));
      this.dictation?.render();
      for (const field of Object.values(this.fields)) field.readOnly = locked || (field === this.fields.body && this.dictation?.busy);
    }

    validate(submit, values) {
      if (!/^[1-9]\d*$/.test(this.fields.price.value) || !Number.isSafeInteger(values.price_coins)) {
        this.status("Choose a positive whole number of coins for the price.", true); this.fields.price.focus(); return false;
      }
      if (!values.body.trim()) { this.status("Add your story before saving.", true); this.fields.body.focus(); return false; }
      if (submit) {
        for (const key of ["title", "teaser"]) {
          if (!values[key].trim()) { this.status(`Add a public ${key} before submitting.`, true); this.fields[key].focus(); return false; }
        }
        if (!values.taxonomy.length) { this.status("Add at least one taxonomy topic before submitting.", true); this.fields.taxonomy.focus(); return false; }
      }
      return true;
    }

    receipt(data, expectedStatus) {
      if (typeof data.draft_id !== "string" || !data.draft_id || !Number.isSafeInteger(data.version)
          || data.version < 1 || data.status !== expectedStatus || (this.id && data.draft_id !== this.id)) {
        throw new RequestError("The draft response could not be read. Your text is still here. Please refresh before retrying.");
      }
      this.id = data.draft_id;
      this.version = data.version;
      this.state = data.status;
    }

    async perform(submit) {
      if (this.pending || this.conflict || this.state !== "draft") return;
      if (this.dictation.stopForReview()) {
        this.status("Dictation is finishing. Review your final words before saving or submitting."); return;
      }
      const values = this.values();
      if (!this.validate(submit, values)) return;
      this.pending = true;
      this.updateControls();
      this.status(submit ? "Saving your private draft before review…" : "Saving your private draft…");
      try {
        const savedText = JSON.stringify(values);
        const payload = this.id ? { ...values, version: this.version } : values;
        const url = this.id ? `/api/experiences/drafts/${encodeURIComponent(this.id)}` : "/api/experiences/drafts";
        this.receipt(await postJSON(this.fetch, url, payload, this.csrfToken, this.id ? "PATCH" : "POST"), "draft");
        this.dirty = JSON.stringify(this.values()) !== savedText;
        if (submit && this.dirty) {
          this.status("Your text changed while saving. Review it, then submit again."); return;
        }
        if (submit) {
          this.submitting = true;
          this.updateControls();
          this.receipt(await postJSON(this.fetch, `/api/experiences/drafts/${encodeURIComponent(this.id)}/submit`,
            { version: this.version }, this.csrfToken), "submitted");
          this.status("Submitted for review. Approval is pending; no reward has been issued by submitting.");
        } else this.status(this.dirty ? "Earlier changes saved privately. You still have unsaved changes." : "Draft saved. Your story is private.");
      } catch (error) {
        if (error.status === 409) {
          this.conflict = true;
          const conflict = this.document.getElementById("draft-conflict");
          conflict.hidden = false;
          conflict.textContent = "A newer draft exists. Your edits are still here. Copy your text before reloading this page to compare versions.";
          this.status("Draft conflict. Review the message below before continuing.", true);
        } else this.status(error instanceof RequestError ? error.message : "The draft could not be saved. Your text is still here. Please try again.", true);
      } finally {
        this.pending = false;
        this.submitting = false;
        this.updateControls();
      }
    }
  }

  function bootstrap() {
    const document = global.document;
    if (!document?.querySelector("[data-marketplace-editor]")) return;
    try {
      const state = JSON.parse(document.getElementById("authoring-state").textContent);
      new EditorController({ document, window: global.window, draft: state.draft,
        csrfToken: document.querySelector('meta[name="csrf-token"]')?.content,
        Recognition: global.SpeechRecognition || global.webkitSpeechRecognition });
    } catch (_) {
      document.getElementById("draft-status").textContent = "The editor could not start. Copy your draft before refreshing this page.";
    }
  }
  global.SaarivAuthoring = { EditorController };
  if (global.document?.readyState === "loading") global.document.addEventListener("DOMContentLoaded", bootstrap);
  else bootstrap();
})(globalThis);

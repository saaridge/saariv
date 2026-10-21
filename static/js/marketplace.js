/* Saariv marketplace: safe cards and editable query dictation. No purchase side effects. */
(function (global) {
  "use strict";

  const string = value => typeof value === "string" ? value : "";
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value : 0;
  const node = (document, tag, className, text) => {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  class RequestError extends Error {
    constructor(message, status = 0, code = "") {
      super(message);
      this.status = status;
      this.code = code;
    }
  }

  async function postJSON(fetch, url, payload, csrfToken, method = "POST") {
    if (!csrfToken) throw new RequestError("Your session needs refreshing. Copy any unsaved text, then refresh this page.");
    let response;
    try {
      response = await fetch(url, { method, credentials: "same-origin",
        headers: { "Accept": "application/json", "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(payload) });
    } catch (_) {
      throw new RequestError("Could not connect. Your text is still here. Please try again.");
    }
    let data;
    try { data = await response.json(); } catch (_) { /* Handle non-JSON error pages without exposing their HTML. */ }
    if (!response.ok) {
      const message = response.status === 401
        ? "Your session has expired. Sign in again in another tab, then try again. Your text is still here."
        : string(data?.error?.message).slice(0, 500) || "This request could not be completed. Please try again.";
      throw new RequestError(message, response.status, string(data?.error?.code));
    }
    if (!data || typeof data !== "object") throw new RequestError("The server returned an unreadable response. Please try again.");
    return data;
  }

  // StoryDictation is shared with the existing onboarding flow. Recognition starts only on click.
  class DictationInput {
    constructor({ document, window, input, toggle, label, status, cancel, Recognition, blocked = () => false, onChange = () => {} }) {
      Object.assign(this, { input, toggle, label, status, cancel, blocked });
      const Controller = typeof StoryDictation === "function" ? StoryDictation : null;
      if (!Controller) {
        this.state = { supported: false, busy: false, phase: "unsupported",
          message: "Voice dictation is unavailable. You can still type or paste your text." };
        this.render();
        return;
      }
      this.controller = new Controller({ Recognition, lang: global.navigator?.language || "en-US",
        getText: () => input.value,
        setText: text => { input.value = text; onChange(); },
        onState: state => { this.state = state; this.render(); } });
      toggle?.addEventListener("click", () => {
        if (this.blocked()) return;
        if (this.busy) this.controller.stop();
        else this.controller.start();
      });
      cancel?.addEventListener("click", () => this.controller.cancel());
      window?.addEventListener("pagehide", () => this.controller.cancel());
      document.addEventListener("visibilitychange", () => { if (document.hidden) this.controller.cancel(); });
      document.addEventListener("click", event => {
        if (event.target.closest?.("a[href]")) this.controller.cancel();
      }, true);
    }
    get busy() { return this.state?.busy === true; }
    stopForReview() {
      if (!this.busy) return false;
      this.controller.stop();
      return true;
    }
    render() {
      const state = this.state;
      if (!state) return;
      this.input.readOnly = state.busy;
      if (this.toggle) {
        this.toggle.disabled = !state.supported || state.phase === "stopping" || this.blocked();
        this.toggle.setAttribute("aria-pressed", String(state.busy));
      }
      if (this.label) this.label.textContent = state.phase === "stopping" ? "Finishing…" : state.busy ? "Stop dictation" : "Dictate";
      if (this.cancel) this.cancel.hidden = !state.busy;
      if (this.status) {
        this.status.textContent = state.message;
        this.status.setAttribute("data-tone", state.phase === "error" ? "error" : "muted");
      }
    }
  }

  function cleanPage(data, authenticated) {
    if (!Array.isArray(data?.items) || !string(data.query_id) || typeof data.login_required !== "boolean"
        || typeof data.retrieval_mode !== "string"
        || !(data.next_cursor === null || typeof data.next_cursor === "string")) {
      throw new RequestError("Search results could not be read. Please try again.");
    }
    const items = data.items.slice(0, authenticated ? 12 : 4).filter(item => string(item?.experience_id)).map(item => ({
      experience_id: item.experience_id, title: string(item.title), teaser: string(item.teaser),
      taxonomy: Array.isArray(item.taxonomy) ? item.taxonomy.filter(tag => typeof tag === "string") : [],
      price_coins: Number.isSafeInteger(item.price_coins) && item.price_coins > 0 ? item.price_coins : null,
      author: authenticated && string(item.author?.display_name) ? { display_name: item.author.display_name } : null,
      rating: { upvotes: count(item.rating?.upvotes), downvotes: count(item.rating?.downvotes) },
      unlocked: authenticated && item.unlocked === true,
    }));
    return { query_id: data.query_id, items, next_cursor: authenticated ? data.next_cursor : null,
      login_required: !authenticated && data.login_required, retrieval_mode: data.retrieval_mode };
  }

  function loginPath(next, queryId) {
    const params = new URLSearchParams({ next });
    if (queryId) params.set("query_id", queryId);
    return `/login?${params}`;
  }

  class SearchController {
    constructor({ document, window = global.window, fetch = global.fetch?.bind(global), Recognition,
      csrfToken, authenticated = false, initialPage = null }) {
      Object.assign(this, { document, fetch, csrfToken, authenticated });
      this.pending = false;
      this.page = null;
      this.elements = Object.fromEntries(["search-form", "search-query", "search-submit", "search-status",
        "search-results", "results-heading", "search-mode", "search-more"].map(id => [id, document.getElementById(id)]));
      const get = id => document.getElementById(id);
      this.dictation = new DictationInput({ document, window, Recognition, input: get("search-query"),
        toggle: get("query-dictation-toggle"), label: get("query-dictation-label"),
        status: get("query-dictation-status"), cancel: get("query-dictation-cancel"), blocked: () => this.pending });
      get("search-form").addEventListener("submit", event => { event.preventDefault(); return this.search(); });
      get("search-more").addEventListener("click", event => {
        if (this.authenticated) { event.preventDefault(); return this.search(true); }
      });
      get("search-submit").disabled = false;
      this.lastQuery = get("search-query").value;
      if (initialPage) {
        try { this.page = cleanPage(initialPage, authenticated); this.render(); }
        catch (error) { this.status(error.message, true); }
      }
    }

    status(message, error = false) {
      const element = this.elements["search-status"];
      element.textContent = message;
      element.setAttribute("data-tone", error ? "error" : "muted");
    }

    async search(more = false) {
      if (this.pending || (more && !this.page?.next_cursor)) return;
      if (this.dictation.stopForReview()) {
        this.status("Dictation is finishing. Review the final words, then search.");
        return;
      }
      const input = this.elements["search-query"];
      const query = (more ? this.lastQuery : input.value).trim();
      if (!query) { this.status("Type or dictate a question to find experiences.", true); input.focus(); return; }
      this.pending = true;
      this.elements["search-submit"].disabled = true;
      this.elements["search-more"].setAttribute("aria-disabled", "true");
      this.elements["search-results"].setAttribute("aria-busy", "true");
      this.dictation.render();
      this.status(more ? "Finding more experiences…" : "Finding relevant experiences…");
      try {
        const payload = { query };
        if (more) payload.cursor = this.page.next_cursor;
        const next = cleanPage(await postJSON(this.fetch, "/api/search", payload, this.csrfToken), this.authenticated);
        if (more) {
          const seen = new Set(this.page.items.map(item => item.experience_id));
          next.items = [...this.page.items, ...next.items.filter(item => !seen.has(item.experience_id))];
        }
        this.page = next;
        this.lastQuery = query;
        this.render();
        this.status(next.items.length ? "Results are ready. Open an experience to see its details." : "Try a different question or a broader topic.");
      } catch (error) {
        this.status(error instanceof RequestError ? error.message : "Search is unavailable. Your question is still here. Please try again.", true);
      } finally {
        this.pending = false;
        this.elements["search-submit"].disabled = false;
        this.elements["search-more"].setAttribute("aria-disabled", "false");
        this.elements["search-results"].setAttribute("aria-busy", "false");
        this.dictation.render();
      }
    }

    render() {
      const { page, document } = this;
      const root = this.elements["search-results"];
      root.replaceChildren();
      this.elements["results-heading"].textContent = `${page.items.length} ${page.items.length === 1 ? "experience" : "experiences"} to explore`;
      const modes = { hybrid: "Semantic + keyword search", lexical: "Keyword search", lexical_fallback: "Keyword search", dense: "Semantic search" };
      this.elements["search-mode"].textContent = modes[page.retrieval_mode] || "Search mode unavailable";
      for (const item of page.items) {
        const link = node(document, "a", "experience-card");
        const internal = `/experiences/${encodeURIComponent(item.experience_id)}`;
        link.href = this.authenticated ? `${internal}?${new URLSearchParams({ query_id: page.query_id })}` : loginPath(internal, page.query_id);
        link.append(node(document, "span", "card-eyebrow", item.unlocked ? "Unlocked" : "Experience"),
          node(document, "h3", "card-title", item.title), node(document, "p", "card-teaser", item.teaser));
        const tags = node(document, "div", "taxonomy-tags");
        item.taxonomy.forEach(tag => tags.appendChild(node(document, "span", "taxonomy-tag", tag)));
        link.appendChild(tags);
        const author = node(document, "div", "card-author");
        if (this.authenticated) author.appendChild(node(document, "span", "author-name", item.author?.display_name || "Community author"));
        else {
          const placeholder = node(document, "span", "author-placeholder", "Community author");
          placeholder.setAttribute("aria-hidden", "true");
          author.append(placeholder, node(document, "span", "author-prompt", "Sign in to see author"));
        }
        if (this.authenticated) {
          const total = item.rating.upvotes + item.rating.downvotes;
          author.appendChild(node(document, "span", "card-rating", total
            ? `${Math.round(item.rating.upvotes / total * 100)}% helpful · ${total} ${total === 1 ? "vote" : "votes"}` : "New author"));
        }
        link.appendChild(author);
        const footer = node(document, "div", "card-footer");
        footer.append(node(document, "span", "card-price", item.unlocked ? "Yours to read"
          : item.price_coins === null ? "Price unavailable" : `${item.price_coins} coins · one-time`),
        node(document, "span", "card-arrow", "↗"));
        link.appendChild(footer);
        root.appendChild(link);
      }
      if (!page.items.length) root.appendChild(node(document, "p", "empty-state", "No experiences matched this question. Try another topic or a little more detail."));
      const more = this.elements["search-more"];
      more.hidden = this.authenticated ? !page.next_cursor : !page.login_required;
      more.textContent = this.authenticated ? "See more experiences" : "Sign in to explore more";
      more.href = this.authenticated ? "#results" : loginPath("/", page.query_id);
    }
  }

  function bootstrap() {
    const document = global.document;
    if (!document?.querySelector("[data-marketplace-home]")) return;
    try {
      const state = JSON.parse(document.getElementById("marketplace-state").textContent);
      new SearchController({ document, window: global.window, authenticated: state.authenticated,
        initialPage: state.page, csrfToken: document.querySelector('meta[name="csrf-token"]')?.content,
        Recognition: global.SpeechRecognition || global.webkitSpeechRecognition });
    } catch (_) {
      document.getElementById("search-status").textContent = "Search could not start. Refresh this page to try again.";
    }
  }

  global.SaarivMarketplace = { SearchController, DictationInput, postJSON, RequestError };
  if (global.document?.readyState === "loading") global.document.addEventListener("DOMContentLoaded", bootstrap);
  else bootstrap();
})(globalThis);

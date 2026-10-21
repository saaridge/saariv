import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const repository = new URL("../", import.meta.url);
const readScript = name => {
  const filename = new URL(`static/js/${name}.js`, repository);
  return fs.existsSync(filename) ? fs.readFileSync(filename, "utf8") : "";
};

// Only browser IO is doubled: controllers, shared dictation, and Jinja rendering run for real.
class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.value = "";
    this.hidden = false;
    this.disabled = false;
    this.readOnly = false;
    this._text = "";
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(""); }
  set innerHTML(_) { throw new Error("User content must be rendered as text nodes."); }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  replaceChildren(...children) { this._text = ""; this.children = children; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(name, callback) { (this.listeners[name] ??= []).push(callback); }
  async dispatch(name, extra = {}) {
    const event = { target: this, preventDefault() {}, ...extra };
    await Promise.all((this.listeners[name] ?? []).map(callback => callback(event)));
  }
  focus() { this.focused = true; }
}

function environment(options = {}) {
  const ids = ["search-form", "search-query", "search-submit", "search-status", "search-results",
    "results-heading", "search-mode", "search-more", "query-dictation-toggle", "query-dictation-label",
    "query-dictation-status", "query-dictation-cancel", "draft-form", "draft-title", "draft-teaser",
    "draft-taxonomy", "draft-price", "draft-body", "draft-save", "draft-submit", "draft-status",
    "draft-conflict", "story-dictation-toggle", "story-dictation-label", "story-dictation-status",
    "story-dictation-cancel", "preview-title", "preview-teaser", "preview-taxonomy", "preview-price",
    "preview-body"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  for (const id of ["search-submit", "draft-save", "draft-submit"]) elements[id].disabled = true;
  const document = new Element("document");
  document.getElementById = id => elements[id] ?? null;
  document.createElement = tag => new Element(tag);
  document.querySelector = () => null;
  const window = new Element("window");
  const requests = [];
  const instances = [];
  class Recognition {
    constructor() { instances.push(this); this.stops = 0; this.aborts = 0; }
    start() {}
    stop() { this.stops++; }
    abort() { this.aborts++; }
  }
  const fetch = async (url, init) => {
    requests.push({ url, ...init, payload: JSON.parse(init.body) });
    return options.response ? options.response(url, init) : response(page());
  };
  const context = vm.createContext({ window, document, fetch, URLSearchParams, URL, console,
    navigator: { language: "en-US" } });
  vm.runInContext(readScript("story-dictation"), context);
  vm.runInContext(readScript("marketplace"), context);
  vm.runInContext(readScript("authoring"), context);
  return { context, document, window, elements, requests, instances, Recognition, fetch };
}

const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status,
  json: async () => data });
const card = (id = "exp-1", extra = {}) => ({ experience_id: id, title: "Planning a move",
  teaser: "I compared rental deposits before deciding where to live.", taxonomy: ["Relocation", "Housing"],
  price_coins: 25, author: null, rating: { upvotes: 0, downvotes: 0, ranking_score: 0.5 },
  unlocked: false, ...extra });
const page = (extra = {}) => ({ query_id: "opaque-query-1", items: [card()], next_cursor: null,
  login_required: true, retrieval_mode: "hybrid", ...extra });
const draft = (extra = {}) => ({ draft_id: "draft-1", version: 3, status: "draft",
  title: "Planning a move", teaser: "I compared rental deposits.", taxonomy: ["Relocation", "Housing"],
  price_coins: 25, body: "I asked about leases. I planned a move. I have not moved yet.", ...extra });

function searchFixture(options = {}) {
  const f = environment(options);
  const Controller = f.context.SaarivMarketplace?.SearchController;
  assert.equal(typeof Controller, "function", "Marketplace search controller must exist");
  f.controller = new Controller({ document: f.document, window: f.window, fetch: f.fetch,
    Recognition: options.unsupported ? undefined : f.Recognition, csrfToken: options.noCSRF ? "" : "test-csrf",
    authenticated: options.authenticated ?? false, initialPage: options.initialPage ?? null });
  return f;
}

function editorFixture(options = {}) {
  const f = environment(options);
  const Controller = f.context.SaarivAuthoring?.EditorController;
  assert.equal(typeof Controller, "function", "Private draft editor controller must exist");
  f.controller = new Controller({ document: f.document, window: f.window, fetch: f.fetch,
    Recognition: options.unsupported ? undefined : f.Recognition,
    csrfToken: options.noCSRF ? "" : "test-csrf", draft: options.draft === null ? null : draft(options.draft) });
  return f;
}

function transcript(recognition, text) {
  recognition.onresult({ results: [Object.assign([{ transcript: text }], { isFinal: true })] });
}

function links(element) {
  return [element, ...element.children.flatMap(child => links(child))].filter(child => child.tagName === "A");
}

test("test_dictated_query_remains_editable_and_submits_once", async () => {
  let finish;
  const f = searchFixture({ response: () => new Promise(resolve => { finish = resolve; }) });
  const e = f.elements;
  e["search-query"].value = "I am planning a move.";
  assert.equal(f.instances.length, 0, "page load must not activate the microphone");
  await e["query-dictation-toggle"].dispatch("click");
  transcript(f.instances[0], "I asked about deposits.");
  assert.match(e["search-query"].value, /planning a move.*\n\nI asked/s);
  assert.equal(e["search-query"].readOnly, true);
  await e["query-dictation-toggle"].dispatch("click");
  assert.equal(f.instances[0].stops, 1);
  f.instances[0].onend();
  assert.equal(e["search-query"].readOnly, false);
  e["search-query"].value = "How did you compare deposits?";
  const pending = e["search-form"].dispatch("submit");
  await e["search-form"].dispatch("submit");
  assert.equal(f.requests.length, 1);
  assert.equal(f.requests[0].payload.query, "How did you compare deposits?");
  assert.equal(f.requests[0].url, "/api/search");
  assert.equal(f.requests[0].headers["X-CSRF-Token"], "test-csrf");
  assert.equal(f.requests[0].credentials, "same-origin");
  finish(response(page()));
  await pending;
  assert.match(e["search-results"].textContent, /Planning a move/);
});

test("submitting while recognition is busy stops and requires review before search", async () => {
  const f = searchFixture();
  f.elements["search-query"].value = "My typed question.";
  await f.elements["query-dictation-toggle"].dispatch("click");
  await f.elements["search-form"].dispatch("submit");
  assert.equal(f.instances[0].stops, 1);
  transcript(f.instances[0], "Final words.");
  f.instances[0].onend();
  assert.equal(f.requests.length, 0);
  assert.match(f.elements["search-query"].value, /Final words/);
});

test("unsupported dictation preserves ordinary typed query search", async () => {
  const f = searchFixture({ unsupported: true });
  assert.equal(f.elements["search-submit"].disabled, false, "successful initialization enables search");
  assert.equal(f.elements["query-dictation-toggle"].disabled, true);
  assert.match(f.elements["query-dictation-status"].textContent, /type|paste/i);
  f.elements["search-query"].value = "Typed question";
  await f.elements["search-form"].dispatch("submit");
  assert.equal(f.requests[0].payload.query, "Typed question");
});

test("denied microphone preserves the query and allows a deliberate retry", async () => {
  const f = searchFixture();
  f.elements["search-query"].value = "Keep my question";
  await f.elements["query-dictation-toggle"].dispatch("click");
  f.instances[0].onerror({ error: "not-allowed" });
  assert.equal(f.elements["search-query"].value, "Keep my question");
  assert.equal(f.elements["search-query"].readOnly, false);
  assert.match(f.elements["query-dictation-status"].textContent, /blocked/i);
  await f.elements["query-dictation-toggle"].dispatch("click");
  assert.equal(f.instances.length, 2);
});

test("cancel and link navigation ignore late transcripts before leaving", async () => {
  const f = searchFixture();
  await f.elements["query-dictation-toggle"].dispatch("click");
  transcript(f.instances[0], "Keep these words");
  await f.elements["query-dictation-cancel"].dispatch("click");
  transcript(f.instances[0], "Late wrong words");
  assert.equal(f.elements["search-query"].value, "Keep these words");
  await f.elements["query-dictation-toggle"].dispatch("click");
  await f.document.dispatch("click", { target: { closest: () => ({ href: "/experiences/new" }) } });
  assert.equal(f.instances[1].aborts, 1);
  await f.elements["query-dictation-toggle"].dispatch("click");
  await f.window.dispatch("pagehide");
  assert.equal(f.instances[2].aborts, 1);
});

test("test_guest_card_creates_resume_intent without carrying raw query text", async () => {
  const f = searchFixture();
  f.elements["search-query"].value = "Private raw search phrase";
  await f.elements["search-form"].dispatch("submit");
  const href = links(f.elements["search-results"])[0].href;
  const url = new URL(href, "https://saariv.test");
  assert.equal(url.pathname, "/login");
  assert.equal(url.searchParams.get("next"), "/experiences/exp-1");
  assert.equal(url.searchParams.get("query_id"), "opaque-query-1");
  assert.equal(href.includes("Private"), false);
  const more = new URL(f.elements["search-more"].href, "https://saariv.test");
  assert.equal(more.searchParams.get("next"), "/");
  assert.equal(more.searchParams.get("query_id"), "opaque-query-1");
});

test("guest rendering and retained state discard body and concealed identity", () => {
  const f = searchFixture({ initialPage: page({ next_cursor: "forbidden-cursor", items:
    Array.from({ length: 6 }, (_, index) => card(`exp-${index}`, {
      body: "CANARY_PRIVATE_BODY", source: "CANARY_SOURCE", author: {
        display_name: "CANARY_REAL_NAME", user_id: "CANARY_AUTHOR_ID", avatar_url: "CANARY_AVATAR" },
    })) }) });
  assert.equal(links(f.elements["search-results"]).length, 4);
  assert.equal(JSON.stringify(f.controller.page).includes("CANARY"), false);
  assert.equal(f.elements["search-results"].textContent.includes("CANARY"), false);
  assert.match(f.elements["search-results"].textContent, /Sign in to see author/);
  assert.equal(f.controller.page.next_cursor, null);
});

test("signed in cards show real vote counts, neutral new authors, and owned navigation", () => {
  const f = searchFixture({ authenticated: true, initialPage: page({ login_required: false,
    items: [card("owned", { author: { display_name: "Synthetic Reader" }, unlocked: true,
      rating: { upvotes: 3, downvotes: 1, ranking_score: 0.625 } }), card("new")] }) });
  const content = f.elements["search-results"].textContent;
  assert.match(content, /Synthetic Reader/);
  assert.match(content, /75% helpful.*4 votes/s);
  assert.match(content, /New author/);
  assert.match(content, /Unlocked/);
  assert.equal(links(f.elements["search-results"])[0].href,
    "/experiences/owned?query_id=opaque-query-1");
  assert.equal(f.requests.length, 0, "opening a page cannot trigger purchases or quotes");
});

test("empty results stay honest and show the server retrieval mode", async () => {
  const f = searchFixture({ response: () => response(page({ items: [], retrieval_mode: "lexical" })) });
  f.elements["search-query"].value = "Unknown topic";
  await f.elements["search-form"].dispatch("submit");
  assert.match(f.elements["search-results"].textContent, /No experiences/i);
  assert.match(f.elements["search-mode"].textContent, /keyword/i);
  assert.equal(links(f.elements["search-results"]).length, 0);
});

test("a failed search retains the query and previous cards", async () => {
  const f = searchFixture({ initialPage: page(), response: () => { throw new Error("offline"); } });
  f.elements["search-query"].value = "Keep my search";
  await f.elements["search-form"].dispatch("submit");
  assert.equal(f.elements["search-query"].value, "Keep my search");
  assert.match(f.elements["search-results"].textContent, /Planning a move/);
  assert.match(f.elements["search-status"].textContent, /try again/i);
  assert.equal(f.elements["search-submit"].disabled, false);
});

test("empty queries and missing CSRF never send requests", async () => {
  const empty = searchFixture();
  empty.elements["search-query"].value = " \n ";
  await empty.elements["search-form"].dispatch("submit");
  assert.equal(empty.requests.length, 0);
  assert.equal(empty.elements["search-query"].focused, true);
  const expired = searchFixture({ noCSRF: true });
  expired.elements["search-query"].value = "A question";
  await expired.elements["search-form"].dispatch("submit");
  assert.equal(expired.requests.length, 0);
  assert.match(expired.elements["search-status"].textContent, /refresh/i);
});

test("authenticated pagination retains the submitted query and deduplicates results", async () => {
  const f = searchFixture({ authenticated: true, initialPage: page({ next_cursor: "cursor-2",
    login_required: false }), response: () => response(page({ login_required: false,
    items: [card(), card("exp-2")], next_cursor: null })) });
  f.controller.lastQuery = "Original query";
  f.elements["search-query"].value = "Unsaved edited query";
  await f.elements["search-more"].dispatch("click");
  assert.equal(f.requests[0].payload.query, "Original query");
  assert.equal(f.requests[0].payload.cursor, "cursor-2");
  assert.equal(links(f.elements["search-results"]).length, 2);
  assert.equal(f.elements["search-more"].hidden, true);
});

test("editor saves an exact private draft with CSRF and its optimistic version", async () => {
  const f = editorFixture({ response: () => response({ draft_id: "draft-1", version: 4, status: "draft" }) });
  f.elements["draft-body"].value = "I asked about a move. I planned it; I have not completed it.";
  await f.elements["draft-form"].dispatch("submit");
  assert.equal(f.requests.length, 1);
  assert.equal(f.requests[0].url, "/api/experiences/drafts/draft-1");
  assert.equal(f.requests[0].method, "PATCH");
  assert.equal(f.requests[0].headers["X-CSRF-Token"], "test-csrf");
  assert.equal(f.requests[0].payload.version, 3);
  assert.equal(f.requests[0].payload.body, f.elements["draft-body"].value);
  assert.equal(f.requests[0].payload.price_coins, 25);
  assert.equal(Object.hasOwn(f.requests[0].payload, "author_id"), false);
  assert.equal(Object.hasOwn(f.requests[0].payload, "status"), false);
  assert.match(f.elements["draft-status"].textContent, /saved.*private/i);
});

test("new draft is created before explicit review submission and never awards coins", async () => {
  const f = editorFixture({ draft: null, response: url => response(url.endsWith("/submit")
    ? { draft_id: "new-draft", version: 2, status: "submitted" }
    : { draft_id: "new-draft", version: 1, status: "draft" }, 201) });
  for (const [id, value] of Object.entries({ "draft-title": "My plan", "draft-teaser": "What I compared",
    "draft-body": "I planned to move.", "draft-taxonomy": "Relocation, Housing", "draft-price": "30" })) {
    f.elements[id].value = value;
  }
  await f.elements["draft-submit"].dispatch("click");
  assert.deepEqual(f.requests.map(request => request.url),
    ["/api/experiences/drafts", "/api/experiences/drafts/new-draft/submit"]);
  assert.deepEqual(f.requests[1].payload, { version: 1 });
  assert.deepEqual(f.requests[0].payload.taxonomy, ["Relocation", "Housing"]);
  assert.match(f.elements["draft-status"].textContent, /submitted.*review/i);
  assert.doesNotMatch(f.elements["draft-status"].textContent, /approved|earned|credited/i);
  assert.equal(f.elements["draft-save"].disabled, true);
});

test("invalid prices and incomplete publication metadata cannot be submitted", async () => {
  for (const price of ["0", "-1", "2.5", "1e2", "", "9007199254740992"]) {
    const f = editorFixture();
    f.elements["draft-price"].value = price;
    await f.elements["draft-submit"].dispatch("click");
    assert.equal(f.requests.length, 0, `invalid price ${price}`);
    assert.match(f.elements["draft-status"].textContent, /positive.*whole/i);
  }
  const f = editorFixture();
  f.elements["draft-teaser"].value = "";
  await f.elements["draft-submit"].dispatch("click");
  assert.equal(f.requests.length, 0);
  assert.match(f.elements["draft-status"].textContent, /teaser/i);
});

test("revision conflict preserves edits and blocks blind retries", async () => {
  const f = editorFixture({ response: () => response({ error: {
    code: "version_conflict", message: "A newer draft exists." } }, 409) });
  f.elements["draft-body"].value = "Keep this unsaved story.";
  await f.elements["draft-form"].dispatch("submit");
  assert.equal(f.elements["draft-body"].value, "Keep this unsaved story.");
  assert.equal(f.elements["draft-body"].readOnly, false);
  assert.equal(f.elements["draft-conflict"].hidden, false);
  assert.match(f.elements["draft-conflict"].textContent, /copy.*reload/i);
  await f.elements["draft-form"].dispatch("submit");
  assert.equal(f.requests.length, 1);
});

test("editor errors retain the private story and restore save controls", async () => {
  const f = editorFixture({ response: () => { throw new Error("offline"); } });
  const original = f.elements["draft-body"].value;
  await f.elements["draft-form"].dispatch("submit");
  assert.equal(f.elements["draft-body"].value, original);
  assert.equal(f.elements["draft-save"].disabled, false);
  assert.match(f.elements["draft-status"].textContent, /try again/i);
});

test("the exact saved revision cannot be edited while review submission is in flight", async () => {
  let finishSubmit;
  const f = editorFixture({ response: url => url.endsWith("/submit")
    ? new Promise(resolve => { finishSubmit = resolve; })
    : response({ draft_id: "draft-1", version: 4, status: "draft" }) });
  const pending = f.elements["draft-submit"].dispatch("click");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.requests.length, 2);
  for (const key of ["body", "title", "teaser", "price", "taxonomy"]) {
    assert.equal(f.elements[`draft-${key}`].readOnly, true, `${key} must match the submitted revision`);
  }
  finishSubmit(response({ draft_id: "draft-1", version: 5, status: "submitted" }));
  await pending;
  assert.equal(f.elements["draft-body"].readOnly, true);
});

test("editing during save preserves new text and requires another explicit submission", async () => {
  let finishSave;
  const f = editorFixture({ response: () => new Promise(resolve => { finishSave = resolve; }) });
  const pending = f.elements["draft-submit"].dispatch("click");
  f.elements["draft-body"].value = "I asked a new question while saving.";
  await f.elements["draft-body"].dispatch("input");
  finishSave(response({ draft_id: "draft-1", version: 4, status: "draft" }));
  await pending;
  assert.equal(f.requests.length, 1);
  assert.equal(f.elements["draft-body"].value, "I asked a new question while saving.");
  assert.match(f.elements["draft-status"].textContent, /changed.*review.*submit again/i);
  assert.equal(f.elements["draft-submit"].disabled, false);
});

test("editor dictation errors and stopping never discard draft text", async () => {
  const f = editorFixture();
  assert.equal(f.instances.length, 0);
  await f.elements["story-dictation-toggle"].dispatch("click");
  transcript(f.instances[0], "I asked, rather than completed.");
  await f.elements["draft-submit"].dispatch("click");
  assert.equal(f.requests.length, 0);
  assert.equal(f.instances[0].stops, 1);
  f.instances[0].onerror({ error: "not-allowed" });
  assert.match(f.elements["draft-body"].value, /I asked, rather than completed/);
  assert.match(f.elements["story-dictation-status"].textContent, /blocked/i);
  assert.equal(f.elements["draft-body"].readOnly, false);
});

test("preview renders supplied narrative and metadata as inert text", async () => {
  const f = editorFixture();
  f.elements["draft-title"].value = '<img src=x onerror="alert(1)">';
  f.elements["draft-body"].value = "<script>private story</script>";
  await f.elements["draft-title"].dispatch("input");
  await f.elements["draft-body"].dispatch("input");
  assert.equal(f.elements["preview-title"].textContent, '<img src=x onerror="alert(1)">');
  assert.equal(f.elements["preview-body"].textContent, "<script>private story</script>");
  assert.equal(f.elements["preview-body"].children.length, 0);
});

const pythonCandidates = [process.env.SAARIV_TEST_PYTHON,
  fileURLToPath(new URL(".venv-rag/bin/python", repository)),
  fileURLToPath(new URL("../../.venv-rag/bin/python", repository))].filter(Boolean);
const python = pythonCandidates.find(filename => fs.existsSync(filename)) ?? "python3";
function render(template, values = {}) {
  assert.ok(fs.existsSync(new URL(`templates/marketplace/${template}.html`, repository)),
    `${template} template must exist`);
  const run = spawnSync(python, ["-c", `
import json, sys
from flask import Flask, render_template
app = Flask(__name__, template_folder="templates")
app.jinja_env.globals["csrf_token"] = lambda: "fixture-csrf"
values = json.load(sys.stdin)
with app.test_request_context("/"):
    print(render_template("marketplace/" + sys.argv[1] + ".html", **values))
`, template], { cwd: fileURLToPath(repository), input: JSON.stringify({
    principal: { user_id: null }, wallet: null, search_page: null, initial_query: "", draft: null,
    experience: card(), access_state: "locked", content: null, query_id: null, ...values }),
    encoding: "utf8", env: { ...process.env, DOTENV_DISABLED: "1" } });
  assert.equal(run.status, 0, run.stderr);
  return run.stdout;
}

test("home fixture renders guest privacy, login resume links, and auth-guarded plus", () => {
  const html = render("home", { initial_query: "PRIVATE_QUERY", search_page: page({ items: [card("exp-1", {
    author: { display_name: "CANARY_REAL_NAME", avatar_url: "CANARY_AVATAR", user_id: "CANARY_ID" },
    body: "CANARY_FULL_STORY", sources: ["CANARY_SOURCE"] })] }) });
  assert.equal(html.includes("CANARY"), false);
  assert.match(html, /href="\/experiences\/new"/);
  assert.match(html, /next=%2Fexperiences%2Fexp-1&amp;query_id=opaque-query-1/);
  assert.match(html, /name="csrf-token" content="fixture-csrf"/);
  const loginHrefs = [...html.matchAll(/href="(\/login[^\"]*)"/g)].map(match => match[1]);
  assert.equal(loginHrefs.some(href => href.includes("PRIVATE_QUERY")), false);
});

test("signed in header displays only a supplied wallet balance", () => {
  const html = render("home", { principal: { user_id: "synthetic-reader" }, wallet: { available_coins: 125 } });
  assert.match(html, /125 coins/);
  assert.match(html, /href="\/wallet"/);
  assert.doesNotMatch(render("home", { principal: { user_id: "synthetic-reader" } }), /0 coins/);
});

test("locked experience HTML excludes full content even if accidentally present in context", () => {
  const html = render("experience", { principal: { user_id: "synthetic-reader" },
    content: { body: "CANARY_PRIVATE_BODY", sources: ["CANARY_SOURCE"] }, access_state: "locked" });
  assert.equal(html.includes("CANARY"), false);
  assert.match(html, /disabled[^>]*>\s*Unlock for 25 coins/s);
  assert.doesNotMatch(html, /\/api\/experiences\/.*\/(quote|unlock)/);
});

test("authorized experience HTML preserves exact asked/planned/completed wording and escapes markup", () => {
  const html = render("experience", { principal: { user_id: "synthetic-reader" }, access_state: "author",
    content: { body: "I asked about housing.\nI planned a move.\nI completed no move. <script>alert(1)</script>" } });
  assert.match(html, /I asked about housing\.\nI planned a move\.\nI completed no move\. &lt;script&gt;/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /Unlock for/);
});

test("guest detail cannot render content with a forged unlocked context", () => {
  const html = render("experience", { access_state: "unlocked", content: { body: "CANARY_PRIVATE_BODY" } });
  assert.equal(html.includes("CANARY"), false);
  assert.match(html, /Sign in/);
});

test("editor fixture keeps private narrative in escaped author-only inputs and preview", () => {
  const html = render("editor", { principal: { user_id: "synthetic-author" },
    draft: draft({ body: "I planned a move. </textarea><script>unsafe()</script>" }) });
  assert.match(html, /I planned a move\. &lt;\/textarea&gt;&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>unsafe/);
  assert.match(html, /name="csrf-token" content="fixture-csrf"/);
  assert.match(html, /Private draft/);
  assert.match(html, /Submit for review/);
});

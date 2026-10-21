import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

const script = fs.readFileSync(new URL("../static/js/main.js", import.meta.url), "utf8");
const dictationScript = fs.readFileSync(new URL("../static/js/story-dictation.js", import.meta.url), "utf8");

function setup(fetchResponse, extraElements = {}) {
  const hidden = new Set(["hidden"]);
  const panel = {
    classList: { add: value => hidden.add(value), remove: value => hidden.delete(value) },
    scrollIntoView() {},
  };
  const input = { value: "" };
  const error = { textContent: "", classList: { add() {}, remove() {} } };
  const elements = { step4_story: input, step4_pasted_json: input, step4_error: error, "step-panel-5": panel, ...extraElements };
  const requests = [];
  const context = vm.createContext({
    localStorage: { getItem: () => null, setItem() {} }, window: {},
    FormData: class { constructor() { this.items = []; } append(key, value) { this.items.push([key, value]); } },
    document: {
      getElementById: id => elements[id] || null,
      querySelector: () => null, addEventListener() {},
    },
    fetch: async (url, options) => {
      requests.push({ url, body: typeof options.body === "string" ? JSON.parse(options.body) : options.body });
      return fetchResponse();
    },
  });
  vm.runInContext(dictationScript, context);
  vm.runInContext(script, context);
  return { context, input, error, hidden, requests };
}

test("pasted story is submitted without JSON parsing and advances after saving", async () => {
  const f = setup(() => ({ ok: true, json: async () => ({ ok: true, indexed_count: 2 }) }));
  f.input.value = "## Relocation\nYou asked about housing.\n\n## Career\nYou compared two roles.";
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(f.requests.length, 1);
  assert.equal(f.requests[0].body.experience_story, f.input.value);
  assert.equal(f.requests[0].url, "/api/onboarding/step4");
  assert.equal(f.hidden.has("hidden"), false);
});

test("a rejected story stays on the import step and shows the server error", async () => {
  const f = setup(() => ({ ok: false, json: async () => ({ ok: false, message: "Please include story paragraphs." }) }));
  f.input.value = "## Relocation";
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(f.hidden.has("hidden"), true);
  assert.equal(f.error.textContent, "Please include story paragraphs.");
});

test("a network error does not advance past an unsaved story", async () => {
  const f = setup(() => { throw new Error("offline"); });
  f.input.value = "You asked about housing.";
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(f.hidden.has("hidden"), true);
  assert.match(f.error.textContent, /save.*story/i);
});

test("Load Sample fills the input with a readable story", () => {
  const f = setup(() => {});
  vm.runInContext("loadSampleExperiences()", f.context);
  assert.ok(f.input.value.includes("I asked"));
  assert.throws(() => JSON.parse(f.input.value));
});

test("story submission adopts the server issued avatar id", async () => {
  const f = setup(() => ({ ok: true, json: async () => ({ ok: true, session_id: "server-owned-id" }) }));
  f.input.value = "You asked about housing.";
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(vm.runInContext("onboardingState.sessionId", f.context), "server-owned-id");
});

test("browser imports rely on the signed cookie so a failed first import can be retried", async () => {
  const f = setup(() => ({ ok: false, json: async () => ({ ok: false, message: "API unavailable" }) }));
  f.input.value = "You asked about housing.";
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(Object.hasOwn(f.requests[0].body, "session_id"), false);
});

test("direct playground navigation refreshes index migration status", () => {
  const f = setup(() => {});
  vm.runInContext("var statusRefreshes = 0; refreshKnowledgeStatus = () => statusRefreshes++; goToStep(6);", f.context);
  assert.equal(vm.runInContext("statusRefreshes", f.context), 1);
});

function step5Fixture(response, files = []) {
  const error = { textContent: "", classList: { add() {}, remove() {} } };
  const f = setup(response, {
    step5_error: error, step5_custom_text: { value: "You asked about deposits." },
    step5_topic_tag: { value: "Housing" }, step5_file_upload: { files },
  });
  vm.runInContext("var transitions = []; setupPlayground = () => {}; goToStep = step => transitions.push(step);", f.context);
  return { ...f, error };
}

test("failed additional indexing stays on step 5 and displays the error", async () => {
  const f = step5Fixture(() => ({ ok: false, json: async () => ({ ok: false, message: "Embedding service unavailable" }) }));
  await vm.runInContext("handleStep5Submit()", f.context);
  assert.equal(vm.runInContext("transitions.length", f.context), 0);
  assert.equal(f.error.textContent, "Embedding service unavailable");
});

test("PDF and text files are sent individually to the backend", async () => {
  const f = step5Fixture(() => ({ ok: true, json: async () => ({ ok: true }) }), [
    { name: "journey.pdf" }, { name: "notes.txt" },
  ]);
  await vm.runInContext("handleStep5Submit()", f.context);
  assert.equal(f.requests[0].url, "/api/onboarding/step5-files");
  assert.deepEqual(f.requests[0].body.items.filter(([key]) => key === "files").map(([, file]) => file.name),
    ["journey.pdf", "notes.txt"]);
});

test("source excerpts and filenames are rendered as text nodes", () => {
  const f = setup(() => {});
  const root = { children: [], appendChild(child) { this.children.push(child); } };
  f.context.document.createElement = tag => ({
    tag, children: [], textContent: "", appendChild(child) { this.children.push(child); },
    set innerHTML(value) { throw new Error("Sources must not be inserted as HTML"); },
  });
  f.context.sourceRoot = root;
  vm.runInContext(`appendKnowledgeSources(sourceRoot, [{
    citation_id: "S1", text: "<img src=x onerror=alert(1)>",
    source: { title: "<script>unsafe</script>", section: "Housing", page_start: 1, page_end: 2 }
  }])`, f.context);
  assert.equal(root.children[0].children[1].textContent, "<img src=x onerror=alert(1)>");
});

test("first-person evidence is displayed without rewriting the raw citation", () => {
  const f = setup(() => {});
  const root = { children: [], appendChild(child) { this.children.push(child); } };
  f.context.document.createElement = tag => ({
    tag, children: [], textContent: "", appendChild(child) { this.children.push(child); },
  });
  f.context.sourceRoot = root;
  vm.runInContext(`evidence = {citation_id: "S1", text: "You asked about housing.",
    display_text: "I asked about housing.", source: {title: "Story", start: 0, end: 24}};
    appendKnowledgeSources(sourceRoot, [evidence]);`, f.context);
  assert.equal(root.children[0].children[1].textContent, "I asked about housing.");
  assert.equal(vm.runInContext("evidence.text", f.context), "You asked about housing.");
});

function dictationFixture(supported = true) {
  const toggle = { disabled: false, setAttribute(name, value) { this[name] = value; } };
  const save = { disabled: false };
  const status = { textContent: "" };
  const f = setup(() => ({ ok: true, json: async () => ({ ok: true, indexed_count: 1 }) }), {
    "story-dictation-toggle": toggle, "story-dictation-label": { textContent: "" },
    "story-dictation-status": status, "step4-submit-btn": save,
  });
  const recognitions = [];
  class Recognition {
    constructor() { recognitions.push(this); }
    start() {}
    stop() {}
    abort() {}
  }
  if (supported) f.context.window.SpeechRecognition = Recognition;
  f.context.window.addEventListener = () => {};
  f.context.navigator = { language: "en-IN" };
  f.context.Event = class {};
  f.input.dispatchEvent = () => {};
  assert.equal(vm.runInContext("typeof initializeStoryDictation", f.context), "function");
  vm.runInContext("initializeStoryDictation()", f.context);
  return { ...f, toggle, save, status, recognitions };
}

test("dictation blocks early submission, then saves the reviewed text through the existing endpoint", async () => {
  const f = dictationFixture();
  f.input.value = "I compared deposits.";
  vm.runInContext("toggleStoryDictation()", f.context);
  f.recognitions[0].onstart();
  assert.equal(f.input.readOnly, true);
  assert.equal(f.save.disabled, true);
  assert.equal(f.toggle["aria-pressed"], "true");
  f.recognitions[0].onresult({ results: [[{ transcript: "I asked about leases." }]] });
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(f.requests.length, 0);
  assert.match(f.error.textContent, /stop.*dictation/i);
  vm.runInContext("toggleStoryDictation()", f.context);
  assert.equal(f.save.disabled, true);
  f.recognitions[0].onend();
  assert.equal(f.input.readOnly, false);
  assert.equal(f.save.disabled, false);
  f.input.value += " No contract was signed.";
  await vm.runInContext("handleStep4Submit()", f.context);
  assert.equal(f.requests[0].url, "/api/onboarding/step4");
  assert.equal(f.requests[0].body.experience_story, "I compared deposits.\n\nI asked about leases. No contract was signed.");
});

test("leaving the story panel cancels dictation without losing the transcript", () => {
  const f = dictationFixture();
  vm.runInContext("toggleStoryDictation()", f.context);
  f.recognitions[0].onresult({ results: [[{ transcript: "I prepared for interviews." }]] });
  vm.runInContext("goToStep(3)", f.context);
  f.recognitions[0].onresult({ results: [[{ transcript: "Late words must be ignored." }]] });
  assert.equal(f.input.value, "I prepared for interviews.");
  assert.equal(f.input.readOnly, false);
  assert.equal(f.toggle["aria-pressed"], "false");
});

test("an unsupported browser keeps manual story entry and Continue available", () => {
  const f = dictationFixture(false);
  assert.equal(f.toggle.disabled, true);
  assert.equal(f.input.readOnly, false);
  assert.equal(f.save.disabled, false);
  assert.match(f.status.textContent, /not available.*browser/i);
});

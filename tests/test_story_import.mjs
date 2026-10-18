import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

const script = fs.readFileSync(new URL("../static/js/main.js", import.meta.url), "utf8");

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
  assert.ok(f.input.value.includes("You asked"));
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

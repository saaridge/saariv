import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = new URL("../static/js/story-dictation.js", import.meta.url);
const script = fs.existsSync(source) ? fs.readFileSync(source, "utf8") : "";

function fixture(initialText = "", options = {}) {
  const context = vm.createContext({});
  vm.runInContext(script, context);
  const Controller = vm.runInContext("typeof StoryDictation === 'function' ? StoryDictation : null", context);
  assert.equal(typeof Controller, "function", "The story dictation controller is available");
  const instances = [];
  class Recognition {
    constructor() { instances.push(this); }
    start() { if (options.startError) throw options.startError; }
    stop() {}
    abort() {}
  }
  let text = initialText;
  let state;
  const controller = new Controller({
    Recognition: options.unsupported ? undefined : Recognition,
    getText: () => text,
    setText: value => { text = value; },
    onState: value => { state = value; },
    lang: "en-IN",
  });
  return { controller, instances, get text() { return text; }, set text(value) { text = value; }, get state() { return state; } };
}

function result(recognition, ...segments) {
  recognition.onresult({ results: segments.map(([text, final]) => Object.assign([{ transcript: text }], { isFinal: final })) });
}

test("opening the page does not start microphone capture", () => {
  const f = fixture();
  assert.equal(f.instances.length, 0);
  assert.equal(f.state.phase, "idle");
  assert.equal(f.controller.busy, false);
});

test("revised interim and repeated final results do not duplicate words or replace typed text", () => {
  const f = fixture("## Housing\nI compared deposits.");
  f.controller.start();
  const recognition = f.instances[0];
  recognition.onstart();
  result(recognition, ["I asked about", false]);
  assert.equal(f.text, "## Housing\nI compared deposits.\n\nI asked about");
  result(recognition, ["I asked about leases.", true], ["I planned", false]);
  result(recognition, ["I asked about leases.", true], ["I planned to relocate.", true]);
  result(recognition, ["I asked about leases.", true], ["I planned to relocate.", true]);
  assert.equal(f.text, "## Housing\nI compared deposits.\n\nI asked about leases. I planned to relocate.");
});

test("removed interim hypotheses disappear while the original story remains", () => {
  const f = fixture("My original story.");
  f.controller.start();
  result(f.instances[0], ["Something misheard", false]);
  result(f.instances[0]);
  assert.equal(f.text, "My original story.");
});

test("stop waits for the final transcript before allowing submission", () => {
  const f = fixture();
  f.controller.start();
  f.controller.stop();
  assert.equal(f.state.phase, "stopping");
  assert.equal(f.controller.busy, true);
  result(f.instances[0], ["I prepared for interviews.", true]);
  f.instances[0].onend();
  assert.equal(f.controller.busy, false);
  assert.equal(f.text, "I prepared for interviews.");
  assert.match(f.state.message, /review/i);
});

test("a second dictation appends to the user's edited draft", () => {
  const f = fixture();
  f.controller.start();
  result(f.instances[0], ["I compared two roles.", true]);
  f.instances[0].onend();
  f.text = "I compared three roles.";
  f.controller.start();
  result(f.instances[1], ["No offer was documented.", true]);
  assert.equal(f.text, "I compared three roles.\n\nNo offer was documented.");
});

test("blocked microphone permission preserves the draft and permits retry", () => {
  const f = fixture("Keep this story.");
  f.controller.start();
  f.instances[0].onerror({ error: "not-allowed" });
  assert.equal(f.controller.busy, false);
  assert.match(f.state.message, /microphone.*blocked/i);
  assert.equal(f.text, "Keep this story.");
  f.controller.start();
  assert.equal(f.state.phase, "starting");
});

test("unavailable speech recognition leaves typing available", () => {
  const f = fixture("Typed story.", { unsupported: true });
  f.controller.start();
  assert.equal(f.state.phase, "unsupported");
  assert.equal(f.controller.busy, false);
  assert.equal(f.text, "Typed story.");
  assert.match(f.state.message, /type|paste/i);
});

test("cancelling a session ignores its late results and keeps the visible draft", () => {
  const f = fixture();
  f.controller.start();
  const old = f.instances[0];
  result(old, ["I asked about housing.", false]);
  f.controller.cancel();
  f.controller.start();
  result(old, ["Wrong late result.", true]);
  old.onend();
  assert.equal(f.state.phase, "starting");
  assert.equal(f.text, "I asked about housing.");
  result(f.instances[1], ["I compared deposits.", true]);
  assert.equal(f.text, "I asked about housing.\n\nI compared deposits.");
});

test("a browser start error restores a usable editor without losing text", () => {
  const f = fixture("My draft.", { startError: Object.assign(new Error("blocked"), { name: "NotAllowedError" }) });
  f.controller.start();
  assert.equal(f.controller.busy, false);
  assert.equal(f.state.phase, "error");
  assert.equal(f.text, "My draft.");
});

test("an automatic recognition end does not restart the microphone", () => {
  const f = fixture();
  f.controller.start();
  f.instances[0].onend();
  assert.equal(f.instances.length, 1);
  assert.equal(f.state.phase, "idle");
});

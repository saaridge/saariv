// Browser speech recognition writes an editable draft; saving stays in the story flow.
class StoryDictation {
  constructor({ Recognition, getText, setText, onState, lang = "en-US" }) {
    this.Recognition = Recognition;
    this.getText = getText;
    this.setText = setText;
    this.onState = onState;
    this.lang = lang;
    this.recognition = null;
    this.supported = typeof Recognition === "function";
    this.update(this.supported ? "idle" : "unsupported", this.supported
      ? "Speak to add to your story, then stop to review and edit."
      : "Voice dictation is not available in this browser. You can still type or paste your story.");
  }

  get busy() {
    return ["starting", "listening", "stopping"].includes(this.phase);
  }

  update(phase, message) {
    this.phase = phase;
    this.onState({ phase, message, busy: this.busy, supported: this.supported });
  }

  start() {
    if (!this.supported || this.busy) return;
    const original = this.getText();
    let recognition;
    try {
      recognition = new this.Recognition();
      this.recognition = recognition;
      recognition.lang = this.lang;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        if (this.recognition === recognition && this.phase !== "stopping") {
          this.update("listening", "Listening… Speak about your experience. Stop dictation to edit your story.");
        }
      };
      recognition.onresult = event => {
        if (this.recognition !== recognition) return;
        // The event contains the complete session, including revised interim results.
        // Rebuild that suffix instead of appending the same final words twice.
        const spoken = Array.from(event.results, result => result[0].transcript.trim()).filter(Boolean).join(" ");
        const separator = original && spoken && !/\s$/.test(original) ? "\n\n" : "";
        this.setText(original + separator + spoken);
      };
      recognition.onend = () => {
        if (this.recognition !== recognition) return;
        this.recognition = null;
        this.update("idle", "Dictation stopped. Review and edit your story before continuing.");
      };
      recognition.onerror = event => {
        if (this.recognition !== recognition) return;
        this.fail(event.error, recognition);
      };
      this.update("starting", "Waiting for microphone access… Allow access in your browser to begin.");
      recognition.start();
    } catch (error) {
      this.fail(error.name === "NotAllowedError" ? "not-allowed" : "start-failed", recognition);
    }
  }

  stop() {
    if (!this.recognition || !this.busy || this.phase === "stopping") return;
    this.update("stopping", "Finishing dictation… Waiting for the final words.");
    try {
      this.recognition.stop();
    } catch (_) {
      this.fail("start-failed", this.recognition);
    }
  }

  cancel() {
    if (!this.recognition) return;
    const recognition = this.recognition;
    this.recognition = null;
    try { recognition.abort(); } catch (_) { /* Already ended. */ }
    this.update("idle", "Dictation stopped. Review and edit your story before continuing.");
  }

  fail(reason, recognition) {
    this.recognition = null;
    try { recognition?.abort(); } catch (_) { /* Preserve the draft if the browser already stopped. */ }
    const messages = {
      "not-allowed": "Microphone access was blocked. Allow microphone access in your browser, then try again.",
      "service-not-allowed": "Speech recognition is blocked in this browser. You can still type or paste your story.",
      "audio-capture": "No microphone is available. Connect a microphone, then try again.",
      "no-speech": "No speech was detected. Try again when you are ready, or type your story.",
      "network": "Speech recognition could not connect. Check your connection and try again, or type your story.",
      "language-not-supported": "Speech recognition does not support your browser's language. You can still type or paste your story.",
    };
    this.update("error", messages[reason] || "Dictation could not start. Your draft is preserved; try again or type your story.");
  }
}

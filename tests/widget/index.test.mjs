// The shipped widget's inline script, driven with fake fetch responses — no
// network. `tests/test_widget.py` runs this file through `node` when it is
// installed; every refusal row of the task's I/O matrix lives here, next to
// the HTML it pins.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
  path.resolve(here, "..", "..", "widget", "index.html"),
  "utf8",
);
const script = /<script>([\s\S]*?)<\/script>/.exec(html)?.[1];
assert.ok(script, "the widget's inline script was not found in widget/index.html");
const serviceUrl = /const SERVICE_URL = "([^"]+)";/.exec(html)?.[1];
assert.ok(serviceUrl, "the widget's SERVICE_URL constant was not found");

// A DOM of plain records: the handlers the script registers are captured on
// the elements so the tests can drive them directly.
function widgetRuntime() {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        hidden: true,
        textContent: "",
        className: "",
        disabled: false,
        value: "",
        listeners: new Map(),
        addEventListener(type, handler) {
          this.listeners.set(type, handler);
        },
      });
    }
    return elements.get(id);
  };
  const fetchCalls = [];
  let respond = async () => {
    throw new Error("the test did not stage a fetch response");
  };
  const sandbox = {
    document: { getElementById: element },
    fetch: async (url, init) => {
      fetchCalls.push({ url, init });
      return respond();
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(script, sandbox);
  return {
    element,
    fetchCalls,
    stage: (response) => {
      respond = async () => response;
    },
    submit: async (question) => {
      element("question").value = question;
      await element("ask").listeners.get("submit")({ preventDefault() {} });
    },
  };
}

function response({ status, body, headers = {}, bodyFails = false }) {
  const lowered = new Map(
    Object.entries(headers).map(([name, value]) => [name.toLowerCase(), value]),
  );
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => lowered.get(name.toLowerCase()) ?? null },
    json: bodyFails ? async () => { throw new TypeError("not JSON"); } : async () => body,
  };
}

function assertIdleState(w) {
  assert.equal(w.element("loading").hidden, true);
  assert.equal(w.element("ask-button").disabled, false);
}

test("the submit posts exactly one JSON body to the service URL", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 200,
      body: { status: "answered", answer: "A.", citations: [{ source: "s.org" }] },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(w.fetchCalls.length, 1);
  const { url, init } = w.fetchCalls[0];
  assert.equal(url, serviceUrl);
  assert.equal(init.method, "POST");
  assert.deepEqual(JSON.parse(init.body), { question: "What is your search experience?" });
});

test("a rate 429 with Retry-After renders the wait in minutes", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 429,
      body: { detail: "too many requests" },
      headers: { "Retry-After": "115" },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "Too many questions from this address — try again in about 2 minutes.",
  );
  assert.equal(w.element("error").hidden, false);
  assert.equal(w.element("reply").hidden, true);
  assertIdleState(w);
});

test("a rate 429 rounds the wait up: 300 s is about 5 minutes", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 429,
      body: { detail: "too many requests" },
      headers: { "Retry-After": "300" },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "Too many questions from this address — try again in about 5 minutes.",
  );
});

test("a rate 429 without a readable Retry-After renders the copy without a number", async () => {
  const w = widgetRuntime();
  w.stage(response({ status: 429, body: { detail: "too many requests" } }));
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "Too many questions from this address — try again later.",
  );
});

test("a rate 429 with a sub-minute Retry-After renders the copy without a number", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 429,
      body: { detail: "too many requests" },
      headers: { "Retry-After": "0" },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "Too many questions from this address — try again later.",
  );
});

test("a daily-quota 429 renders the daily-limit copy, keyed on the stable detail", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 429,
      body: { detail: "the daily model-call quota is exhausted" },
      headers: { "Retry-After": "43200" },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "The daily question limit has been reached — please try again tomorrow.",
  );
});

test("a 413 keeps the raw {detail} rendering", async () => {
  const w = widgetRuntime();
  w.stage(response({ status: 413, body: { detail: "request body too large" } }));
  await w.submit("What is your search experience?");

  assert.equal(w.element("error").textContent, "413: request body too large");
});

test("a 422 keeps the raw {detail} rendering", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 422,
      body: { detail: "question exceeds the maximum length of 2000 characters" },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "422: question exceeds the maximum length of 2000 characters",
  );
});

test("a 5xx keeps the raw {detail} rendering", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 500,
      body: { detail: "the service failed to process the request" },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(
    w.element("error").textContent,
    "500: the service failed to process the request",
  );
});

test("a non-JSON 429 body keeps the generic refusal copy", async () => {
  const w = widgetRuntime();
  w.stage(response({ status: 429, body: null, bodyFails: true }));
  await w.submit("What is your search experience?");

  assert.equal(w.element("error").textContent, "429: the service refused the request");
});

test("an answered reply renders the answer and its citations", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 200,
      body: {
        status: "answered",
        answer: "Search infrastructure.",
        citations: [{ source: "profile.org" }],
      },
    }),
  );
  await w.submit("What is your search experience?");

  assert.equal(w.element("answer").textContent, "Search infrastructure.");
  assert.equal(
    w.element("citations").textContent,
    "Cited sources: profile.org",
  );
  assert.equal(w.element("reply").className, "answered");
  assert.equal(w.element("error").hidden, true);
  assertIdleState(w);
});

test("an insufficient reply renders the decline copy without citations", async () => {
  const w = widgetRuntime();
  w.stage(
    response({
      status: 200,
      body: { status: "insufficient", answer: "I answer only from my public profile.", citations: [] },
    }),
  );
  await w.submit("What is the weather tomorrow?");

  assert.equal(
    w.element("answer").textContent,
    "I answer only from my public profile.",
  );
  assert.equal(w.element("citations").textContent, "");
  assert.equal(w.element("reply").className, "declined");
});

test("a blank question refuses locally without calling the service", async () => {
  const w = widgetRuntime();
  await w.submit("   ");

  assert.equal(w.element("error").textContent, "Please type a question first.");
  assert.equal(w.fetchCalls.length, 0);
});

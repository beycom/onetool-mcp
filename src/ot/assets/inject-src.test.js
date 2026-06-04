import { readFile } from "node:fs/promises";
import test from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";
import { JSDOM } from "jsdom";

const source = await readFile(new URL("./inject-src.js", import.meta.url), "utf8");

test("inject script supports cleanup and idempotent reinjection", async () => {
  const dom = new JSDOM("<!doctype html><button id='target'>Inspect me</button>", {
    runScripts: "dangerously",
    url: "https://en.wikipedia.org/wiki/Anthropic",
  });
  installBrowserShims(dom.window);

  dom.window.eval(await bundleForEval());
  assert.equal(dom.window.__inspector.isReady(), true);

  const added = dom.window.__inspector.addAnnotation("#target", "target", "Target", "blue");
  assert.equal(added.success, true);
  assert.equal(added.count, 1);
  assert.deepEqual([...added.ids], ["target"]);
  assert.equal(dom.window.document.querySelectorAll("[x-inspect]").length, 1);

  const disposed = dom.window.__inspector.dispose();
  assert.equal(disposed.success, true);
  assert.equal(dom.window.__inspector, undefined);
  assert.equal(dom.window.document.querySelectorAll("[x-inspect]").length, 0);
  assert.equal(dom.window.document.querySelector("#__inspector-overlays"), null);

  dom.window.eval(await bundleForEval());
  assert.equal(dom.window.__inspector.isReady(), true);
});

test("clear annotations returns the same shape used by browser adapters", async () => {
  const dom = new JSDOM("<!doctype html><main><h1>Heading</h1><p>Body</p></main>", {
    runScripts: "dangerously",
    url: "https://en.wikipedia.org/wiki/Anthropic",
  });
  installBrowserShims(dom.window);
  dom.window.eval(await bundleForEval());

  dom.window.__inspector.addAnnotation("h1", "heading", "Heading", "orange");
  const scanned = dom.window.__inspector.scanAnnotations();
  assert.equal(scanned.length, 1);
  assert.equal(scanned[0].id, "heading");
  assert.equal(scanned[0].tagName, "h1");

  const cleared = dom.window.__inspector.clearAnnotations();
  assert.equal(cleared.success, true);
  assert.equal(cleared.cleared, 1);
});

async function bundleForEval() {
  const result = await build({
    stdin: {
      contents: source,
      resolveDir: new URL(".", import.meta.url).pathname,
      loader: "js",
    },
    bundle: true,
    format: "iife",
    target: "es2020",
    write: false,
  });
  return result.outputFiles[0].text;
}

function installBrowserShims(window) {
  window.requestAnimationFrame = (callback) => window.setTimeout(callback, 0);
  window.cancelAnimationFrame = (id) => window.clearTimeout(id);
  window.prompt = () => "selected";
}

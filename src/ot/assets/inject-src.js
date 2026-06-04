/**
 * inject.js v2.0 — Universal element annotation system
 *
 * Features:
 * - Bulletproof CSS selectors via optimal-select
 * - SPA support via MutationObserver with debounce
 * - 4 colour schemes (orange, red, blue, green)
 * - Viewport-aware smart label positioning
 * - Debounced scroll/resize handlers (150ms + RAF)
 * - Ctrl+I / Cmd+I manual selection mode
 */

import { select } from "optimal-select";

(function () {
  "use strict";

  // Skip if already initialised
  if (window.__inspector && window.__inspector.isReady()) return;

  // ── Colour schemes ──────────────────────────────────────────────────
  const COLORS = {
    orange: { border: "#f59e0b", bg: "rgba(245,158,11,0.12)", label: "#f59e0b", text: "#fff" },
    red:    { border: "#ef4444", bg: "rgba(239,68,68,0.12)",   label: "#ef4444", text: "#fff" },
    blue:   { border: "#3b82f6", bg: "rgba(59,130,246,0.12)",  label: "#3b82f6", text: "#fff" },
    green:  { border: "#22c55e", bg: "rgba(34,197,94,0.12)",   label: "#22c55e", text: "#fff" },
  };

  const DEFAULT_COLOR = "orange";

  // ── State ───────────────────────────────────────────────────────────
  const overlayContainer = document.createElement("div");
  overlayContainer.id = "__inspector-overlays";
  overlayContainer.style.cssText = "position:fixed;top:0;left:0;width:0;height:0;z-index:2147483646;pointer-events:none;";
  document.documentElement.appendChild(overlayContainer);

  let selectionMode = false;
  let annotationCounter = 0;

  // ── Helpers ─────────────────────────────────────────────────────────

  function getSelector(el) {
    try {
      return select(el, { root: document });
    } catch {
      // Fallback: build a simple selector
      if (el.id) return "#" + CSS.escape(el.id);
      const tag = el.tagName.toLowerCase();
      const classes = Array.from(el.classList).map((c) => "." + CSS.escape(c)).join("");
      return tag + classes;
    }
  }

  function getColorScheme(name) {
    return COLORS[name] || COLORS[DEFAULT_COLOR];
  }

  function debounce(fn, ms) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function rafDebounce(fn, ms) {
    let timer;
    let rafId;
    return function (...args) {
      clearTimeout(timer);
      if (rafId) cancelAnimationFrame(rafId);
      timer = setTimeout(() => {
        rafId = requestAnimationFrame(() => fn.apply(this, args));
      }, ms);
    };
  }

  // ── Overlay rendering ──────────────────────────────────────────────

  function clearOverlays() {
    overlayContainer.innerHTML = "";
  }

  function renderHighlight(el, id, label, colorName) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return;

    const scheme = getColorScheme(colorName);

    // Highlight box
    const box = document.createElement("div");
    box.className = "__inspector-highlight";
    box.dataset.inspectId = id;
    box.style.cssText = [
      "position:fixed",
      `top:${rect.top}px`,
      `left:${rect.left}px`,
      `width:${rect.width}px`,
      `height:${rect.height}px`,
      `border:2px solid ${scheme.border}`,
      `background:${scheme.bg}`,
      "pointer-events:none",
      "box-sizing:border-box",
      "transition:all 0.15s ease",
    ].join(";");

    // Label
    const tag = document.createElement("div");
    tag.className = "__inspector-label";
    tag.textContent = label || id;

    // Smart positioning
    const labelH = 20;
    const flipBelow = rect.top < labelH;
    let labelTop = flipBelow ? rect.height + 2 : -(labelH + 2);
    let labelLeft = 0;

    // Horizontal clamping
    const labelWidth = Math.min(200, label ? label.length * 8 + 16 : 60);
    if (rect.left + labelWidth > window.innerWidth) {
      labelLeft = window.innerWidth - rect.left - labelWidth;
    }

    tag.style.cssText = [
      "position:absolute",
      `top:${labelTop}px`,
      `left:${labelLeft}px`,
      `background:${scheme.label}`,
      `color:${scheme.text}`,
      "font:bold 11px/18px system-ui,sans-serif",
      "padding:1px 6px",
      "border-radius:3px",
      "white-space:nowrap",
      "max-width:200px",
      "overflow:hidden",
      "text-overflow:ellipsis",
      "pointer-events:none",
    ].join(";");

    box.appendChild(tag);
    overlayContainer.appendChild(box);
  }

  function renderAll() {
    clearOverlays();
    const elements = document.querySelectorAll("[x-inspect]");
    elements.forEach((el) => {
      const id = el.getAttribute("x-inspect");
      const label = el.getAttribute("x-inspect-label") || id;
      const color = el.getAttribute("x-inspect-color") || DEFAULT_COLOR;
      renderHighlight(el, id, label, color);
    });
  }

  // ── Core API ───────────────────────────────────────────────────────

  function addAnnotation(selector, id, label, color) {
    const colorName = color || DEFAULT_COLOR;
    const elements = document.querySelectorAll(selector);
    if (elements.length === 0) {
      return { success: false, count: 0, ids: [], error: "No elements match selector" };
    }

    const ids = [];
    elements.forEach((el, i) => {
      const annotId = id || `ann-${++annotationCounter}`;
      const finalId = elements.length > 1 ? `${annotId}-${i}` : annotId;
      el.setAttribute("x-inspect", finalId);
      el.setAttribute("x-inspect-color", colorName);
      if (label) el.setAttribute("x-inspect-label", label);
      ids.push(finalId);
    });

    renderAll();
    return { success: true, count: elements.length, ids };
  }

  function removeAnnotation(selector) {
    const elements = document.querySelectorAll(selector);
    let removed = 0;
    elements.forEach((el) => {
      if (el.hasAttribute("x-inspect")) {
        el.removeAttribute("x-inspect");
        el.removeAttribute("x-inspect-color");
        el.removeAttribute("x-inspect-label");
        removed++;
      }
    });
    renderAll();
    return { success: true, removed };
  }

  function scanAnnotations() {
    const elements = document.querySelectorAll("[x-inspect]");
    return Array.from(elements).map((el) => ({
      id: el.getAttribute("x-inspect"),
      label: el.getAttribute("x-inspect-label") || el.getAttribute("x-inspect"),
      selector: getSelector(el),
      content: (el.textContent || "").trim().slice(0, 200),
      tagName: el.tagName.toLowerCase(),
      color: el.getAttribute("x-inspect-color") || DEFAULT_COLOR,
    }));
  }

  function clearAnnotations() {
    const elements = document.querySelectorAll("[x-inspect]");
    elements.forEach((el) => {
      el.removeAttribute("x-inspect");
      el.removeAttribute("x-inspect-color");
      el.removeAttribute("x-inspect-label");
    });
    clearOverlays();
    return { success: true, cleared: elements.length };
  }

  function isReady() {
    return true;
  }

  // ── SPA support (MutationObserver) ─────────────────────────────────

  const debouncedRender = debounce(() => {
    renderAll();
  }, 100);

  const observer = new MutationObserver((mutations) => {
    let addedCount = 0;
    for (const m of mutations) {
      addedCount += m.addedNodes.length;
    }
    if (addedCount > 5) {
      debouncedRender();
    }
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  // ── Scroll/resize handlers ─────────────────────────────────────────

  const debouncedScrollResize = rafDebounce(() => {
    renderAll();
  }, 150);

  window.addEventListener("scroll", debouncedScrollResize, { passive: true });
  window.addEventListener("resize", debouncedScrollResize, { passive: true });

  // ── Manual selection mode (Ctrl+I / Cmd+I) ────────────────────────

  let hoverOverlay = null;

  function enableSelectionMode() {
    selectionMode = true;
    document.body.style.cursor = "crosshair";
    document.addEventListener("mouseover", onSelectionHover, true);
    document.addEventListener("click", onSelectionClick, true);
  }

  function disableSelectionMode() {
    selectionMode = false;
    document.body.style.cursor = "";
    document.removeEventListener("mouseover", onSelectionHover, true);
    document.removeEventListener("click", onSelectionClick, true);
    if (hoverOverlay) {
      hoverOverlay.remove();
      hoverOverlay = null;
    }
  }

  function onSelectionHover(e) {
    if (!selectionMode) return;
    const el = e.target;
    if (el === overlayContainer || overlayContainer.contains(el)) return;

    if (hoverOverlay) hoverOverlay.remove();

    const rect = el.getBoundingClientRect();
    hoverOverlay = document.createElement("div");
    hoverOverlay.style.cssText = [
      "position:fixed",
      `top:${rect.top}px`,
      `left:${rect.left}px`,
      `width:${rect.width}px`,
      `height:${rect.height}px`,
      "border:2px dashed #f59e0b",
      "background:rgba(245,158,11,0.08)",
      "pointer-events:none",
      "z-index:2147483647",
      "box-sizing:border-box",
    ].join(";");
    document.documentElement.appendChild(hoverOverlay);
  }

  function onSelectionClick(e) {
    if (!selectionMode) return;
    const el = e.target;
    if (el === overlayContainer || overlayContainer.contains(el)) return;

    e.preventDefault();
    e.stopPropagation();

    // Prompt user for annotation label
    const tagName = el.tagName.toLowerCase();
    const defaultLabel = tagName;
    const userLabel = prompt(
      `Enter a name for this annotation (${tagName}):`,
      defaultLabel
    );

    // If user cancels, exit selection mode without adding annotation
    if (userLabel === null) {
      disableSelectionMode();
      return;
    }

    // Use user-provided label or fallback to tag name if empty
    const label = userLabel.trim() || defaultLabel;
    const id = `sel-${++annotationCounter}`;

    // Annotate the specific clicked element directly — do NOT use
    // addAnnotation(selector) here as querySelectorAll may match multiple elements
    el.setAttribute("x-inspect", id);
    el.setAttribute("x-inspect-color", DEFAULT_COLOR);
    el.setAttribute("x-inspect-label", label);
    renderAll();
    disableSelectionMode();
  }

  function onKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "i") {
      e.preventDefault();
      if (selectionMode) {
        disableSelectionMode();
      } else {
        enableSelectionMode();
      }
    }
  }

  document.addEventListener("keydown", onKeyDown);

  function dispose() {
    disableSelectionMode();
    observer.disconnect();
    window.removeEventListener("scroll", debouncedScrollResize);
    window.removeEventListener("resize", debouncedScrollResize);
    document.removeEventListener("keydown", onKeyDown);
    clearAnnotations();
    overlayContainer.remove();
    delete window.__inspector;
    return { success: true };
  }

  // ── Public API ─────────────────────────────────────────────────────

  window.__inspector = {
    addAnnotation,
    removeAnnotation,
    scanAnnotations,
    clearAnnotations,
    isReady,
    enableSelectionMode,
    disableSelectionMode,
    dispose,
    renderAll,
    version: "2.0.0",
  };
})();

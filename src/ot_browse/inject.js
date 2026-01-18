/**
 * Browser Inspector - Inject script
 *
 * Features:
 * 1. Highlight elements with x-inspect attribute (red box + label)
 * 2. Ctrl+I to select element, shows input popup for annotation
 */

(function() {
  if (window.__inspector) return;

  let selectMode = false;
  let hoverEl = null;
  let counter = 1;

  // Inject styles - refined color palette
  const style = document.createElement('style');
  style.textContent = `
    .__xi-highlight {
      position: absolute;
      pointer-events: none;
      border: 2px solid #f59e0b;
      background: rgba(245, 158, 11, 0.08);
      z-index: 2147483640;
    }
    .__xi-label {
      position: absolute;
      pointer-events: none;
      font: 11px/1.2 system-ui, -apple-system, sans-serif;
      padding: 3px 6px;
      background: #f59e0b;
      color: #1f2937;
      font-weight: 500;
      border-radius: 3px;
      z-index: 2147483640;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .__xi-hover {
      position: fixed;
      pointer-events: none;
      border: 2px solid #5c9aff;
      background: rgba(92, 154, 255, 0.15);
      z-index: 2147483645;
    }
    .__xi-modal {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 20px;
      z-index: 2147483647;
      font-family: system-ui, -apple-system, sans-serif;
      color: #f1f5f9;
      min-width: 320px;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.6);
    }
    .__xi-modal h3 {
      margin: 0 0 16px 0;
      font-size: 15px;
      font-weight: 600;
      color: #e2e8f0;
    }
    .__xi-modal input {
      width: 100%;
      padding: 10px 12px;
      margin-bottom: 10px;
      border: 1px solid #475569;
      border-radius: 6px;
      background: #0f172a;
      color: #f1f5f9;
      font-size: 14px;
      box-sizing: border-box;
      transition: border-color 0.15s;
    }
    .__xi-modal input:focus {
      outline: none;
      border-color: #5c9aff;
      box-shadow: 0 0 0 3px rgba(92, 154, 255, 0.15);
    }
    .__xi-modal input::placeholder {
      color: #64748b;
    }
    .__xi-modal input::selection {
      background: #3d5a80;
      color: #f1f5f9;
    }
    .__xi-modal .hint {
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 16px;
      line-height: 1.4;
    }
    .__xi-modal .buttons {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
    }
    .__xi-modal button {
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      border: none;
      transition: background 0.15s;
    }
    .__xi-modal .save {
      background: #5c9aff;
      color: white;
    }
    .__xi-modal .save:hover {
      background: #4a8af0;
    }
    .__xi-modal .cancel {
      background: #475569;
      color: #e2e8f0;
    }
    .__xi-modal .cancel:hover {
      background: #526175;
    }
    .__xi-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.6);
      backdrop-filter: blur(2px);
      z-index: 2147483646;
    }
  `;
  document.head.appendChild(style);

  // Generate selector for element
  function getSelector(el) {
    if (!el || el === document.body) return 'body';
    if (el.id && !el.id.startsWith('__xi')) return '#' + CSS.escape(el.id);

    const parent = el.parentElement;
    if (!parent) return el.tagName.toLowerCase();

    const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
    const tag = el.tagName.toLowerCase();
    if (siblings.length === 1) return getSelector(parent) + ' > ' + tag;

    const idx = siblings.indexOf(el) + 1;
    return getSelector(parent) + ' > ' + tag + ':nth-of-type(' + idx + ')';
  }

  // Highlight all x-inspect elements
  function highlightAll() {
    document.querySelectorAll('.__xi-highlight, .__xi-label').forEach(el => el.remove());

    document.querySelectorAll('[x-inspect]').forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return;

      const box = document.createElement('div');
      box.className = '__xi-highlight';
      box.style.cssText = `top:${rect.top + scrollY}px;left:${rect.left + scrollX}px;width:${rect.width}px;height:${rect.height}px`;

      const label = document.createElement('div');
      label.className = '__xi-label';
      label.textContent = el.getAttribute('x-inspect');
      label.style.cssText = `top:${rect.top + scrollY - 16}px;left:${rect.left + scrollX}px`;

      document.body.appendChild(box);
      document.body.appendChild(label);
    });
  }

  // Show hover highlight
  function showHover(el) {
    if (!hoverEl) {
      hoverEl = document.createElement('div');
      hoverEl.className = '__xi-hover';
      document.body.appendChild(hoverEl);
    }
    const rect = el.getBoundingClientRect();
    hoverEl.style.cssText = `top:${rect.top}px;left:${rect.left}px;width:${rect.width}px;height:${rect.height}px`;
  }

  function hideHover() {
    if (hoverEl) { hoverEl.remove(); hoverEl = null; }
  }

  // Show annotation input modal
  function showModal(el, selector) {
    const tag = el.tagName.toLowerCase();
    const defaultId = tag + '-' + counter;

    const overlay = document.createElement('div');
    overlay.className = '__xi-overlay';

    const modal = document.createElement('div');
    modal.className = '__xi-modal';
    modal.innerHTML = `
      <h3>Add Annotation</h3>
      <input type="text" id="__xi-id" placeholder="ID (e.g., btn-submit)" value="${defaultId}">
      <input type="text" id="__xi-text" placeholder="Label (optional)">
      <div class="hint">Element: &lt;${tag}&gt; ${el.textContent?.slice(0,30) || ''}</div>
      <div class="buttons">
        <button class="cancel">Cancel</button>
        <button class="save">Save (Enter)</button>
      </div>
    `;

    document.body.appendChild(overlay);
    document.body.appendChild(modal);

    const idInput = modal.querySelector('#__xi-id');
    const textInput = modal.querySelector('#__xi-text');
    idInput.focus();
    idInput.select();

    function save() {
      const id = idInput.value.trim() || defaultId;
      const text = textInput.value.trim();
      const value = text ? `${id}:${text}` : id;

      el.setAttribute('x-inspect', value);
      counter++;
      cleanup();
      highlightAll();
    }

    function cleanup() {
      overlay.remove();
      modal.remove();
    }

    modal.querySelector('.save').onclick = save;
    modal.querySelector('.cancel').onclick = cleanup;
    overlay.onclick = cleanup;

    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); save(); }
      if (e.key === 'Escape') { e.preventDefault(); cleanup(); }
    });
  }

  // Event handlers
  function onMouseMove(e) {
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (el && !el.className?.includes?.('__xi-')) showHover(el);
  }

  function onClick(e) {
    e.preventDefault();
    e.stopPropagation();

    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || el.className?.includes?.('__xi-')) return;

    const selector = getSelector(el);

    // Exit select mode and show modal
    toggleSelectMode();
    showModal(el, selector);
  }

  function toggleSelectMode() {
    selectMode = !selectMode;
    if (selectMode) {
      document.addEventListener('mousemove', onMouseMove, true);
      document.addEventListener('click', onClick, true);
      document.body.style.cursor = 'crosshair';
    } else {
      document.removeEventListener('mousemove', onMouseMove, true);
      document.removeEventListener('click', onClick, true);
      document.body.style.cursor = '';
      hideHover();
    }
  }

  // Ctrl+I / Cmd+I to toggle
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'i') {
      e.preventDefault();
      toggleSelectMode();
    }
  }, true);

  // Update highlights on scroll/resize
  window.addEventListener('scroll', highlightAll, { passive: true });
  window.addEventListener('resize', highlightAll, { passive: true });

  // Initial highlight
  highlightAll();

  // Get computed styles for element (key styles only)
  function getKeyStyles(el) {
    const computed = window.getComputedStyle(el);
    return {
      display: computed.display,
      position: computed.position,
      visibility: computed.visibility,
      opacity: computed.opacity,
      color: computed.color,
      backgroundColor: computed.backgroundColor,
      fontSize: computed.fontSize,
      fontWeight: computed.fontWeight,
      width: computed.width,
      height: computed.height,
      margin: computed.margin,
      padding: computed.padding,
      border: computed.border,
      zIndex: computed.zIndex,
      overflow: computed.overflow,
    };
  }

  // Get box model for element
  function getBoxModel(el) {
    const rect = el.getBoundingClientRect();
    const computed = window.getComputedStyle(el);
    return {
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      left: rect.left,
      margin: {
        top: parseFloat(computed.marginTop),
        right: parseFloat(computed.marginRight),
        bottom: parseFloat(computed.marginBottom),
        left: parseFloat(computed.marginLeft),
      },
      padding: {
        top: parseFloat(computed.paddingTop),
        right: parseFloat(computed.paddingRight),
        bottom: parseFloat(computed.paddingBottom),
        left: parseFloat(computed.paddingLeft),
      },
      border: {
        top: parseFloat(computed.borderTopWidth),
        right: parseFloat(computed.borderRightWidth),
        bottom: parseFloat(computed.borderBottomWidth),
        left: parseFloat(computed.borderLeftWidth),
      },
    };
  }

  // Get all attributes of element
  function getAttributes(el) {
    const attrs = {};
    for (const attr of el.attributes) {
      if (!attr.name.startsWith('x-inspect')) {
        attrs[attr.name] = attr.value;
      }
    }
    return attrs;
  }

  // Get comprehensive element details
  function getElementDetails(el) {
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return {
      tagName: el.tagName.toLowerCase(),
      elementId: el.id || null,
      className: el.className || null,
      selector: getSelector(el),
      isVisible: rect.width > 0 && rect.height > 0,
      boxModel: getBoxModel(el),
      childCount: el.children.length,
      parentTag: el.parentElement?.tagName.toLowerCase() || null,
    };
  }

  // API for CLI
  window.__inspector = {
    isReady: () => true,

    // Get all annotations from DOM (basic)
    scanAnnotations: () => {
      const annotations = [];
      document.querySelectorAll('[x-inspect]').forEach(el => {
        const value = el.getAttribute('x-inspect');
        const [id, ...textParts] = value.split(':');
        annotations.push({
          id: id,
          label: textParts.join(':') || '',
          selector: getSelector(el),
          content: el.textContent || '',
          tagName: el.tagName.toLowerCase()
        });
      });
      return annotations;
    },

    // Get all annotations with full details (for capture)
    getAnnotationDetails: () => {
      const annotations = [];
      document.querySelectorAll('[x-inspect]').forEach(el => {
        const value = el.getAttribute('x-inspect');
        const [id, ...textParts] = value.split(':');
        annotations.push({
          id: id,
          label: textParts.join(':') || '',
          outerHTML: el.outerHTML || '',
          ...getElementDetails(el),
        });
      });
      return annotations;
    },

    // Get page info
    getPageInfo: () => ({
      url: window.location.href,
      title: document.title,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        scrollX: window.scrollX,
        scrollY: window.scrollY,
        documentWidth: document.documentElement.scrollWidth,
        documentHeight: document.documentElement.scrollHeight,
      },
      meta: {
        description: document.querySelector('meta[name="description"]')?.content || null,
        charset: document.characterSet,
        lang: document.documentElement.lang || null,
      },
    }),

    // Get full page HTML
    getPageHTML: () => document.documentElement.outerHTML,

    // Get all images
    getImages: () => {
      return Array.from(document.querySelectorAll('img')).slice(0, 50).map(img => ({
        src: img.src,
        alt: img.alt || null,
        width: img.naturalWidth,
        height: img.naturalHeight,
        loading: img.loading,
      }));
    },

    // Get element by selector with full details
    getElementBySelector: (selector) => {
      const el = document.querySelector(selector);
      return el ? getElementDetails(el) : null;
    },

    // Add annotation by selector (supports multiple elements via querySelectorAll)
    addAnnotation: (selector, id, label) => {
      const elements = document.querySelectorAll(selector);
      if (elements.length === 0) return { success: false, error: 'No elements found', count: 0 };

      const added = [];
      elements.forEach((el, index) => {
        // Auto-number IDs when multiple elements: prefix-1, prefix-2, etc.
        const elementId = elements.length > 1 ? `${id}-${index + 1}` : id;
        const value = label ? `${elementId}:${label}` : elementId;
        el.setAttribute('x-inspect', value);
        added.push(elementId);
      });

      highlightAll();
      return { success: true, count: elements.length, ids: added };
    },

    // Remove annotation by selector
    removeAnnotation: (selector) => {
      const el = document.querySelector(selector);
      if (el) el.removeAttribute('x-inspect');
      highlightAll();
      return { success: true };
    },

    // Remove annotation by id
    removeById: (id) => {
      document.querySelectorAll('[x-inspect]').forEach(el => {
        const value = el.getAttribute('x-inspect');
        if (value.startsWith(id + ':') || value === id) {
          el.removeAttribute('x-inspect');
        }
      });
      highlightAll();
      return { success: true };
    },

    highlightAll
  };
})();

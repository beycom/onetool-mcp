// Ops script — re-injected on every tool call via _ensure_ready().
() => {
  // Internal drawing helper — not exposed as tools.
  // Called from Python via browser_evaluate after bootstrap.js has run.


  window._batch_draw = (shapes, edges, frames) => {
    const now = Date.now();
    const rng = () => Math.floor(Math.random() * 9999999);

    // One live read for positions of elements the user may have moved
    const liveMap = {};
    for (const el of window.__drawApi.read()) {
      liveMap[el.id] = el;
    }

    // Phase 1: shapes
    for (const s of shapes) {
      const { id, label, x, y, w, h, shape, styleProps } = s;
      // Prefer the live position when the element already exists on canvas
      // (moved by the user or by layout()) so redraws don't snap it back.
      const live = liveMap[id];
      const useLive = live && !live.isDeleted
        && typeof live.x === 'number' && typeof live.y === 'number';
      const px = useLive ? live.x : x;
      const py = useLive ? live.y : y;
      const textId   = id + '-text';
      const fontSize = styleProps.fontSize || 16;
      const lineCount = label.split('\n').length;
      const textH    = lineCount * fontSize * 1.25;

      const shapeRoundness = styleProps.corners === 'sharp' ? null
                           : 'roundness' in styleProps ? styleProps.roundness
                           : { type: 3 };
      window.__drawElements[id] = {
        id, type: shape, x: px, y: py, width: w, height: h,
        strokeColor:     styleProps.strokeColor     || '#1e1e1e',
        backgroundColor: styleProps.backgroundColor || '#ffffff',
        strokeWidth:     styleProps.strokeWidth     || 2,
        strokeStyle:     styleProps.strokeStyle     || 'solid',
        roughness:       styleProps.roughness       ?? 1,
        opacity:         styleProps.opacity         ?? 100,
        roundness:       shapeRoundness,
        fillStyle:       styleProps.fillStyle       || 'solid',
        angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [{ type: 'text', id: textId }],
      };
      window.__drawElements[textId] = {
        id: textId, type: 'text',
        x: px + 8, y: py + (h - textH) / 2, width: w - 16, height: textH,
        text: label,
        fontSize,
        fontFamily:    styleProps.fontFamily    || 1,
        textAlign:     styleProps.textAlign     || 'center',
        verticalAlign: styleProps.verticalAlign || 'middle',
        strokeColor:   styleProps.color         || '#1e1e1e',
        backgroundColor: 'transparent',
        fillStyle: 'solid', strokeWidth: 1, roughness: 1,
        opacity: 100, angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [], containerId: id, lineHeight: 1.25, baseline: 18,
        originalText: label, autoResize: true,
      };
    }

    // Phase 2: edges
    const gap = 8;
    // Pre-compute parallel edge groups for y-offset separation
    const pairCount = {};
    const pairIndex = {};
    for (const e of edges) {
      const key = e.srcId + '|' + e.dstId;
      pairCount[key] = (pairCount[key] || 0) + 1;
    }
    const pairSeen = {};
    for (const e of edges) {
      const key = e.srcId + '|' + e.dstId;
      pairIndex[e.id] = pairSeen[key] || 0;
      pairSeen[key] = (pairSeen[key] || 0) + 1;
    }
    const parallelSpacing = 20;
    for (const e of edges) {
      const { id, srcId, dstId, label, startArrowhead, endArrowhead, strokeStyle } = e;
      const sp = e.styleProps || {};
      // Prefer live position (user-moved), fall back to freshly placed
      const src = liveMap[srcId] || window.__drawElements[srcId];
      const dst = liveMap[dstId] || window.__drawElements[dstId];
      if (!src || !dst) continue;

      const pairKey = srcId + '|' + dstId;
      const n = pairCount[pairKey] || 1;
      const idx = pairIndex[id] || 0;
      const yOff = n > 1 ? (idx - (n - 1) / 2) * parallelSpacing : 0;

      const sx = src.x + src.width  + gap,  sy = src.y + src.height / 2 + yOff;
      const ex = dst.x              - gap,  ey = dst.y + dst.height  / 2 + yOff;

      let arrowX, arrowY, pts, bboxW, bboxH, roughness;
      if (sp.arrowType === 'elbow') {
        // Elbow arrows use a straight 2-point seed path. Excalidraw re-routes
        // the connector orthogonally via elbowed:true + startBinding/endBinding.
        arrowX = sx; arrowY = sy;
        pts = [[0, 0], [ex - sx, ey - sy]];
        bboxW = ex - sx; bboxH = ey - sy;
        roughness = 0;
      } else {
        arrowX = sx; arrowY = sy;
        pts = [[0, 0], [ex - sx, ey - sy]];
        bboxW = ex - sx; bboxH = ey - sy;
        roughness = 1;
      }

      // Back-fill boundElements on src and dst in cache
      const srcEl = window.__drawElements[srcId] || src;
      const dstEl = window.__drawElements[dstId] || dst;
      window.__drawElements[srcId] = { ...srcEl,
        boundElements: [...(srcEl.boundElements||[]), { type: 'arrow', id }] };
      window.__drawElements[dstId] = { ...dstEl,
        boundElements: [...(dstEl.boundElements||[]), { type: 'arrow', id }] };

      const labelId = id + '-label';
      const boundEls = label ? [{ type: 'text', id: labelId }] : [];
      const at = sp.arrowType;
      const edgeRoundness = (at === 'sharp' || at === 'elbow') ? null : { type: 2 };
      const elbowed = at === 'elbow' ? true : undefined;
      window.__drawElements[id] = {
        id, type: 'arrow',
        x: arrowX, y: arrowY, width: bboxW, height: bboxH,
        points: pts,
        strokeColor:  sp.strokeColor  || '#1e1e1e',
        backgroundColor: 'transparent',
        fillStyle:    sp.fillStyle    || 'solid',
        strokeWidth:  sp.strokeWidth  ?? 2,
        roughness,
        strokeStyle:  sp.strokeStyle  || strokeStyle || 'solid',
        opacity:      sp.opacity      ?? 100,
        angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: boundEls, roundness: edgeRoundness,
        ...(elbowed !== undefined ? { elbowed } : {}),
        startArrowhead: startArrowhead !== undefined ? startArrowhead : null,
        endArrowhead:   endArrowhead   !== undefined ? endArrowhead   : 'arrow',
        startBinding: { elementId: srcId, focus: 0, gap },
        endBinding:   { elementId: dstId, focus: 0, gap },
      };
      if (label) {
        const mx = sx + (ex - sx) / 2;
        const my = sy + (ey - sy) / 2;
        const fontSize = 14;
        window.__drawElements[labelId] = {
          id: labelId, type: 'text',
          x: mx - 60, y: my - fontSize,
          width: 120, height: fontSize * 1.25,
          text: label, fontSize,
          fontFamily: 1, textAlign: 'center', verticalAlign: 'middle',
          strokeColor: '#1e1e1e', backgroundColor: 'transparent',
          fillStyle: 'solid', strokeWidth: 1, roughness: 1,
          opacity: 100, angle: 0, groupIds: [], frameId: null,
          isDeleted: false, link: null, locked: false,
          version: 1, versionNonce: rng(), updated: now,
          boundElements: [], containerId: id, lineHeight: 1.25, baseline: 18,
          originalText: label, autoResize: true,
        };
      }
    }

    // Phase 3: subgraphs — rendered as a bounding rectangle with bound label,
    // pushed to the back so member shapes render in front.
    const pad = 40;
    const labelFontSize = 13;
    const labelHeight = labelFontSize * 1.25;
    const labelPad = labelHeight + 12; // space reserved at top for the label
    for (const f of frames) {
      const { id, label, memberIds, savedBounds } = f;
      // Erase previous rect + label if they exist (redraw always)
      delete window.__drawElements[id];
      delete window.__drawElements[id + '-label'];

      let x, y, w, h;
      if (savedBounds) {
        ({ x, y, w, h } = savedBounds);
      } else {
        // Compute bounds from freshly placed elements (or live for existing ones)
        const members = memberIds.map(mid =>
          window.__drawElements[mid] || liveMap[mid]
        ).filter(Boolean);
        if (!members.length) continue;
        const minX = Math.min(...members.map(e => e.x));
        const minY = Math.min(...members.map(e => e.y));
        const maxX = Math.max(...members.map(e => e.x + (e.width  || 160)));
        const maxY = Math.max(...members.map(e => e.y + (e.height || 60)));
        x = minX - pad;
        y = minY - labelPad - pad;
        w = (maxX - minX) + pad * 2;
        h = (maxY - minY) + labelPad + pad * 2;
      }

      const labelId = id + '-label';
      const groupRect = {
        id, type: 'rectangle',
        x, y, width: w, height: h,
        strokeColor: '#868e96',
        backgroundColor: 'transparent',
        strokeWidth: 1, strokeStyle: 'dashed', roughness: 0, opacity: 80,
        fillStyle: 'solid', angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [{ type: 'text', id: labelId }], roundness: null,
      };
      const labelEl = {
        id: labelId, type: 'text',
        x: x + 8, y: y + 8, width: w - 16, height: labelHeight,
        text: label, fontSize: labelFontSize,
        fontFamily: 1, textAlign: 'center', verticalAlign: 'top',
        containerId: id,
        strokeColor: '#868e96', backgroundColor: 'transparent',
        fillStyle: 'solid', strokeWidth: 1, roughness: 0,
        opacity: 80, angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [], lineHeight: 1.25, baseline: 13,
        originalText: label, autoResize: true,
      };

      for (const mid of memberIds) {
        const el = window.__drawElements[mid] || liveMap[mid];
        if (el) {
          const gids = el.groupIds || [];
          window.__drawElements[mid] = {
            ...el,
            groupIds: gids.includes(id) ? gids : [...gids, id],
          };
        }
        const tid = mid + '-text';
        const tel = window.__drawElements[tid] || liveMap[tid];
        if (tel) {
          const tgids = tel.groupIds || [];
          window.__drawElements[tid] = {
            ...tel,
            groupIds: tgids.includes(id) ? tgids : [...tgids, id],
          };
        }
      }

      // Insert rect + label at BEGINNING so they render behind all other elements
      window.__drawElements = { [id]: groupRect, [labelId]: labelEl, ...window.__drawElements };
    }

    // Single updateScene for all phases
    window.__drawApi._raw.updateScene({ elements: Object.values(window.__drawElements) });
    return true;
  };

  window._batch_erase = (ids) => {
    for (const id of ids) {
      delete window.__drawElements[id];
      delete window.__drawElements[id + '-text'];
      delete window.__drawElements[id + '-label'];
    }
    window.__drawApi._raw.updateScene({ elements: Object.values(window.__drawElements) });
    return true;
  };

  // ---------------------------------------------------------------------------
  // Patch existing elements (upsert — label and/or style only, position preserved)
  // Used by whiteboard.draw for existing nodes and whiteboard.style.
  // patches: [{id, text?, strokeColor?, backgroundColor?, ...excalidraw props}]
  // ---------------------------------------------------------------------------
  window._patch_elements = (patches) => {
    const now = Date.now();
    const rng = () => Math.floor(Math.random() * 9999999);
    let matched = 0;

    const liveMap = {};
    for (const el of window.__drawApi.read()) {
      liveMap[el.id] = el;
    }

    for (const patch of patches) {
      const { id, text, shape: newType, corners: cornersVal, ...styleProps } = patch;

      const existing = liveMap[id] || window.__drawElements[id];
      if (!existing) continue;
      matched++;

      const textId = id + '-text';
      const existingText = liveMap[textId] || window.__drawElements[textId];

      // Translate corners shorthand to Excalidraw's roundness property
      if (cornersVal !== undefined) {
        styleProps.roundness = cornersVal === 'sharp' ? null : { type: 3 };
      }

      // Shape type change requires delete + recreate (Excalidraw cannot change type in-place)
      if (newType && newType !== existing.type) {
        const boundEls = existing.boundElements || [];
        window.__drawElements[id] = {
          ...existing,
          type: newType,
          ...styleProps,
          boundElements: boundEls,
          version: (existing.version || 1) + 1,
          versionNonce: rng(),
          updated: now,
        };
      } else {
        window.__drawElements[id] = {
          ...existing,
          ...styleProps,
          version: (existing.version || 1) + 1,
          versionNonce: rng(),
          updated: now,
        };
      }

      // Update text child
      if (existingText) {
        const newLabel = text !== undefined ? text : existingText.text;
        const fontSize = styleProps.fontSize || existingText.fontSize || 16;
        const lineCount = newLabel.split('\n').length;
        const textH = lineCount * fontSize * 1.25;
        // When x/y move the parent, translate the text child by the same delta
        const dx = styleProps.x !== undefined ? styleProps.x - existing.x : 0;
        const dy = styleProps.y !== undefined ? styleProps.y - existing.y : 0;
        window.__drawElements[textId] = {
          ...existingText,
          text: newLabel,
          originalText: newLabel,
          fontSize,
          height: textH,
          ...(dx || dy ? { x: existingText.x + dx, y: existingText.y + dy } : {}),
          // Sync text stroke colour if sc was provided
          ...(styleProps.strokeColor ? { strokeColor: styleProps.strokeColor } : {}),
          ...(styleProps.fontFamily  ? { fontFamily: styleProps.fontFamily }   : {}),
          ...(styleProps.textAlign   ? { textAlign: styleProps.textAlign }     : {}),
          version: (existingText.version || 1) + 1,
          versionNonce: rng(),
          updated: now,
        };
      }
    }

    window.__drawApi._raw.updateScene({ elements: Object.values(window.__drawElements) });
    return matched;
  };

  // ---------------------------------------------------------------------------
  // Style elements by ID — applies Excalidraw props directly.
  // ids: string[], styleProps: {backgroundColor?, strokeColor?, strokeWidth?, ...}
  // ---------------------------------------------------------------------------
  window._style_elements = (ids, styleProps) => {
    const patches = ids.map(id => ({ id, ...styleProps }));
    return window._patch_elements(patches);
  };

  // ---------------------------------------------------------------------------
  // Upsert the __otDSL text element (fixed ID) with the current DSL string.
  // Positioned at (20, 20) on first write; preserves position on updates.
  // ---------------------------------------------------------------------------
  window._upsert_dsl_element = (dslText) => {
    const now = Date.now();
    const rng = () => Math.floor(Math.random() * 9999999);
    const id = '__otDSL';

    const allEls = window.__drawApi.read();
    const existing = allEls.find(e => e.id === id) || window.__drawElements[id];

    const lines = dslText.split('\n');
    const fontSize = 12;
    const lineH = fontSize * 1.4;
    const charW = 7;
    const pad = 12;
    const w = Math.max(120, Math.max(...lines.map(l => l.length)) * charW + pad * 2);
    const h = lines.length * lineH + pad * 2;

    const x = existing ? existing.x : 20;
    const y = existing ? existing.y : 20;

    window.__drawElements[id] = {
      id, type: 'text',
      x, y, width: w, height: h,
      text: dslText,
      fontSize,
      fontFamily: 3,
      textAlign: 'left', verticalAlign: 'top',
      strokeColor: '#888888', backgroundColor: 'transparent',
      fillStyle: 'solid', strokeWidth: 1, roughness: 0,
      opacity: 50, angle: 0, groupIds: [], frameId: null,
      isDeleted: false, link: null, locked: false,
      version: existing ? (existing.version || 1) + 1 : 1,
      versionNonce: rng(), updated: now,
      boundElements: [], containerId: null, lineHeight: 1.4, baseline: 10,
      originalText: dslText, autoResize: true,
    };

    window.__drawApi._raw.updateScene({ elements: Object.values(window.__drawElements) });
    return true;
  };

  // ---------------------------------------------------------------------------
  // Read scene — structured text summary of all canvas elements.
  // Returns a compact text report for agent inspection (no screenshots needed).
  // ---------------------------------------------------------------------------
  window._read_scene = (level) => {
    // level: "min" | "default" | "full" | "debug"
    const isDebug = level === 'debug';
    const detailLevel = isDebug ? 'full' : level;
    // debug: show everything including deleted and __otDSL; normal: filter them out
    const allEls = window.__drawApi.read();
    const els = isDebug ? allEls : allEls.filter(e => !e.isDeleted && e.id !== '__otDSL');

    // Build lookup: containerId → text element
    const textChildren = {};
    for (const e of els) {
      if (e.type === 'text' && e.containerId) {
        textChildren[e.containerId] = e;
      }
    }

    const shapes = [];
    const edges = [];
    const textEls = [];

    for (const e of els) {
      if (e.type === 'arrow') {
        const src = e.startBinding ? e.startBinding.elementId : '?';
        const dst = e.endBinding ? e.endBinding.elementId : '?';
        const labelEl = textChildren[e.id];
        const label = labelEl ? labelEl.text : '';
        const startAH = e.startArrowhead ?? 'none';
        const endAH = e.endArrowhead ?? 'none';
        const ss = e.strokeStyle || 'solid';
        let line = '  ' + e.id.padEnd(24) + src + ' -> ' + dst;
        if (label) line += '  "' + label + '"';
        line += '  [' + startAH + '/' + endAH + ' ' + ss + ']';
        if (detailLevel === 'full') {
          line += '  sc:' + (e.strokeColor || '#1e1e1e');
          line += ' sw:' + (e.strokeWidth ?? 2);
          line += ' o:' + (e.opacity ?? 100);
          const r = e.roundness;
          const at = e.elbowed ? 'elbow' : (r === null ? 'sharp' : 'curve');
          line += ' at:' + at;
          line += ' x:' + Math.round(e.x) + ',y:' + Math.round(e.y);
          line += ' w:' + Math.round(e.width) + ',h:' + Math.round(e.height);
        }
        if (isDebug) {
          line += ' deleted:' + (!!e.isDeleted);
          const pts = e.points || [];
          line += ' points:[' + pts.map(p => '[' + p.join(',') + ']').join(',') + ']';
        }
        edges.push(line);
      } else if (e.type === 'text' && e.containerId) {
        // Bound text — handled inline with parent; only show standalone in debug
        if (isDebug) {
          let line = '  ' + e.id.padEnd(24) + 'text'.padEnd(12);
          line += '"' + (e.text || '').split('\n')[0].slice(0, 40) + '"';
          line += '  containerId:' + e.containerId;
          line += ' deleted:' + (!!e.isDeleted);
          textEls.push(line);
        }
      } else if (e.type === 'text' && !e.containerId) {
        // Standalone text (e.g. __otDSL)
        if (isDebug) {
          let line = '  ' + e.id.padEnd(24) + 'text'.padEnd(12);
          const preview = (e.text || '').split('\n')[0].slice(0, 40);
          line += '"' + preview + '"';
          line += '  deleted:' + (!!e.isDeleted);
          line += ' o:' + (e.opacity ?? 100);
          line += ' x:' + Math.round(e.x) + ',y:' + Math.round(e.y);
          textEls.push(line);
        }
      } else if (e.type !== 'text') {
        // Shape (rectangle, diamond, ellipse, etc.)
        const textEl = textChildren[e.id];
        const label = textEl ? textEl.text.split('\n')[0] : '';
        const truncLabel = label.length > 40 ? label.slice(0, 37) + '...' : label;
        const typeName = e.type === 'ellipse' ? 'circle' : e.type;
        const bc = e.backgroundColor ?? 'transparent';
        const sc = e.strokeColor ?? '#1e1e1e';
        const gids = (e.groupIds || []).filter(g => g);

        let line = '  ' + e.id.padEnd(24) + typeName.padEnd(12);
        if (truncLabel) line += '"' + truncLabel + '"';
        line += '  bc:' + bc + ' sc:' + sc;
        if (textEl) line += ' text-sc:' + (textEl.strokeColor || '#1e1e1e');
        if (gids.length) line += ' groups:[' + gids.join(',') + ']';

        if (detailLevel === 'full') {
          line += ' sw:' + (e.strokeWidth ?? 2);
          line += ' ss:' + (e.strokeStyle || 'solid');
          line += ' r:' + (e.roughness ?? 1);
          line += ' o:' + (e.opacity ?? 100);
          const fi = e.fillStyle || 'solid';
          if (fi !== 'solid') line += ' fi:' + fi;
          const cr = e.roundness === null ? 'sharp' : 'round';
          line += ' cr:' + cr;
          line += ' x:' + Math.round(e.x) + ',y:' + Math.round(e.y);
          line += ' w:' + Math.round(e.width) + ',h:' + Math.round(e.height);
          if (textEl) {
            const ff = {1: 'hand', 2: 'normal', 3: 'mono'}[textEl.fontFamily] || textEl.fontFamily;
            line += ' f:' + ff + ' fs:' + (textEl.fontSize || 16);
            line += ' ta:' + (textEl.textAlign || 'center');
            line += ' va:' + (textEl.verticalAlign || 'middle');
          }
        }
        if (isDebug) {
          line += ' deleted:' + (!!e.isDeleted);
        }

        // Warn if text strokeColor matches backgroundColor (invisible label)
        if (textEl && bc !== 'transparent' && textEl.strokeColor === bc) {
          line += ' ⚠ TEXT=BG';
        }

        shapes.push(line);
      }
    }

    const header = 'Scene: ' + shapes.length + ' shapes, ' + edges.length + ' edges';
    if (level === 'min') return header;

    const parts = [header, ''];
    if (shapes.length) {
      parts.push('Shapes:');
      for (const s of shapes) parts.push(s);
      parts.push('');
    }
    if (edges.length) {
      parts.push('Edges:');
      for (const e of edges) parts.push(e);
      parts.push('');
    }
    if (isDebug && textEls.length) {
      parts.push('Text elements:');
      for (const t of textEls) parts.push(t);
      parts.push('');
    }

    return parts.join('\n');
  };


  return true;
}

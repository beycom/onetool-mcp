# Vision Comparison

Compare `img.ask` (ot_image tool) vs Harness-native direct image attachment for answering
questions about an image.

---

## Step 0 — Select Image

Glob `tests/data/products-*.*` and list the files found. Ask the user to pick one.

If running unattended, default to `tests/data/products-full.png` and continue.

---

## Measurement Pattern

**IMPORTANT: Every numbered step MUST be run inside its own subagent (Agent tool call).** This
ensures each step executes in a separate turn, flushing to JSONL before the next measurement is
taken. Never call `tmr.start`, `img.ask`, or `tmr.elapsed` directly in the main conversation —
always delegate to a subagent.

Steps 1 and 2 within each approach may be launched as parallel subagents. Step 3 must wait for
steps 1–2 to complete. Steps 4 and 5 must wait for step 3 to complete, and may be parallel.

**Note:** `img.ask` executes via its own API client in a separate session.

**Approach A — `img.ask`:**
```
1. [subagent] tmr.start(name="A")
   --- wait for 1 ---
3. [subagent] img.ask(img="<image_path>", q=["<grid question — see below>"])
   --- wait for 3 ---
4. [subagent] tmr.elapsed(name="A")
```

**Approach B — Direct attachment:**
```
1. [subagent] tmr.start(name="B")
   --- wait for 1 ---
3. [subagent] Read(file_path="<image_path>")
              Then answer the grid question below from the rendered image.
   --- wait for 3 ---
4. [subagent] tmr.elapsed(name="B")
```

Step 3 for Approach B requires a subagent that reads the image file and answers the question in
the same turn. Steps 4 and 5 must come **after** that subagent completes.

Run Approach A first (steps 1–4), then Approach B (steps 1–4).

---

## Question

The products are arranged in a **4-column grid**. Use this exact question for both approaches:

> **Return the prices as a table with exactly 4 columns, one row per row of products, in the
> exact order they appear in the image left-to-right, top-to-bottom.
> Format each row as: price1 | price2 | price3 | price4**

---

## Quality Comparison

After both approaches complete, display results side-by-side as two grids and one accuracy table.

### Grid A — img.ask

| Col 1 | Col 2 | Col 3 | Col 4 |
| ---: | ---: | ---: | ---: |
| (fill in) | | | |

### Grid B — Direct

| Col 1 | Col 2 | Col 3 | Col 4 |
| ---: | ---: | ---: | ---: |
| (fill in) | | | |

### Cell-by-cell Accuracy

Compare each cell position. Mark each cell ✓ (match), ~ (close, ≤5% difference), or ✗ (wrong/missing).
Use img.ask as the reference since it is the more accurate approach.

| Row | Col 1 | Col 2 | Col 3 | Col 4 |
| :--- | :---: | :---: | :---: | :---: |
| 1 | | | | |
| ... | | | | |

Summary line: `X / Y cells correct (Z%)` — where Y = total cells in the img.ask grid.

---

## Measurements

| Metric | img.ask | Direct |
| :--- | ---: | ---: |
| Time (s) | | |

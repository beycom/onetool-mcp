# Bentobox Features Layout - Implementation Guide

This document explains how to implement the bentobox grid layout for `docs/features.md` using MkDocs Material.

**Demo:** Open [bento-demo.html](bento-demo.html) in a browser to preview the design.

---

## Prerequisites

The following MkDocs Material extensions are required (already enabled in `mkdocs.yml`):

```yaml
markdown_extensions:
  - attr_list      # Add CSS classes to elements
  - md_in_html     # Use markdown inside HTML blocks
  - pymdownx.emoji # Material Design icons
```

---

## Step 1: Add CSS to extra.css

Add the following to `docs/stylesheets/extra.css`:

```css
/* ============================================
   BENTOBOX GRID SYSTEM
   ============================================ */

.bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  padding: 2rem 0;
}

/* Card base styling */
.bento-card {
  border-radius: 1.25rem;
  padding: 1.75rem;
  display: flex;
  flex-direction: column;
  min-height: 180px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.bento-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.15);
}

/* Remove link underlines inside bento cards */
.bento-card a {
  text-decoration: none;
}

.bento-card h2, .bento-card h3 {
  margin-top: 0;
  margin-bottom: 0.75rem;
}

.bento-card p {
  margin: 0.5rem 0;
  line-height: 1.5;
}

/* Size variants */
.bento-card.span-2 { grid-column: span 2; }
.bento-card.span-3 { grid-column: span 3; }
.bento-card.span-4 { grid-column: span 4; }
.bento-card.tall { grid-row: span 2; }

/* Color palette - Brand aligned */
.bento-card.primary {
  background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
  color: #fff;
}
.bento-card.accent {
  background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
  color: #fff;
}
.bento-card.green {
  background: #10B981;
  color: #fff;
}
.bento-card.mint {
  background: #D1FAE5;
  color: #065F46;
}
.bento-card.sky {
  background: #E0F2FE;
  color: #0369A1;
}
.bento-card.rose {
  background: #FCE7F3;
  color: #9D174D;
}
.bento-card.amber {
  background: #FEF3C7;
  color: #92400E;
}
.bento-card.slate {
  background: #1E293B;
  color: #F1F5F9;
}

/* Icon styling */
.bento-card .bento-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
  opacity: 0.9;
}

/* Image handling */
.bento-card img {
  max-width: 100%;
  border-radius: 0.75rem;
  margin-top: auto;
}

.bento-card.img-top img {
  margin-top: 0;
  margin-bottom: 1rem;
}

/* Code blocks in cards */
.bento-card pre {
  margin: 1rem 0 0 0;
  border-radius: 0.5rem;
  font-size: 0.85rem;
}

/* CTA link styling */
.bento-card .cta {
  margin-top: auto;
  padding-top: 1rem;
  font-weight: 600;
  opacity: 0.9;
}

.bento-card .cta:hover {
  opacity: 1;
}

/* Stat callout */
.bento-stat {
  font-size: 3.5rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 0.5rem;
}

/* Responsive breakpoints */
@media (max-width: 1200px) {
  .bento-grid { grid-template-columns: repeat(3, 1fr); }
  .bento-card.span-3 { grid-column: span 3; }
  .bento-card.span-4 { grid-column: span 3; }
}

@media (max-width: 900px) {
  .bento-grid { grid-template-columns: repeat(2, 1fr); }
  .bento-card.span-2, .bento-card.span-3, .bento-card.span-4 { grid-column: span 2; }
}

@media (max-width: 600px) {
  .bento-grid { grid-template-columns: 1fr; }
  .bento-card.span-2, .bento-card.span-3, .bento-card.span-4 { grid-column: span 1; }
  .bento-card.tall { grid-row: span 1; }
}
```

---

## Step 2: Markdown Syntax

### Basic Card Structure

```markdown
<div class="bento-grid" markdown>

<div class="bento-card green" markdown>

### Card Title

Card content goes here.

</div>

</div>
```

**Important:** The `markdown` attribute on both the grid and card divs enables markdown parsing inside HTML blocks.

### Available Classes

#### Size Classes

| Class | Effect |
|-------|--------|
| `span-2` | Card spans 2 columns |
| `span-3` | Card spans 3 columns |
| `span-4` | Card spans full width (4 columns) |
| `tall` | Card spans 2 rows vertically |

Combine for large hero cards: `span-2 tall`

#### Color Classes

| Class | Background | Text | Use for |
|-------|------------|------|---------|
| `primary` | Blue gradient | White | Key features, CTAs |
| `accent` | Purple gradient | White | Secondary highlights |
| `green` | Solid green | White | Success, metrics, savings |
| `slate` | Dark gray | Light | Technical, code-focused |
| `mint` | Light green | Dark green | Positive, extensibility |
| `sky` | Light blue | Dark blue | Info, developer tools |
| `rose` | Light pink | Dark pink | Warnings, security |
| `amber` | Light yellow | Dark brown | Configuration, settings |

---

## Step 3: Component Patterns

### Hero Card with Stat

```markdown
<div class="bento-card green span-2 tall" markdown>

<span class="bento-stat">96%</span>

## Token Savings

Description text here.

![Chart](assets/features/token-chart.png)

[Learn more →](learn/comparison.md){ .cta }

</div>
```

### Icon Card

```markdown
<div class="bento-card primary" markdown>

:material-code-braces:{ .bento-icon }

### Explicit Execution

Write Python, not tool definitions.

</div>
```

### Card with Code Block

```markdown
<div class="bento-card slate" markdown>

:material-terminal:{ .bento-icon }

### CLI Example

\`\`\`python
__ot brave.search(q="AI")
\`\`\`

</div>
```

### Card with CTA Link

```markdown
<div class="bento-card accent" markdown>

### Feature Name

Description here.

[Learn more →](path/to/docs.md){ .cta }

</div>
```

---

## Step 4: Full Page Structure

```markdown
# What's in OneTool?

Tagline text here.

<!-- Section 1: Hero -->
<div class="bento-grid" markdown>

<div class="bento-card green span-2 tall" markdown>
<!-- Hero content -->
</div>

<div class="bento-card primary" markdown>
<!-- Card 2 -->
</div>

<div class="bento-card slate" markdown>
<!-- Card 3 -->
</div>

<div class="bento-card accent span-2" markdown>
<!-- Card 4 - spans 2 columns -->
</div>

</div>

## Section Title

<div class="bento-grid" markdown>

<!-- More cards... -->

</div>
```

---

## Step 5: Available Icons

Use Material Design Icons with the syntax `:material-icon-name:{ .bento-icon }`

**Recommended icons for OneTool features:**

| Feature | Icon |
|---------|------|
| Code/Execution | `:material-code-braces:` |
| Tools/Packages | `:material-package-variant-closed:` |
| Search | `:material-magnify:` |
| Security | `:material-shield-check:` |
| Config | `:material-file-cog:` |
| Database | `:material-database:` |
| AI/LLM | `:material-brain:` |
| Testing | `:material-test-tube:` |
| Stats | `:material-chart-line:` |
| Extensions | `:material-puzzle:` |
| Speed | `:material-lightning-bolt:` |
| Isolation | `:material-cog-play:` |

Browse all icons: https://pictogrammers.com/library/mdi/

---

## Step 6: Adding Images

1. Create directory: `docs/assets/features/`
2. Add images (recommended sizes):
   - Hero cards: 600x300px
   - Standard cards: 300x200px
   - Icons: 64x64px or use Material icons

3. Reference in markdown:
```markdown
![Alt text](assets/features/image-name.png)
```

---

## Troubleshooting

### Markdown not rendering inside cards

Ensure both the grid and card have the `markdown` attribute:

```markdown
<div class="bento-grid" markdown>  <!-- Required -->
<div class="bento-card green" markdown>  <!-- Required -->
```

### Cards not aligning properly

- Check that the total spans in a row don't exceed 4
- Verify responsive breakpoints match your viewport

### Icons not showing

- Confirm `pymdownx.emoji` extension is enabled
- Use exact icon names from Material Design Icons
- Include the `{ .bento-icon }` class for proper sizing

### Hover effects not working

The CSS requires the `.bento-card` class. Check for typos in class names.

---

## Dark Mode Considerations

The current color palette works in both light and dark modes. The `slate` cards are specifically designed for dark themes. If needed, add dark-mode-specific overrides:

```css
[data-md-color-scheme="slate"] .bento-card.mint {
  /* Adjusted colors for dark mode */
}
```

---

## Preview

Run `mkdocs serve` and navigate to the features page to see the layout in action.

For a static preview without MkDocs, open [bento-demo.html](bento-demo.html) in a browser.

# Documentation Visual Design

Reusable visual design token checklist for documentation sites, with this repository's current token values filled in as the project profile.

## Colors

### Light Theme

| Token | Hex | Usage |
|-------|-----|-------|
| `--brand-primary` | `#087EA4` | Links, active states, logo, accents |
| `--brand-primary-bg` | `#E6F7FF` | Active tab pill, highlights |
| `--brand-text` | `#404756` | Body text, nav items |
| `--brand-text-secondary` | `#6b7280` | Placeholders, muted text |
| Background | `#ffffff` | Page, header |
| Highlight BG | `#F0F1F4` | Code blocks, secondary areas |
| Search BG | `#EBECF0` | Search input |

### Dark Theme

| Token | Hex | Usage |
|-------|-----|-------|
| `--brand-primary` | `#58C4DC` | Links, active states, logo, accents |
| `--brand-primary-bg` | `#283542` | Active tab pill, highlights |
| `--brand-text` | `#f6f7f9` | Body text, nav items |
| `--brand-text-secondary` | `#99a1b3` | Placeholders, muted text |
| Background | `#23272F` | Page, header |
| Search BG | `#343a46` | Search input |

### Status Colors

| Role | Hex |
|------|-----|
| Success | `#22C55E` |
| Warning | `#F59E0B` |
| Error | `#EF4444` |

## Typography

### Font Stack

```css
/* Body text */
--md-text-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                "Helvetica Neue", Arial, "Noto Sans", sans-serif;

/* Code */
--md-code-font: "Source Code Pro", ui-monospace, SFMono-Regular, "SF Mono",
                Menlo, Consolas, "Liberation Mono", monospace;
```

### Sizes

| Element | Size | Weight |
|---------|------|--------|
| Nav tabs | `0.9rem` | 500 |
| Body text | `1rem` | 400 |

## Border Radius

| Element | Radius |
|---------|--------|
| Active tab pill | `2rem` |
| Search box | `2rem` |
| Code blocks | Default |

## Shadows

| State | Shadow |
|-------|--------|
| Header (default) | None |
| Header (scrolled) | `0 0 0.2rem rgba(0,0,0,0.1), 0 0.2rem 0.4rem rgba(0,0,0,0.2)` |

## Logo

Single SVG file with CSS-controlled color via `mask-image`:

| File | Color (Light) | Color (Dark) |
|------|---------------|--------------|
| `docs/assets/logo.svg` | `#087EA4` | `#58C4DC` |

**How it works:**
- SVG used as CSS mask
- `background-color: var(--brand-primary)` fills the shape
- Theme switch automatically changes the color

**SVG requirements:**
- Fill color in file doesn't matter (CSS overrides)
- Use solid shapes (transparency becomes cutout)
- Avoid gradients

## Links

- Content links: Underlined, brand primary color
- Nav/header links: No underline, brand text color
- Hover: Brand primary color

## Active States

Active navigation tabs use a pill style:
- Rounded background (`2rem`)
- Background: `--brand-primary-bg`
- Text: `--brand-primary`

## Icons

- Theme toggle: Material Design icons
- Repository: FontAwesome GitHub icon
- Search: Material magnify icon

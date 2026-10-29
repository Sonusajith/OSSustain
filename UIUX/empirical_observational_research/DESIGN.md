---
name: Empirical Observational Research
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#515f74'
  on-secondary: '#ffffff'
  secondary-container: '#d5e3fd'
  on-secondary-container: '#57657b'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#0d1c2e'
  on-tertiary-container: '#77859a'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#d5e3fd'
  secondary-fixed-dim: '#b9c7e0'
  on-secondary-fixed: '#0d1c2f'
  on-secondary-fixed-variant: '#3a485c'
  tertiary-fixed: '#d5e3fc'
  tertiary-fixed-dim: '#b9c7df'
  on-tertiary-fixed: '#0d1c2e'
  on-tertiary-fixed-variant: '#3a485b'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Newsreader
    fontSize: 36px
    fontWeight: '500'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Newsreader
    fontSize: 28px
    fontWeight: '500'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Newsreader
    fontSize: 28px
    fontWeight: '500'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Newsreader
    fontSize: 22px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Newsreader
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Newsreader
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  code-metric:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.02em
  code-metric-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: '0'
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-tablet: 1.25rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers an academic, sober, and authoritative interface tailored for empirical software sustainability research and ecosystem analytics. It avoids tech-startup exuberance, playful gamification, and decorative flourishes in favor of structural clarity, analytical rigor, and evidentiary density.

The aesthetic blends structural minimalism with editorial typography and high-density tabular presentation. The tone evokes institutional peer review, rigorous econometric reporting, and longitudinal laboratory instruments. The user experience prioritizes:
- **Epistemic Modesty**: Clear visual boundaries separating observational correlations from causal claims (e.g., dedicated styling for non-causal metrics, confidence intervals, and p-values).
- **High Information Density**: Compact structural rhythm, tabular data supremacy, and immediate scanning without visual noise.
- **Sober Accountability**: Subdued risk signaling that treats project health not as a game score, but as a risk-distribution profile.

## Colors

The palette is engineered around high structural contrast, clinical neutrality, and controlled semantic accents. The surface architecture remains immaculate white and light slate, anchored by deep charcoal slate text to exceed WCAG AAA readability on primary content.

### Core Palette
- **Canvas / Root Background**: `#F8FAFC`
- **Surface / Card Background**: `#FFFFFF`
- **Surface Muted / Inset**: `#F1F5F9`
- **Structural Borders**: `#E2E8F0`
- **Border Active / Strong**: `#CBD5E1`
- **Primary Ink (Slate 900)**: `#0F172A`
- **Secondary Ink (Slate 700)**: `#334155`
- **Tertiary Ink / Meta (Slate 600)**: `#475569`
- **Muted Ink / Placeholder (Slate 500)**: `#64748B`

### Empirical Risk Accents
Risk indicators are restrained to prevent visual alarmism. They never use saturated neon or decorative glows:
- **Low Risk (Soft Emerald)**:
  - Surface: `#ECFDF5`
  - Border: `#A7F3D0`
  - Foreground: `#065F46`
- **Medium Risk (Warm Amber)**:
  - Surface: `#FFFBEB`
  - Border: `#FDE68A`
  - Foreground: `#92400E`
- **High Risk (Muted Crimson)**:
  - Surface: `#FEF2F2`
  - Border: `#FECACA`
  - Foreground: `#991B1B`

### Informational & Methodology Accents
- **Observation / Descriptive Tag**: Slate tinted (`#F1F5F9`, border `#CBD5E1`, text `#1E293B`)
- **Metric Highlight / Delta Neutral**: `#0369A1` (Deep Indigo-Blue, used strictly for hyperlinked citations or statistical references)

## Typography

Typography establishes an intentional dialectic between humanist scholarship and technological analysis:
- **Headlines & Section Titles (Newsreader)**: Evokes published literature, working papers, and empirical proceedings. Rendered in medium weights with restrained leading to preserve academic authority.
- **Body & Tabular Interface (Inter)**: Handles descriptive documentation, analytical rationales, and dense UI controls with neutral legibility and consistent vertical metrics.
- **Metrics, Model Versions, & Quantitative Identifiers (JetBrains Mono)**: Applied to all commit hashes, Bus Factor counts, confidence interval bands, p-values, release tags, and math notation. Monospacing ensures strict tabular vertical alignment when comparing values across rows.

## Layout & Spacing

The layout is structured around an uncompromising, compact multi-column tabular grid designed for dense information ingestion:
- **Grid Architecture**: 12-column fixed-proportion grid on desktop (`max-width: 1440px`), collapsing to 8 columns on tablet and 4 columns on mobile.
- **Rhythm**: Compact base units (`0.25rem / 4px`) to preserve high data density without feeling cluttered.
- **Table Density**: Data row padding is locked to `0.5rem` vertical and `0.75rem` horizontal to maximize row visibility on typical 1080p and 1440p displays.
- **Responsive Adaptations**:
  - Desktop (>1024px): Multi-pane analytical layout with sticky facet filters on the left (280px) and wide tabular canvas on the right.
  - Tablet (768px - 1023px): Collapsible filter drawer; data tables maintain full column width with horizontal scroll bars and sticky primary key columns (e.g., repository name).
  - Mobile (<768px): Metrics reflow from horizontal tables into stacked research ledger cards.

## Elevation & Depth

This design system avoids drop shadows, blurred ambient projections, and simulated volumetric layers. Spatial order is conveyed purely through **crisp borders, flat tonal layering, and high line contrast**.

1. **Flat Tonal Foundation**:
   - Level 0 (Base Canvas): `#F8FAFC`
   - Level 1 (Panels & Surfaces): `#FFFFFF` bounded by a 1px border of `#E2E8F0`
   - Level 2 (Sub-sections, Inset Metrics, Table Headers): `#F1F5F9` with `#E2E8F0` separators
2. **Dividers and Hairlines**:
   - Thin 1px solid outlines `#E2E8F0` delimit every cell, card, and structural panel.
   - Header separation uses a reinforced 2px border `#CBD5E1`.
3. **Overlays & Popovers**:
   - Dropdown menus and methodology tooltips use `#FFFFFF` with a direct 1px solid `#CBD5E1` border and a minimalist, non-decorative hairline shadow: `0 1px 3px rgba(15, 23, 42, 0.08)`.

## Shapes

The interface embraces an architectural, near-square silhouette (Level 1: Soft). 

- **Containers, Cards, and Inputs**: Fixed at `0.25rem` (4px). Rounded corners are purely functional to prevent abrasive pixel clipping without softening the serious, institutional character of the application.
- **Chips, Risk Badges, and Status Tags**: `0.25rem` (4px) or strict square-cut pill forms. No fully circular/bubble pills.
- **Data Visualizations & Sparkbars**: Clean, sharp extremities (0px radius) to guarantee precise graphical reading on coordinate axes.

## Components

### 1. Data Tables
- **Header**: `#F8FAFC` background, 1px bottom border `#CBD5E1`. Typography uses `label-caps` in `#475569`. Column headers for quantitative metrics are right-aligned.
- **Rows**: `#FFFFFF` background with alternating hover state `#F8FAFC`. 1px border `#E2E8F0` between rows. No alternating striped zebra bands; clean white creates an uninterrupted reading plane.
- **Numeric Cells**: Formatted exclusively with `code-metric`, right-aligned, with fixed decimal precision (e.g., `0.420`, `12.4%`).

### 2. Risk & Status Indicators
- **High Risk**: Background `#FEF2F2`, border `#FECACA`, text `#991B1B`. Accompanied by a square 6px marker or explicit text label.
- **Medium Risk**: Background `#FFFBEB`, border `#FDE68A`, text `#92400E`.
- **Low Risk**: Background `#ECFDF5`, border `#A7F3D0`, text `#065F46`.
- **Non-Causal Indicator Tag**: Dedicated monochrome chip displaying `CORRELATIONAL` or `DESCRIPTIVE ONLY` in `JetBrains Mono` (`code-metric-sm`) with background `#F1F5F9`, border `#CBD5E1`, text `#475569`.

### 3. Buttons
- **Primary**: Solid `#0F172A` background, `#FFFFFF` text, `0.25rem` radius, hover state `#1E293B`, active `#334155`.
- **Secondary / Outline**: `#FFFFFF` background, 1px solid border `#CBD5E1`, `#0F172A` text, hover state `#F8FAFC`.
- **Destructive**: `#FEF2F2` background, 1px solid border `#FECACA`, `#991B1B` text.

### 4. Chips and Taxonomy Tags
- Subtle, compact tags featuring 1px solid borders.
- Padding: `2px 6px`.
- Metric tags display label in `Inter` (`11px`) and raw value in `JetBrains Mono` (`11px`), separated by a hairline divider.

### 5. Input Fields & Selects
- 1px solid `#CBD5E1` border on `#FFFFFF` surface.
- Focus ring: Sharp, 1px inset `#0F172A` with 2px offset; no diffuse blue halos.
- Label: Positioned strictly above the input in `Inter` Medium (`12px`), color `#334155`.

### 6. Cards & Metric Tiles
- Bounded by 1px solid `#E2E8F0` with `#FFFFFF` background.
- Top section contains metadata (metric title, time window, model baseline in `code-metric-sm`).
- Core metric presented in `code-metric` (large size), followed by confidence interval subtext (e.g., `95% CI [1.12, 1.48]`).

### 7. Analytical Tooltip (Methodology Callout)
- Activated on hover/click over metric headers.
- Displays mathematical definition, underlying sample size ($N$), data source (e.g., `GitHub Archive API v4`), and econometric caveat.
- Rendered in `#0F172A` background with `#F8FAFC` text, 4px border radius, monospaced footnotes.
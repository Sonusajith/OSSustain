# OSSustain Design System & Visual Specification (`design.md`)

## 1. Design Philosophy & Visual Language
- **Aesthetic Direction:** Academic, empirical, sober, and authoritative. Designed like a rigorous scientific instrument and peer-reviewed research bench (inspired by Our World in Data, Papers with Code, and NCBI informatics tools).
- **Core Principles:**
  - **Empirical Transparency:** Methodological integrity, sample sizes, and confidence intervals prioritized over marketing fluff.
  - **High Information Density with Generous Breathing Room:** Compact data grids, structured cards, crisp tabular layouts, and clear typographic hierarchy.
  - **Restrained Elevation & Flat Borders:** Flat surfaces using 1px crisp borders (`#E2E8F0`) and minimal elevation (`shadow-xs` / `shadow-sm`).
  - **Statistical Integrity in Copy:** Visual badges and descriptions explicitly use "associated indicator", "predictive association", and "calibrated probability" without causal claims.

---

## 2. Color System & Design Tokens

### 2.1 Neutral Surfaces & Typography
| Token | Hex | Usage |
|---|---|---|
| `color-bg-canvas` | `#F8FAFC` | Main application background (Slate-50) |
| `color-surface` | `#FFFFFF` | Card backgrounds, table panels, top navbar |
| `color-surface-subtle` | `#F1F5F9` | Table header rows, code blocks, card footers |
| `color-border` | `#E2E8F0` | Structural dividers, container borders |
| `color-border-subtle` | `#F1F5F9` | Light inner cell dividers |
| `color-text-primary` | `#0F172A` | Primary titles, metrics, bold headings (Slate-900) |
| `color-text-secondary` | `#475569` | Body text, table data, explanatory labels (Slate-600) |
| `color-text-muted` | `#64748B` | Timestamps, model hashes, disclaimers (Slate-500) |
| `color-text-subtle` | `#94A3B8` | Icons, disabled states, placeholder borders |

### 2.2 Primary Brand & Interactive
| Token | Hex | Usage |
|---|---|---|
| `color-brand-primary` | `#0F172A` | Primary CTA buttons, active tabs, header logo |
| `color-brand-hover` | `#1E293B` | Hover states on primary buttons |
| `color-accent-blue` | `#2563EB` | Active links, primary metric lines, test split indicators |
| `color-accent-blue-subtle`| `#EFF6FF` | Active selection backgrounds, info callout containers |

### 2.3 Semantic & Risk Status (Paired Color + Iconography for WCAG AA)
| Status | Background | Text / Icon | Border | Meaning |
|---|---|---|---|---|
| **High Risk** | `#FEF2F2` (Red-50) | `#991B1B` (Red-800) | `#FECACA` | >50% probability of 90d decline |
| **Medium Risk** | `#FFFBEB` (Amber-50) | `#92400E` (Amber-800) | `#FDE68A` | 30%–50% probability of decline |
| **Low Risk** | `#ECFDF5` (Emerald-50) | `#065F46` (Emerald-800) | `#A7F3D0` | Stable historical momentum (<30%) |
| **Unlabeled / Sparse** | `#F8FAFC` (Slate-50) | `#475569` (Slate-600) | `#CBD5E1` | Reference activity < 20 commits or incomplete window |

---

## 3. Typography Hierarchy

- **Font Family (UI & Headings):** `Inter`, `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `Roboto`, `sans-serif`
- **Font Family (Data, Code, Hashes & Metrics):** `JetBrains Mono`, `"Fira Code"`, `ui-monospace`, `monospace`

| Style | Size | Weight | Line Height | Tracking | Usage |
|---|---|---|---|---|---|
| `Display / H1` | 24px (1.5rem) | 700 (Bold) | 1.25 | -0.02em | Screen headers, repository name |
| `Heading / H2` | 18px (1.125rem)| 600 (Semibold)| 1.35 | -0.01em | Card section titles, comparison groups |
| `Subheading / H3` | 14px (0.875rem)| 600 (Semibold)| 1.4 | 0.00em | Inner card headers, table subheaders |
| `Body Large` | 15px (0.9375rem)| 400 (Regular) | 1.5 | 0.00em | Lead paragraphs, key takeaway notes |
| `Body Regular` | 13px (0.8125rem)| 400 (Regular) | 1.5 | 0.00em | Table cell text, descriptive copy |
| `Metric Number` | 28px–32px | 700 (Bold) | 1.1 | -0.02em | Key KPI displays, probabilities |
| `Micro / Badge` | 11px (0.6875rem)| 600 (Semibold)| 1.2 | 0.04em | Risk category badges, dataset hashes |

---

## 4. Spacing, Layout & Responsive Grid

- **Layout Structure:**
  - Max Content Width: `1320px` centered with horizontal padding (`px-4 sm:px-6 lg:px-8`).
  - Top Navigation: Sticky `h-16` border-bottom `#E2E8F0` with backdrop blur (`bg-white/95`).
- **Spacing Scale:**
  - `space-1` (4px), `space-2` (8px), `space-3` (12px), `space-4` (16px), `space-6` (24px), `space-8` (32px), `space-12` (48px).
- **Border Radius:**
  - `rounded-sm` (4px) for micro-badges, code snippets.
  - `rounded-md` (6px) for form inputs, table wrappers, buttons.
  - `rounded-lg` (8px) for primary analytical cards, dialogs.

---

## 5. Component Patterns & Rules

### 5.1 Global App Shell
- **Top Navigation Bar:**
  - Left: Logo icon (Pulse/Nodes) + wordmark `OSSustain` + `MVP v1.0` badge.
  - Center: Nav links (`Cohort Overview`, `Research Results`, `Methodology & Limitations`).
  - Right: Research dataset status indicator (`Dataset: v2024.1 (50 Repos)`), GitHub repository link.
- **Breadcrumbs:** Appears on `/repositories/:id` for seamless 1-click cohort return.

### 5.2 Risk Cards & Indicators
- **Risk Assessment Hero Card:**
  - Displays risk level badge, calibrated probability percentage, prediction date, and model version.
  - Top 3–4 indicators listed with standardized regression coefficients/importance and directional signs (`[−0.42] Newcomer 90d Retention: 8.3%`).
  - Mandatory Causal Disclaimer in muted footer text: *"Statistical predictive association only; does not claim causation or repository abandonment."*

### 5.3 Tabular Data
- Clean header styling with uppercase tracking (`text-xs font-semibold uppercase text-slate-500 bg-slate-50`).
- Sticky table header on long scrolling views.
- Accessible alternative view toggles for all chart data.

---

## 6. Required MVP Screens
1. **Screen 1 — Cohort Overview (`/`):** Summary stats, multi-criteria filter bar (risk, size, quality), and searchable cohort table with probabilities and top indicators.
2. **Screen 2 — Repository Detail (`/repositories/:id`):** 90-day risk forecast card with indicators, synchronized multi-domain historical charts (activity, contributors, retention, responsiveness), and monthly prediction log.
3. **Screen 3 — Research Results (`/research`):** Scientific model comparison matrix (baseline vs. LR vs. RF vs. Gradient Boosting), activity-only vs. extended features PR-AUC lift, feature importance bar charts, and calibration plots.
4. **Screen 4 — Methodology & Limitations (`/methodology`):** Mathematical label definition ($Activity_{future} \le 0.5 \times Activity_{ref}$), 90-day temporal purge gap diagram, complete feature dictionary, and documented study threats.

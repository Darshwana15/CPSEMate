# OneMate Frontend Design System

## Design Philosophy

OneMate is an industrial material standardization and harmonization workbench. It exists to solve high-stakes master data governance across enterprise CPSEs.

The design philosophy is centered around:
- **Material Operations Workbench**: The UI is a high-precision tool for data inspection, technical comparison, mapping decisions, and audit verification. It is not an executive marketing dashboard or a generic SaaS portal.
- **Calm, High-Clarity Density**: Technical operators require immediate visual parsing of complex physical valve attributes (pressure classes, metallurgy, end connections). Whitespace provides structure, not emptiness.
- **Editorial Typography & Alignment**: Visual hierarchy is created through type weight, size, tabular alignment, and crisp borders rather than saturated backgrounds and heavy card elevations.
- **Trustworthy & Authoritative**: The system conveys precision, deterministic logic, and enterprise reliability. Every state change is backed by an immutable audit trail.
- **Backend-Driven Truth**: The frontend is a pure client. It renders state, classifications, and explanations generated strictly by the backend domain engine without client-side interpretation.
- **Strict Contract Compliance**: The frontend may only display data available from the existing backend API contract. It must not invent missing fields or derive new business metrics from unrelated API responses.

---

## Reference Influence

### Otherkind (https://www.otherkind.design/)
* **Typography & Contrast**: Bold, intentional typographic hierarchy, sharp contrast between primary content and structural scaffolding.
* **Minimal Scaffolding**: Border-led layout discipline, eliminating unnecessary visual noise, nested boxes, and drop shadows.
* **Confidence & Composition**: Purposeful whitespace where every element has intentional placement, avoiding decorative filler.

### Idle (https://idle.space/)
* **Soft Light Surfaces**: Neutral, calming background tones (`#F8F9FA` / `#F4F4F6`) that reduce eye fatigue during high-volume catalog reviews.
* **Restrained Color Accents**: Sparing use of color reserved exclusively for semantic signals (status badges, conflict highlights, active states).
* **Airy Precision**: Generous yet disciplined line-heights and component padding that preserve high data density without feeling cramped.

### Mobbin (https://mobbin.com/)
* **Master-Detail Workspaces**: Two-pane split layouts for queues and inspectors, keeping context visible while making decisions.
* **Side-by-Side Comparison**: Distinct dual-column diff views for source vs. candidate materials, aligning corresponding technical attributes row-by-row.
* **Contextual Action Sheets & Dialogs**: Tight, focused action dialogs with required validation fields (e.g. review rejection reasons) that preserve operator momentum.

---

## Visual Personality

| Attribute | OneMate Direction | Avoid |
| :--- | :--- | :--- |
| **Tone** | Industrial, technical, calm, authoritative | Flashy, marketing-heavy, casual |
| **Aesthetic** | Crisp borders, flat surfaces, tabular alignment | Glassmorphism, blurred cards, neon glows |
| **Coloring** | Monochromatic base with subtle semantic tints | Purple/blue SaaS gradients, rainbow palettes |
| **Iconography** | Clean, functional geometric icons (16px/20px) | AI sparkle icons, robot heads, magic wands |
| **Density** | Information-rich, tabular, structured | Oversized cards, giant headings, empty padding |

---

## Color System

```
Backgrounds & Surfaces:
  ├── App Canvas / Background:    #F8F9FA  (Soft warm neutral)
  ├── Card / Panel Surface:       #FFFFFF  (Pure white)
  ├── Secondary Panel / Well:     #F3F4F6  (Subtle inset gray)
  └── Table Row Hover:            #F9FAFB

Borders & Dividers:
  ├── Default Border:             #E5E7EB  (1px crisp divider)
  ├── Subtle Border:              #F0F1F3
  └── Strong Border / Focus:      #111827

Typography:
  ├── Primary Text (Charcoal):    #111827  (Headings, primary codes, active labels)
  ├── Secondary Text (Slate):     #4B5563  (Descriptions, attribute names)
  ├── Muted / Caption:            #6B7280  (Timestamps, table headers, metadata)
  └── Disabled / Placeholder:     #9CA3AF

Brand Accent (Deep Industrial Slate):
  ├── Primary Brand:              #1E293B  (Slate 800)
  ├── Primary Hover:              #0F172A  (Slate 900)
  └── Subtle Brand Tint:          #F1F5F9  (Active navigation background)

Semantic & Classification Status Colors:
  ├── SAME / AUTO_SAME (Sage / Green):
  │     ├── Background:           #ECFDF5  (Emerald 50)
  │     ├── Border:               #A7F3D0  (Emerald 200)
  │     └── Text:                 #065F46  (Emerald 800)
  ├── POTENTIALLY_EQUIVALENT / REVIEW (Amber / Sand):
  │     ├── Background:           #FFFBEB  (Amber 50)
  │     ├── Border:               #FDE68A  (Amber 200)
  │     └── Text:                 #92400E  (Amber 800)
  ├── DIFFERENT / CONFLICT (Muted Brick / Red):
  │     ├── Background:           #FEF2F2  (Red 50)
  │     ├── Border:               #FECACA  (Red 200)
  │     └── Text:                 #991B1B  (Red 800)
  └── NEUTRAL / INACTIVE / SUPERSEDED (Slate):
        ├── Background:           #F3F4F6  (Gray 100)
        ├── Border:               #E5E7EB  (Gray 200)
        └── Text:                 #374151  (Gray 700)
```

---

## Typography

### Typefaces
* **Primary Sans**: `Plus Jakarta Sans` or `Geist Sans` (fallback: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`)
  * Used for all UI text, headings, buttons, labels, and table content.
* **Monospace / Tabular**: `JetBrains Mono` or `Geist Mono` (fallback: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`)
  * Used for material codes (`source_material_code`, `national_code`), identity keys, raw JSON keys/values, and numeric values with `font-variant-numeric: tabular-nums`.

### Type Scale

| Role | Font Size | Line Height | Weight | Letter Spacing | Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Page Title** | 20px (1.25rem) | 26px | 600 (Semibold) | -0.02em | Normal |
| **Section Title** | 16px (1.0rem) | 22px | 600 (Semibold) | -0.01em | Normal |
| **Card Title / Group Header** | 14px (0.875rem) | 20px | 600 (Semibold) | 0.0em | Normal |
| **Table Header** | 11px (0.6875rem) | 16px | 500 (Medium) | +0.05em | Uppercase |
| **Body (Default)** | 13px (0.8125rem) | 18px | 400 (Regular) | 0.0em | Normal |
| **Body Semibold** | 13px (0.8125rem) | 18px | 600 (Semibold) | 0.0em | Normal |
| **Metadata / Caption** | 12px (0.75rem) | 16px | 400 (Regular) | 0.0em | Normal |
| **Code / Attribute Monospace** | 12px (0.75rem) | 16px | 400 / 500 | 0.0em | Normal |

---

## Spacing

OneMate uses a strict 4px baseline grid system:

| Token | Pixels | Application |
| :--- | :--- | :--- |
| `space-1` | 4px | Inline icon gaps, badge internal vertical padding |
| `space-2` | 8px | Button/input internal vertical padding, badge horizontal padding |
| `space-3` | 12px | Input/button horizontal padding, small element gaps |
| `space-4` | 16px | Standard card interior padding, table cell horizontal padding |
| `space-5` | 20px | Inspector panel padding, section separations |
| `space-6` | 24px | Workspace split gaps, major container margins |
| `space-8` | 32px | Page header to content separation |
| `space-12`| 48px | Page bottom padding |

---

## Radius / Borders / Shadows

* **Border Radius**:
  * Badges & Tags: `4px`
  * Buttons & Inputs: `6px`
  * Panels & Cards: `8px`
  * Dialog Modals: `8px`
  * *Strict Rule: No pill-shaped `rounded-full` buttons or excessively rounded `16px+` bubbly cards.*
* **Borders**:
  * Default: `1px solid #E5E7EB`
  * Focused / Active: `1px solid #111827` (with `2px` offset outline)
* **Elevation / Shadows**:
  * Cards / Containers: Flat (`box-shadow: none` or subtle `0 1px 2px 0 rgba(0, 0, 0, 0.03)`)
  * Dropdowns / Popovers: `0 4px 12px -2px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.04)`
  * Modals: `0 12px 24px -4px rgba(0, 0, 0, 0.12), 0 4px 8px -2px rgba(0, 0, 0, 0.06)`

---

## Navigation

* **Structure**: Fixed left sidebar (width: `240px`) on a light gray background (`#F8F9FA`), separated by a clean `1px solid #E5E7EB` vertical border.
* **Brand Header**:
  * Text: **OneMate** (`15px`, Semibold, `#111827`)
  * Subtitle: `Material Harmonization` (`11px`, Medium, `#6B7280`)
* **Primary Navigation Items** (Strict set):
  1. **Dashboard** (Icon: Layout Dashboard)
  2. **CPSEs** (Icon: Building / Enterprise)
  3. **Materials** (Icon: Package / Database)
  4. **Matching** (Icon: Git Compare / Layers)
  5. **Review Queue** (Icon: Check Square / Inbox — includes dynamic badge for pending reviews)
  6. **National Materials** (Icon: Shield Check / Bookmark)
  7. **Audit Trail** (Icon: Clock / History)
* **Item States**:
  * Default: `#4B5563` text, transparent background.
  * Hover: `#111827` text, `#F3F4F6` background.
  * Active: `#111827` text (Semibold), `#FFFFFF` background with `1px solid #E5E7EB` border.

---

## Table Design

Tables are the core data visualization medium for materials, CPSEs, national materials, and audit logs:
* **Header**: Fixed top, height `36px`, background `#F9FAFB`, bottom border `1px solid #E5E7EB`, text `11px` uppercase tracking `+0.05em`, color `#6B7280`.
* **Rows**: Height `44px`, background `#FFFFFF`, bottom border `1px solid #F3F4F6`. Hover state `#F9FAFB`.
* **Columns & Alignment**:
  * Material Codes / Identifiers: Left-aligned, monospace font, semibold `#111827`.
  * Descriptions: Left-aligned, regular `#374151`, truncated with tooltip.
  * Technical Attributes (Valve Type, Size, Pressure, Trim): Monospace/regular, `#4B5563`.
  * Status / Badges: Center or left-aligned semantic badge.
  * Numbers / Counts / Percentages: Right-aligned, tabular figures (`font-variant-numeric: tabular-nums`).
* **Row Selection / Drilldown**: Entire row is clickable, smoothly opening the Inspector slide-over sheet.

---

## Inspector Design

The Inspector is a slide-over panel (width: `480px` or `540px`) anchored to the right side of the screen:
* **Header**: Shows entity identifier (e.g. `source_material_code` or `national_code`), status badge, and close button.
* **Sections**:
  1. **Canonical Normalized Identity**: Clean key-value grid showing extracted technical attributes:
     * Valve Type, Size, Body Material, Pressure Class, End Connection, Trim.
     * Missing values explicitly styled as `UNKNOWN` in muted italics (`#9CA3AF`), never left blank.
  2. **Source Information (Immutable)**:
     * CPSE name/code, original source description, source UOM.
  3. **Original Raw Payload**: Collapsible code block rendering `raw_source_data` with exact original headers preserved.
  4. **Mapping Status & History**: Active mapping link or historical timeline from `/materials/{material_id}/mapping-history`.

---

## Matching Workspace

The Matching Workspace is a split comparison view designed for inspecting candidate material pairs:
* **Layout**: Two side-by-side material cards (Source Material vs. Candidate Material) separated by an attribute comparison bridge.
* **Attribute Comparison Grid**:
  | Attribute | Source (CPSE A) | Status | Candidate (CPSE B) |
  | :--- | :--- | :---: | :--- |
  | **Valve Type** | `BALL` | `MATCH` | `BALL` |
  | **Size** | `DN50` | `MATCH` | `DN50` |
  | **Body Material** | `CARBON_STEEL` | `MATCH` | `CARBON_STEEL` |
  | **Pressure Class** | `CLASS300` | `CONFLICT` | `CLASS150` |
  | **Connection** | `RF` | `MATCH` | `RF` |
  | **Trim** | `SS316` | `MISSING` | `UNKNOWN` |
* **Match Evaluation Card**:
  * **Classification Badge**: Large, crisp badge (`SAME`, `POTENTIALLY_EQUIVALENT`, `DIFFERENT`).
  * **Confidence Score**: Compact percentage readout (e.g. `86%`) with a subtle 4px-high neutral-to-semantic progress bar.
  * **Backend Explanation**: Clean blockquote showing the backend-generated reason string (e.g., *"Same valve type, size, and body material; missing information for trim."*).

---

## Review Workspace

Designed for high-throughput human governance decisions:
* **Two-Pane Layout**:
  * **Left Queue List (35% width)**: Scrollable list of pending recommendations. Each item displays source CPSE, source code, candidate code, classification badge, and timestamp.
  * **Right Decision Workbench (65% width)**: Active recommendation detail, full side-by-side attribute comparison, and persistent action bar.
* **Action Bar**:
  * **Accept** (Button: Deep Slate solid):
    * Disabled or blocked with an explanation banner if the source material has an incomplete identity (enforcing backend rules).
  * **Reject** (Button: White with red outline):
    * Prompts for mandatory `reason` in a compact inline popover or modal.
  * **Mark Different** (Button: White with gray outline):
    * Prompts for mandatory `reason`.
  * **Override** (Button: White with slate outline):
    * Opens searchable modal to select a target `NationalMaterial` + mandatory `reason`.

---

## National Material Workspace

* **Catalog View**: Clean, searchable, filterable table of consolidated National Materials populated strictly from `GET /api/v1/national-materials`.
* **Table Columns (List API)**:
  * `national_code` (e.g., `NM-A1B2C3D4`, monospace, semibold)
  * `canonical_description` (e.g., `Ball Valve, DN50, CS, Class 300, RF, SS316`)
  * `status` (Semantic badge: `ACTIVE`)
* **Inspector View (Detail API - `GET /api/v1/national-materials/{national_material_id}`)**:
  * Displays scalar attributes: `category`, `valve_type`, `size`, `body_material`, `pressure_class`, `connection_type`, `trim`, `normalized_uom`.
  * Displays technical `identity_key` (monospace block).
  * *Note: No unprovided relational counts or mapping lists are assumed.*

---

## Audit Workspace

* **Chronological Event Ledger**: Complete, tamper-evident log of every backend action from `GET /api/v1/audit`.
* **Filter Bar**: Direct filter inputs for `entity_type` (`MATERIAL`, `NATIONAL_MATERIAL`, `MATCH_RECOMMENDATION`) and `entity_id`.
* **Columns**: `Timestamp`, `Actor` (`SYSTEM` vs. Reviewer ID), `Action` (`NORMALIZE`, `MATCH`, `ACCEPT`, `OVERRIDE`, `REJECT`), `Entity Type`, `Entity ID`, `Reason`.
* **State Diff Viewer**: Expandable row or inspector showing JSON before-and-after states with changed keys highlighted.

---

## Dashboard

The Dashboard provides an editorial, spacious, and operational overview. Rather than generic SaaS KPI cards, it presents crisp typographic metric groups, generous spacing, and a clean CPSE operational table with minimal visual chrome.

```
+-----------------------------------------------------------------------------------+
| OneMate Dashboard                                           Operational Overview  |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  INVENTORY                 HARMONIZATION              AUTOMATION       REVIEW     |
|  1,500 Materials           450 National Materials     85.5% Auto       45 Pending |
|  3 CPSEs Registered        1,200 Mapped Materials     1,026 / 1,200    120 Done   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
|  CPSE INVENTORY & HARMONIZATION BREAKDOWN                                         |
|  +-----------------------------------------------------------------------------+  |
|  | CPSE Name          Total Materials    Mapped Materials     Harmonization %  |  |
|  +-----------------------------------------------------------------------------+  |
|  | CPSE Alpha               500                420                84.0%        |  |
|  | CPSE Beta                600                510                85.0%        |  |
|  | CPSE Gamma               400                270                67.5%        |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Metric Structure (Exact Contract Fields):
1. **Inventory**:
   * `total_materials`: Primary count
   * `total_cpses`: Secondary count
2. **Harmonization**:
   * `total_national_materials`: Primary count
   * `total_mapped_materials`: Secondary count
3. **Automation**:
   * `automation_rate_percentage`: Primary percentage (e.g. `85.5%`)
4. **Review**:
   * `pending_reviews`: Actionable items count
   * `completed_reviews`: Audit-confirmed actions count
5. **CPSE Breakdown Table**:
   * `cpse_name`: Enterprise name
   * `total_materials`: Material count per CPSE
   * `mapped_materials`: Active mapped count per CPSE
   * Derived ratio display: `(mapped / total) * 100%`

*No charts, trend lines, or vanity metrics are included.*

---

## Interaction / Motion

* **Transition Durations**: `100ms` to `150ms` ease-out for hover states, button presses, and tab switches.
* **Drawer / Sheet Transitions**: `200ms` cubic-bezier(0.16, 1, 0.3, 1) slide-in from right.
* **Zero Bouncy Springs**: Motion is strictly functional, directional, and instantaneous. No decorative animations or loop effects.

---

## Accessibility

* **Contrast**: All text meets WCAG AA standards (minimum 4.5:1 for normal text, 3:1 for large text and UI borders).
* **Non-Color Reliance**: Every semantic status color is always accompanied by an explicit text label and/or distinct geometric icon.
* **Keyboard Navigation**:
  * Visible focus rings (`2px solid #111827`, `offset 2px`) on all interactive inputs, buttons, and table rows.
  * Standard logical tab navigation across forms, table rows, and review action buttons.

---

## Forbidden Patterns

The following patterns are strictly forbidden across the OneMate interface:
* ❌ **No AI Sparkles / Brain / Robot Imagery**: No "AI Magic", sparkle badges, or chatbot dialogs.
* ❌ **No Gradient Backgrounds or Text**: No purple-to-blue gradients, mesh gradients, or glow effects.
* ❌ **No Glassmorphism**: No backdrop blur overlays, translucent glassy cards, or shiny specular highlights.
* ❌ **No Giant Hero KPIs**: No oversized headline widgets or decorative vanity counters.
* ❌ **No Floating / Heavily Shadowed Cards**: Elements must be grounded with subtle `1px` borders rather than deep elevation shadows.
* ❌ **No Client-Side Scoring or Classification**: The UI must never compute percentages, similarity scores, or conflict classifications locally.
* ❌ **No Invented Fields**: The UI must not display fields or relationships not present in the backend API response.

---

## Implementation Principles

1. **Backend Contract Authority**: The frontend may only display data available from the existing backend API contract (`docs/FRONTEND_API_CONTRACT.md`). It must not invent missing fields or derive new business metrics from unrelated API responses.
2. **Immutable Source Separation**: The UI must explicitly visually distinguish between raw source data (immutable) and normalized attributes (derived).
3. **Graceful Empty & Error States**: Every table, queue, and detail view must provide clean, informative zero-data states and explicit backend error alert displays.
4. **Idempotent Operations**: Actions that trigger backend mutations (normalization, matching, harmonization, reviews) must manage loading states clearly and prevent duplicate submissions.

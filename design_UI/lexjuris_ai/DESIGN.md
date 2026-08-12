---
name: LexJuris AI
colors:
  surface: '#FFFFFF'
  surface-dim: '#dcd9dd'
  surface-bright: '#fbf8fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f2f7'
  surface-container: '#f0edf1'
  surface-container-high: '#eae7eb'
  surface-container-highest: '#e4e1e6'
  on-surface: '#1b1b1e'
  on-surface-variant: '#434655'
  inverse-surface: '#303033'
  inverse-on-surface: '#f3f0f4'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#5e5e67'
  on-secondary: '#ffffff'
  secondary-container: '#e0dee9'
  on-secondary-container: '#62626b'
  tertiary: '#943700'
  on-tertiary: '#ffffff'
  tertiary-container: '#bc4800'
  on-tertiary-container: '#ffede6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#e3e1ec'
  secondary-fixed-dim: '#c7c5d0'
  on-secondary-fixed: '#1a1b23'
  on-secondary-fixed-variant: '#46464f'
  tertiary-fixed: '#ffdbcd'
  tertiary-fixed-dim: '#ffb596'
  on-tertiary-fixed: '#360f00'
  on-tertiary-fixed-variant: '#7d2d00'
  background: '#FAFAFA'
  on-background: '#1b1b1e'
  surface-variant: '#e4e1e6'
  surface-subtle: '#F7F7F8'
  border: '#E4E4E7'
  border-strong: '#D4D4D8'
  success: '#16A34A'
  warning: '#D97706'
  destructive: '#DC2626'
  primary-soft: '#EFF6FF'
typography:
  headline-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 32px
    fontWeight: '650'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Be Vietnam Pro
    fontSize: 26px
    fontWeight: '650'
    lineHeight: 32px
  headline-md:
    fontFamily: Be Vietnam Pro
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
  body-legal:
    fontFamily: Be Vietnam Pro
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 28px
  body-base:
    fontFamily: Be Vietnam Pro
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: Be Vietnam Pro
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  badge:
    fontFamily: Be Vietnam Pro
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  mono:
    fontFamily: monospace
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 260px
  content-max-width: 860px
  evidence-panel: 400px
  gutter: 1.5rem
  stack-sm: 0.5rem
  stack-md: 1rem
  stack-lg: 2rem
---

## Brand & Style

The design system is built on a foundation of **Professionalism, Clarity, and Authority**. As a legal assistant for traffic laws, the interface must prioritize trust and objectivity. The aesthetic follows a **Modern Corporate** approach—clean, structured, and highly legible—avoiding unnecessary decorative elements that could distract from critical legal information.

The visual narrative is "Answer First, Evidence Always." This is achieved through a neutral base that allows semantic status indicators (fines, warnings, effectiveness) to stand out without overwhelming the user. The experience should feel like a digital law clerk: precise, calm, and dependable.

## Colors

The palette is anchored by a **Zinc-based neutral scale** to maintain a serious and institutional feel. 

- **Core Tones:** The background uses a very light off-white (`#FAFAFA`) to reduce eye strain during long reading sessions, while the main text uses a deep Zinc (`#18181B`) for maximum contrast.
- **Primary Accent:** Blue-600 is used exclusively for primary actions and focused states, symbolizing intelligence and reliability.
- **Semantic Logic:** Color is used functionally to categorize legal outcomes:
    - **Destructive (Red):** Reserved for penalties, fines, and critical errors.
    - **Warning (Amber):** Used for legal caveats, uncertainty, or temporal warnings.
    - **Success (Green):** Indicates active legal status, compliance, and "Effective" markers.

## Typography

This design system uses **Be Vietnam Pro** for its excellent Vietnamese diacritic support and contemporary, professional feel. 

- **Readability:** For long-form legal answers, the `body-legal` token uses a generous line height (1.75x) to prevent "wall of text" fatigue.
- **Hierarchy:** Headlines use a custom weight of 650 to create a distinct visual anchor without being overly aggressive.
- **Technicality:** A monospace fallback is used specifically for Document IDs, Clause numbers, and technical metadata to distinguish them from natural language.

## Layout & Spacing

The layout is designed to scale from a single-column mobile view to a sophisticated three-pane desktop environment.

- **Desktop (≥1280px):** A structured layout featuring a fixed **Navigation Sidebar** (left), a centered **Chat Stream** (middle), and an optional **Evidence Panel** (right) for citations.
- **Reading Comfort:** The main chat content is constrained to a maximum width of 860px to maintain an optimal character count per line for legal reading.
- **Grid:** A fluid 8px-based rhythm is used for all internal component spacing to ensure mathematical harmony.
- **Mobile:** Transition to a full-screen chat experience with a sticky top header for the "Event Date" filter and a bottom-docked input composer.

## Elevation & Depth

To maintain a trustworthy and "official" appearance, the system avoids heavy shadows and floating effects, favoring **Tonal Layers** and **Subtle Outlines**.

- **Surface Tiers:** The main background is `#FAFAFA`. Cards and chat bubbles use `#FFFFFF` with a 1px border (`#E4E4E7`) to create separation.
- **Shadows:** Use a single, very soft "Ambient Shadow" (`0 1px 2px rgba(0,0,0,0.04)`) to lift interactive components like buttons and active cards.
- **Backdrop:** Use a standard CSS backdrop-blur (8px) on navigation headers and floating composers to maintain context while keeping the UI clean.
- **Interactive Depth:** On hover, interactive elements should shift from the standard border to a `border-strong` or primary tint rather than increasing shadow depth.

## Shapes

The shape language is **Softly Structured**. While the base roundedness is 12px (Rounded), we use a scale to differentiate between global containers and internal elements:

- **Buttons:** 10px (for a tighter, more precise look).
- **Cards/Input Fields:** 12px - 14px (the standard for container elements).
- **Modals/Composers:** 16px - 18px (to emphasize their role as distinct, elevated layers).
- **Badges/Tags:** Fully rounded (Pill) to distinguish them from interactive buttons.

## Components

- **Buttons:** High-contrast Primary Blue for CTAs. Use ghost or outline styles for secondary actions like "Copy" or "View Source" to keep the focus on the content.
- **Sanction Cards:** Specialized components for legal penalties. These should use a thicker left-border (4px) in the semantic color (Red for fines) and a background tint (e.g., `destructive-bg`).
- **Input Fields:** Use 12px radius with a `border-strong` on focus. The chat composer is the most prominent input, styled with an 18px radius and a soft shadow.
- **Legal Citations (Chips):** Small, pill-shaped tags using `primary-soft` backgrounds. They should look interactive but subordinate to the main text.
- **Status Badges:** Use a "Dot + Text" pattern for effectiveness (e.g., a green dot next to "Effective from Jan 2024").
- **Lists:** Unordered lists in legal text should use custom icons (e.g., Chevron or Scale) rather than standard bullets to reinforce the legal theme.
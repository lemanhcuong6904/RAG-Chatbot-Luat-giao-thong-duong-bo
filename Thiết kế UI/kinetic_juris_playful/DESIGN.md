---
name: Kinetic Juris Playful
colors:
  surface: '#fff8ef'
  surface-dim: '#e1d9c7'
  surface-bright: '#fff8ef'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#fcf3e0'
  surface-container: '#f6edda'
  surface-container-high: '#f0e7d5'
  surface-container-highest: '#eae2cf'
  on-surface: '#1f1b10'
  on-surface-variant: '#4d4632'
  inverse-surface: '#343024'
  inverse-on-surface: '#f9f0dd'
  outline: '#7f775f'
  outline-variant: '#d0c6ab'
  surface-tint: '#705d00'
  primary: '#705d00'
  on-primary: '#ffffff'
  primary-container: '#ffd600'
  on-primary-container: '#705d00'
  inverse-primary: '#e9c400'
  secondary: '#a04100'
  on-secondary: '#ffffff'
  secondary-container: '#fe6b00'
  on-secondary-container: '#572000'
  tertiary: '#006c44'
  on-tertiary: '#ffffff'
  tertiary-container: '#0df7a2'
  on-tertiary-container: '#006c44'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffe170'
  primary-fixed-dim: '#e9c400'
  on-primary-fixed: '#221b00'
  on-primary-fixed-variant: '#544600'
  secondary-fixed: '#ffdbcc'
  secondary-fixed-dim: '#ffb693'
  on-secondary-fixed: '#351000'
  on-secondary-fixed-variant: '#7a3000'
  tertiary-fixed: '#50ffaf'
  tertiary-fixed-dim: '#00e293'
  on-tertiary-fixed: '#002111'
  on-tertiary-fixed-variant: '#005232'
  background: '#fff8ef'
  on-background: '#1f1b10'
  surface-variant: '#eae2cf'
  mint-fresh: '#00F5A0'
  electric-orange: '#FF6B00'
  sun-yellow: '#FFD600'
  midnight-ink: '#1A1C1C'
  soft-cloud: '#F0F4F8'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 42px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: '1.2'
  section-title:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: '1.4'
  body-large:
    fontFamily: Be Vietnam Pro
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-base:
    fontFamily: Be Vietnam Pro
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.6'
  label-md:
    fontFamily: Work Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Work Sans
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  unit: 4px
  gutter-md: 24px
  margin-page: 32px
  stack-section: 48px
  card-gap: 20px
---

## Brand & Style

This design system reimagines legal interactions through a **Playful & Energetic** lens. It transforms the intimidating nature of law into an approachable, gamified experience designed for a modern, digitally-native audience. The brand personality is "The Helpful Sidekick"—optimistic, witty, and tirelessly supportive.

The visual style is a vibrant blend of **Modern Minimalism** and **Neo-Brutalism**. It utilizes high-energy colors and thick, "bouncy" shadows to create a tactile UI that feels responsive and alive. By moving away from sterile corporate norms, the system uses expressive shapes and delightful motion to reduce the anxiety typically associated with legal documentation while maintaining crystal-clear information density.

## Colors

The color palette shifts from serious blues to a high-contrast, "Sun-Drenched" spectrum. 

- **Primary (Sun Yellow - #FFD600):** The core energy of the system. Used for main highlights and primary interactive foundations.
- **Secondary (Electric Orange - #FF6B00):** Drives urgency and high-intent actions like "Submit" or "Sign."
- **Tertiary (Mint Fresh - #00F5A0):** Used for success states, approvals, and "Safe to Proceed" indicators.
- **Neutral:** A very bright, slightly cool-tinted white (#F0F4F8) serves as the background to let the vibrant colors pop without causing eye strain.

Text and structural lines use **Midnight Ink (#1A1C1C)** to ensure maximum legibility and a grounded feel amidst the bright palette.

## Typography

The system uses **Plus Jakarta Sans** for headlines to provide a soft, rounded, and welcoming geometric structure. Its "chunky" weight in display settings adds a sense of friendly authority. 

**Be Vietnam Pro** remains the workhorse for body text, maintaining its excellent readability for complex Vietnamese or English legal strings, but with a slightly tighter line height to feel more cohesive within the "bouncy" UI containers. **Work Sans** is used for labels and functional data to provide a grounded, professional contrast to the expressive headings.

## Layout & Spacing

The layout adopts a **Fluid-Fixed Hybrid**. While content remains centered in a max-width container (920px) for readability, the interface elements use more aggressive, generous padding to create a "breathing" effect.

- **Desktop:** Employs a 12-column grid with wide 24px gutters. Sections are separated by "Stacking Blocks" of 48px to prevent the UI from feeling cluttered.
- **Mobile:** Uses a 16px margin with elements spanning the full width. 
- **Rhythm:** Spacing follows a 4px base unit. Interaction targets (buttons/inputs) are oversized to emphasize the playful, easy-to-tap nature of the system.

## Elevation & Depth

This system avoids traditional soft blurs in favor of **Bouncy Neo-Brutalism**.

- **Shadows:** Instead of diffused light, use hard-edged or "thick" shadows. Primary cards use a 4px-8px offset shadow in a darkened version of the background color or a 10% opacity black.
- **Tonal Layering:** Depth is created by stacking highly rounded shapes on top of each other. Background elements are flat, while interactive elements "lift" using a bold 2px outline and a thick bottom-right shadow.
- **Micro-interactions:** When hovered or pressed, elements should physically "sink" (shadow offset decreases) to provide a tactile, squishy feedback loop.

## Shapes

The shape language is **Extra-Rounded (Pill-based)**. Sharp corners are entirely eliminated to maintain a soft and friendly aesthetic.

- **Containers & Cards:** Use a minimum of 24px (rounded-lg) up to 32px (rounded-xl) to create a "bubble-like" appearance.
- **Interaction Points:** Buttons and tags always default to a full-pill shape (9999px).
- **Icons:** Use doodle-style illustrations or 3D-rendered icons with rounded edges. Avoid thin, clinical line icons.

## Components

- **Buttons:** High-contrast "Sun Yellow" or "Electric Orange" fills with a 2px Midnight Ink border. On hover, the button moves 2px up and 2px left, with the shadow expanding to create a "pop" effect.
- **Cards:** White or Soft Cloud backgrounds with a 2px border. Content inside cards should be padded generously (min 24px).
- **Input Fields:** Oversized height (56px+) with a 32px corner radius. The focus state changes the border from Midnight Ink to Electric Orange with a subtle "bouncy" expansion animation.
- **Chips:** Small, colorful pills used for legal categories. Use a palette of pastel versions of the brand colors (e.g., Pale Mint, Light Peach).
- **Checkboxes & Radios:** Scaled up to 24px in size. Checkmarks should look like "hand-drawn" thick strokes.
- **Status Indicators:** Use 3D-style "blobs" or animated doodle icons (e.g., a spinning sun for loading, a thumbs-up doodle for success).
- **Message Bubbles:** Tail-less, highly rounded bubbles. User messages use the Sun Yellow background; AI responses use a clean white with a thick 4px shadow.
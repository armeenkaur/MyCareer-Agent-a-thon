---
name: Compass Enterprise
colors:
  surface: '#faf8ff'
  surface-dim: '#d8d9e5'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#ecedf9'
  surface-container-high: '#e7e7f3'
  surface-container-highest: '#e1e2ee'
  on-surface: '#191b24'
  on-surface-variant: '#424655'
  inverse-surface: '#2e3039'
  inverse-on-surface: '#eff0fc'
  outline: '#737687'
  outline-variant: '#c2c6d8'
  surface-tint: '#0054d7'
  primary: '#004dc6'
  on-primary: '#ffffff'
  primary-container: '#1464f4'
  on-primary-container: '#f1f2ff'
  inverse-primary: '#b3c5ff'
  secondary: '#3159b6'
  on-secondary: '#ffffff'
  secondary-container: '#799dfe'
  on-secondary-container: '#003183'
  tertiary: '#9b3400'
  on-tertiary: '#ffffff'
  tertiary-container: '#c44400'
  on-tertiary-container: '#fff0ec'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b3c5ff'
  on-primary-fixed: '#001849'
  on-primary-fixed-variant: '#003fa5'
  secondary-fixed: '#dae2ff'
  secondary-fixed-dim: '#b3c5ff'
  on-secondary-fixed: '#001849'
  on-secondary-fixed-variant: '#0e409d'
  tertiary-fixed: '#ffdbcf'
  tertiary-fixed-dim: '#ffb59a'
  on-tertiary-fixed: '#380d00'
  on-tertiary-fixed-variant: '#802a00'
  background: '#faf8ff'
  on-background: '#191b24'
  surface-variant: '#e1e2ee'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.02em
  page-title:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  section-title:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  card-title:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  button:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  metadata:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
  page-title-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 30px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  canvas-max-width: 1440px
  content-max-width: 1280px
  grid-columns: '12'
  gutter: 24px
  margin-desktop: 32px
  margin-mobile: 16px
  card-padding: 24px
  stack-gap-sm: 8px
  stack-gap-md: 16px
  stack-gap-lg: 24px
---

## Brand & Style

This design system is engineered for a high-trust HR technology environment, balancing professional rigor with an approachable, motivational tone. The aesthetic follows a **Corporate / Modern** style, emphasizing clarity, data density without clutter, and a structured information hierarchy.

The visual narrative avoids decorative flourishes like glassmorphism or heavy gradients in favor of "functional elegance." It utilizes a card-based interface to modularize complex HR data, making the platform feel organized and manageable. The goal is to evoke a sense of stability and career progression, ensuring users feel supported and focused.

## Colors

The palette is anchored by a trust-inducing "Primary Blue," drawing inspiration from established travel and finance platforms to project reliability. 

- **Primary & Secondary:** Used for core actions, active states, and brand reinforcement.
- **Semantic Colors:** Reserved strictly for feedback—Red for errors/urgent tasks, Green for completions/success, and Amber for pending items or warnings.
- **Neutral System:** A sophisticated range of grays ensures high legibility. The "Locked" tokens are specifically designed for permission-based UI, providing clear visual cues for restricted HR data without breaking the layout.

## Typography

This design system utilizes **Inter** for its exceptional legibility and systematic feel. The type scale is strictly controlled to maintain an institutional yet modern appearance. 

- **Headings:** Use semi-bold weights with slight negative letter-spacing for larger sizes to maintain a tight, professional look.
- **Body:** The default body size is 14px for data-heavy views and 16px for content-focused areas.
- **Metadata:** 12px is used sparingly for timestamps, captions, and secondary labels to ensure visual hierarchy doesn't overwhelm the user.

## Layout & Spacing

The layout employs a **12-column fluid grid** within a constrained maximum width of 1280px to prevent line lengths from becoming unreadable on ultra-wide monitors.

- **Grid:** 24px gutters provide generous breathing room between cards and components.
- **Navigation:** A collapsible sidebar (280px expanded / 64px collapsed) handles primary app navigation, while a sticky top bar provides global search and profile actions.
- **Mobile Adaptivity:** On mobile devices, the 12-column grid collapses to a 1-column stack. Margins reduce to 16px, and card padding may be reduced to 16px to conserve horizontal space.

## Elevation & Depth

Hierarchy is established through a combination of **Tonal Layers** and subtle **Ambient Shadows**.

- **Level 0 (Background):** #F5F7FA. All primary layout containers sit here.
- **Level 1 (Cards/Surface):** #FFFFFF with a 1px border (#DCE2EA). This is the standard container for all content.
- **Level 2 (Hover/Active):** A very soft shadow (0px 4px 12px rgba(23, 32, 51, 0.05)) is applied when a card is interactive or hovered.
- **Level 3 (Modals/Popovers):** A more pronounced shadow (0px 12px 32px rgba(23, 32, 51, 0.12)) to lift the element clearly above the page context.

## Shapes

The design system uses a **Rounded** shape language to appear modern and friendly without sacrificing the "serious" nature of HR technology. 

- **Standard Radius:** 8px (0.5rem) for small components like inputs and buttons.
- **Large Radius (rounded-lg):** 12px (0.75rem) for cards and main content containers.
- **Full Radius:** Reserved for avatars, tags/chips, and specific toggle switches.

## Components

### Buttons
- **Primary:** Solid #1464F4 with white text. 8px border radius.
- **Secondary:** Outlined with #DCE2EA and #1464F4 text.
- **Ghost:** No border, #647085 text, appearing only on hover with a light gray background.

### Cards
- Always use white background, 12px corner radius, and a 1px #DCE2EA border.
- Default internal padding is 24px.
- Use a "Card Header" style with a 1px bottom border for complex data displays.

### Input Fields
- 8px border radius, 1px #DCE2EA border.
- Active/Focus state uses a 1px #1464F4 border with a subtle 2px blue glow (ring).
- Placeholder text uses #8A94A6.

### Chips & Tags
- Pill-shaped (fully rounded).
- Use light tinted backgrounds of the semantic colors (e.g., Success Green at 10% opacity) with the dark semantic hex for the text.

### Progress Indicators
- Use the Primary Blue for standard progress and Success Green for completions.
- Linear bars should have a 4px height and rounded caps.
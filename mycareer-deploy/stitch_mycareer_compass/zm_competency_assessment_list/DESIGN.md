---
name: MMT MyBiz Talent
colors:
  surface: '#fff8f7'
  surface-dim: '#f4d2d0'
  surface-bright: '#fff8f7'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#fff0ef'
  surface-container: '#ffe9e7'
  surface-container-high: '#ffe1df'
  surface-container-highest: '#fddbd8'
  on-surface: '#291716'
  on-surface-variant: '#5d3f3d'
  inverse-surface: '#402b2a'
  inverse-on-surface: '#ffedeb'
  outline: '#926e6c'
  outline-variant: '#e7bdb9'
  surface-tint: '#c0001f'
  primary: '#b4001d'
  on-primary: '#ffffff'
  primary-container: '#df162b'
  on-primary-container: '#fff4f3'
  inverse-primary: '#ffb3ae'
  secondary: '#005cab'
  on-secondary: '#ffffff'
  secondary-container: '#0075d7'
  on-secondary-container: '#fefcff'
  tertiary: '#005f81'
  on-tertiary: '#ffffff'
  tertiary-container: '#0079a3'
  on-tertiary-container: '#eef7ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad7'
  primary-fixed-dim: '#ffb3ae'
  on-primary-fixed: '#410004'
  on-primary-fixed-variant: '#930015'
  secondary-fixed: '#d5e3ff'
  secondary-fixed-dim: '#a6c8ff'
  on-secondary-fixed: '#001c3b'
  on-secondary-fixed-variant: '#004786'
  tertiary-fixed: '#c3e8ff'
  tertiary-fixed-dim: '#7bd0fe'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c68'
  background: '#fff8f7'
  on-background: '#291716'
  surface-variant: '#fddbd8'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
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
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  xs: 0.25rem
  sm: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 2rem
  gutter: 1.5rem
  margin-mobile: 1rem
  margin-desktop: 2.5rem
---

## Brand & Style

The design system is engineered for a high-velocity travel-tech environment, specifically tailored for corporate talent and business travel management. The brand personality is **reliable, efficient, and professional**, balancing the excitement of travel with the rigor of corporate procurement.

The design style follows a **Corporate / Modern** aesthetic. It prioritizes clarity and utility, using a high-contrast palette to drive user action. The interface relies on structured white space and a systematic grid to reduce cognitive load during complex booking workflows. Every element is designed to evoke trust, ensuring users feel confident while managing high-stakes travel arrangements.

## Colors

The palette is anchored by the signature Red and Blue, symbolizing energy and stability respectively. 

- **Primary (#df162b):** Reserved for primary actions, branding moments, and critical alerts. It represents the core energy of the platform.
- **Secondary (#008cff):** Used for secondary interactive elements, links, and travel-specific categories (like flights). It provides a cooling contrast to the primary red.
- **Surface & Backgrounds:** Pure white is the primary surface for cards and containers to maximize legibility. A light grey (#f2f2f2) is used for section backgrounds to create subtle depth.
- **Typography:** A strict hierarchy uses pure black for headings to ensure maximum impact, while a softened dark grey is used for body text to improve long-form reading comfort.

## Typography

The design system utilizes **Inter** across all levels to maintain a systematic, utilitarian feel. The typographic scale is optimized for data-dense environments.

Headlines use bold weights and tighter letter spacing to command attention. Body text is set with generous line heights to ensure readability in complex booking forms and itineraries. Labels are frequently used in uppercase with a medium or semi-bold weight to distinguish metadata from content. 

On mobile devices, headline sizes are scaled down to prevent excessive word wrapping, while body sizes remain constant to preserve accessibility.

## Layout & Spacing

The design system employs a **Fixed Grid** layout for desktop (12 columns) and a **Fluid Grid** for mobile (4 columns). 

- **Desktop:** 1200px max-width container, centered on the viewport. This provides a stable reading experience for corporate dashboards.
- **Rhythm:** An 8px (0.5rem) base unit governs all spacing. Components are separated by `lg` (24px) or `xl` (32px) increments to create distinct visual groups.
- **Safe Areas:** Mobile screens use a 16px side margin, while desktop uses a more generous 40px margin to provide breathing room in complex layouts.
- **Gutters:** Standardized at 24px to ensure clear separation between grid items without breaking the visual flow.

## Elevation & Depth

This design system uses **Tonal Layers** and **Low-Contrast Outlines** rather than heavy shadows to maintain a clean, professional appearance.

1.  **Level 0 (Base):** The #f2f2f2 background.
2.  **Level 1 (Surface):** White cards (#ffffff) with a 1px border (#e0e0e0). No shadow is used here to keep the UI flat and fast.
3.  **Level 2 (Hover/Active):** When an element is interacted with, a subtle ambient shadow (4px blur, 10% opacity, neutral tint) is applied to suggest lift.
4.  **Level 3 (Overlays):** Modals and dropdowns use a more pronounced shadow (16px blur, 15% opacity) to clearly separate the action layer from the background.

Depth is primarily communicated through the contrast between the light grey background and the white component surfaces.

## Shapes

The shape language is defined by **Rounded (8px)** corners across all primary UI components. This choice softens the "corporate" feel, making the tool feel approachable and modern while maintaining a geometric structure that suggests precision.

- **Standard Buttons & Inputs:** 8px (0.5rem) radius.
- **Cards & Containers:** 8px (0.5rem) radius for internal and external boundaries.
- **Chips & Tags:** Use `rounded-xl` (1.5rem) to create a distinct, pill-shaped silhouette that differentiates metadata from actionable buttons.

## Components

### Buttons
- **Primary:** Solid #df162b with white text. 8px roundedness. Bold Inter text.
- **Secondary:** Outlined with #008cff or solid #008cff with white text for travel-specific actions.
- **Ghost:** No background, #4a4a4a text, used for tertiary actions like "Cancel."

### Input Fields
- White background with a 1px #e0e0e0 border. 
- On focus, the border shifts to #008cff with a subtle 2px glow.
- Labels are placed above the field in `body-sm` bold.

### Cards
- White surface, 1px border, 8px corner radius.
- Used for flight results, hotel options, and talent profiles. 
- Header areas within cards often use a subtle #f2f2f2 top bar.

### Chips & Badges
- Pill-shaped (fully rounded).
- Used for "Policy Compliant" (Green), "Out of Policy" (Red), or "Pending" (Yellow).
- Small typography (`label-md`) to keep them unobtrusive.

### Lists & Tables
- High density. 
- Row heights are kept tight (48px - 56px). 
- Alternating row stripes or subtle dividers (#f2f2f2) to guide the eye across data points.

### Progress Indicators
- Linear bars for booking steps using the Secondary Blue.
- Circular loaders for "Searching" states to provide visual feedback during API calls.
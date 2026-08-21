---
name: Aetheric HUD
colors:
  surface: '#0f1419'
  surface-dim: '#0f1419'
  surface-bright: '#353a3f'
  surface-container-lowest: '#0a0f14'
  surface-container-low: '#171c21'
  surface-container: '#1b2025'
  surface-container-high: '#252a30'
  surface-container-highest: '#30353b'
  on-surface: '#dee3ea'
  on-surface-variant: '#bac9cc'
  inverse-surface: '#dee3ea'
  inverse-on-surface: '#2c3136'
  outline: '#849396'
  outline-variant: '#3b494c'
  surface-tint: '#00daf3'
  primary: '#c3f5ff'
  on-primary: '#00363d'
  primary-container: '#00e5ff'
  on-primary-container: '#00626e'
  inverse-primary: '#006875'
  secondary: '#d1bcff'
  on-secondary: '#3c0090'
  secondary-container: '#7000ff'
  on-secondary-container: '#ddcdff'
  tertiary: '#ffe7e2'
  on-tertiary: '#621100'
  tertiary-container: '#ffc2b3'
  on-tertiary-container: '#aa2600'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#9cf0ff'
  primary-fixed-dim: '#00daf3'
  on-primary-fixed: '#001f24'
  on-primary-fixed-variant: '#004f58'
  secondary-fixed: '#e9ddff'
  secondary-fixed-dim: '#d1bcff'
  on-secondary-fixed: '#23005b'
  on-secondary-fixed-variant: '#5700c9'
  tertiary-fixed: '#ffdad2'
  tertiary-fixed-dim: '#ffb4a2'
  on-tertiary-fixed: '#3c0700'
  on-tertiary-fixed-variant: '#8a1d00'
  background: '#0f1419'
  on-background: '#dee3ea'
  surface-variant: '#30353b'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: 0.02em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.1em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 24px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-edge: 40px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

This design system is engineered for high-performance data environments and mission-critical monitoring. The brand personality is clinical, sophisticated, and technologically advanced, evoking a sense of precision and "quiet intelligence."

The visual style is a fusion of **Minimalism** and **Glassmorphism**, specifically tailored for a Head-Up Display (HUD) experience. It prioritizes data clarity through semi-transparent layers, high-definition thin strokes, and subtle luminous accents. The atmosphere is immersive, using "deep space" depth to separate monitoring layers without breaking the user's focus. 

**Core Principles:**
- **Translucency as Hierarchy:** Depth is communicated through varying levels of background blur and opacity rather than solid colors.
- **Luminous Precision:** Use of glow is reserved for active states, critical alerts, and data visualization highlights.
- **Technical Elegance:** Typography and icons are lean, avoiding unnecessary weight to ensure the UI feels light and responsive.

## Colors

The palette is rooted in a "Deep Space" neutral base to maximize the contrast of luminous data points. 

- **Primary (Electric Cyan):** Used for active data streams, primary call-to-actions, and "healthy" status indicators.
- **Secondary (Obsidian Purple):** Used for subtle accents, data grouping, and depth-defining shadows.
- **Tertiary (Warning Ember):** Reserved strictly for alerts, critical performance thresholds, and errors.
- **Neutral:** A range of desaturated deep blues and grays that form the "glass" substrate and inactive UI elements.

All surfaces must maintain a level of alpha-transparency between 40% and 80% to allow for the layered HUD effect.

## Typography

The typography system balances futuristic geometry with technical legibility. 

- **Space Grotesk** handles high-level headings, providing a distinctive "tech" silhouette.
- **Geist** is used for interface text and descriptions due to its exceptional clarity and neutral character.
- **JetBrains Mono** is mandatory for all numerical data, status readouts, and labels. Its fixed-width nature prevents layout "jitter" during real-time data updates.

Maintain a "Light" or "Regular" weight for most labels to preserve the airy HUD aesthetic; reserve "Bold" weights for critical data values.

## Layout & Spacing

This design system utilizes a **Fluid Grid** with fixed-width gutter constraints to maintain a sense of structural integrity across varying resolutions.

- **Grid:** A 12-column system is used for desktop. 
- **Rhythm:** An 8px base unit drives all spacing, but 4px "micro-steps" are used for tight technical readouts (e.g., spacing between a label and its data point).
- **Safe Areas:** Large 40px external margins ensure the UI feels like a floating overlay on the background environment.
- **Mobile Reflow:** On mobile, columns collapse to a single stack, and horizontal margins reduce to 16px. All "Glass" panels transition to 95% opacity to maintain legibility on smaller screens.

## Elevation & Depth

Depth is achieved through **Glassmorphism** and **Luminous Layering** rather than traditional drop shadows.

1.  **Backdrop Blur:** Every container must apply a `backdrop-filter: blur(20px)`. This creates the frosted glass effect.
2.  **Inner Glow:** Surfaces use a 1px internal border (`inset`) with a low-opacity white or primary color to simulate light catching the edge of a glass pane.
3.  **Z-Axis Hierarchy:**
    - **Level 0 (Background):** Deep charcoal/blue gradient.
    - **Level 1 (Panels):** 40% opacity glass.
    - **Level 2 (Modals/Popovers):** 70% opacity glass with a 10% primary-tinted outer glow.
4.  **Floating Elements:** Elements like tooltips or floating action buttons should have no solid background, only a blur effect and a distinct 1.5px border.

## Shapes

The shape language is sharp and architectural. 

- **Soft (0.25rem):** Standard for cards, input fields, and status badges. This creates a modern "precision-machined" look.
- **Sharp (0px):** Used for progress bars, separators, and technical "brackets" surrounding data points.
- **Pill-shaped:** Used exclusively for interactive toggle switches and specific "Live" indicators to distinguish them from static data containers.

## Components

- **Buttons:** Ghost-style by default with 1px borders. On hover, the background fills with a 20% primary color tint and the border glow intensifies.
- **Input Fields:** Bottom-border only, or a fully enclosed glass container with 10% opacity. Focus state triggers a primary-color neon "underline" glow.
- **Chips / Badges:** Small, monochromatic, and semi-transparent. Use "JetBrains Mono" for the text.
- **Progress Bars / Gauges:** High-contrast cyan against a 10% opacity track. Use thin 2px or 4px heights for a sleek look.
- **Cards:** Defined by a 1px border (`rgba(255,255,255,0.1)`) and a subtle gradient fill. No heavy drop shadows.
- **HUD Brackets:** Decorative corner elements (L-shapes) used to frame high-priority data modules, reinforcing the "targeting system" aesthetic.
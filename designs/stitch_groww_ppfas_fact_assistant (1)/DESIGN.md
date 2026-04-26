---
name: Fintech Clarity
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
  on-surface-variant: '#3c4a43'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#6b7b72'
  outline-variant: '#bacac1'
  surface-tint: '#006c4f'
  primary: '#006c4f'
  on-primary: '#ffffff'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#2fe0aa'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#354ae4'
  on-tertiary: '#ffffff'
  tertiary-container: '#a9b2ff'
  on-tertiary-container: '#142dce'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#dfe0ff'
  tertiary-fixed-dim: '#bcc2ff'
  on-tertiary-fixed: '#000b62'
  on-tertiary-fixed-variant: '#102bcd'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  h1:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
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
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  numeric-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 32px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  container-margin: 20px
  gutter: 16px
---

## Brand & Style

The design system is rooted in the "Modern Corporate" aesthetic, specifically tailored for the fintech sector. It prioritizes clarity, speed, and financial confidence. The personality is approachable yet professional, eliminating unnecessary friction to foster a sense of mastery over one's finances. 

The visual style leans heavily on **Minimalism** with a focus on high-quality execution. It utilizes generous white space to reduce cognitive load, precise grid alignment for structural integrity, and subtle tonal shifts to indicate hierarchy. The emotional response should be one of "effortless trust"—the user should feel that the interface is as stable and reliable as the financial institution it represents.

## Colors

The palette is led by a vibrant, optimistic Green (#00D09C), used strategically for primary actions and "growth" indicators. The foundation of the UI is built on a Deep Navy (#0F172A), which provides the necessary weight and authority for typography and secondary accents.

- **Primary:** Reserved for the main "Call to Action" (CTA) buttons, progress bars, and active states.
- **Secondary:** Used for heavy text, icons, and structural elements like headers.
- **Neutral:** A range of slate grays used for secondary text, borders, and disabled states.
- **Surface:** Subtle off-white backgrounds are used to differentiate cards and sections from the pure white base.

## Typography

This design system utilizes **Inter** across all levels to ensure maximum legibility and a systematic, utilitarian feel. The hierarchy is strictly enforced through weight and scale.

For financial data, "tabular figures" (mono-spaced numbers) must be used to ensure that columns of currency values align perfectly for quick scanning. Headlines use tighter letter spacing to feel more cohesive, while small labels use slightly increased tracking to maintain readability at small sizes.

## Layout & Spacing

The system follows a **Fluid Grid** model with a fixed 8px baseline rhythm. For mobile and desktop interfaces, a 12-column grid is standard, though mobile views consolidate into a single column with consistent 20px outer margins.

The spacing philosophy focuses on "Grouping by Proximity." Related elements (like an input label and its field) use `xs` or `sm` spacing, while distinct sections within a card use `lg` spacing to ensure the UI feels airy and uncluttered. Touch targets for all interactive elements must never fall below 48x48px, even if the visual element is smaller.

## Elevation & Depth

This design system uses **Tonal Layers** and **Ambient Shadows** to create a sense of organized depth. Rather than heavy shadows, depth is communicated through:

1.  **Level 0 (Base):** Pure white (#FFFFFF) background.
2.  **Level 1 (Cards/Containers):** Subtle surface shifts (#F8FAFC) or white cards with a very soft, high-diffusion shadow (0px 4px 20px rgba(15, 23, 42, 0.05)).
3.  **Level 2 (Modals/Overlays):** Elevated surfaces with a more pronounced, darker shadow to pull the user's focus.

Avoid inner shadows or complex gradients. The goal is a flat, layered look that feels physical but light.

## Shapes

The shape language is defined by **Rounded** corners, specifically using a 0.5rem (8px) base radius for standard components like buttons and input fields. 

Larger containers, such as investment cards or bottom sheets, use `rounded-lg` (16px) or `rounded-xl` (24px) to feel softer and more modern. This moderate rounding strikes a balance between the precision of a professional tool and the friendliness of a consumer-facing app.

## Components

- **Buttons:** Primary buttons use the Groww Green background with white text. They are full-width on mobile to maximize touch targets. Secondary buttons use a ghost style with a subtle border or a light gray background.
- **Input Fields:** Minimalist design with a focus on focus. When inactive, inputs have a light gray border. Upon focus, the border shifts to the Primary Green and the label floats or remains clearly visible. Use large padding (16px) for ease of interaction.
- **Cards:** White backgrounds with a very thin #E2E8F0 border or a soft ambient shadow. Cards are the primary vehicle for displaying stock info, portfolio balances, or news.
- **Status Indicators:** Clear, high-contrast pills. "Buy/Up" uses Green (#00D09C) and "Sell/Down" uses Red (#EB5757). These must always be accompanied by icons (up/down arrows) to ensure accessibility for colorblind users.
- **Chips:** Small, rounded pills used for filters or tags (e.g., "Equity," "Mutual Funds"). Active chips take on a primary green tint with a darker green text.
- **Lists:** Clean, borderless list items with high-contrast primary text and muted secondary text. Every list item should have a minimum height of 64px to ensure easy tapping.
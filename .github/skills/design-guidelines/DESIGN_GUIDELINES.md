# Design Guidelines - EQUITEK Frontend

## Overview
This document outlines the design system, visual guidelines, and technical implementation for the EQUITEK Excel Generator frontend application.

---

## Color Palette

### Brand Colors
| Color Name | Hex Code | Tailwind Class | Usage |
|------------|----------|----------------|-------|
| Primary Red | `#b91c1c` | `red-700` | Primary brand color, sidebar, CTAs |
| Primary Red Hover | `#dc2626` | `red-600` | Hover states for sidebar items |
| Primary Red Dark | `#991b1b` | `red-800` | Button pressed/active states |
| Primary Red Light | `#fef2f2` | `red-50` | Backgrounds, alerts (light) |
| Error Red | `#f87171` | `red-400` | Error borders and icons |
| Error Red Text | `#b91c1c` | `red-700` | Error text |
| Error Red Accent | `#ef4444` | `red-500` | Error messages |

### Interactive Colors
| Color Name | Hex Code | Tailwind Class | Usage |
|------------|----------|----------------|-------|
| Blue Primary | `#2563eb` | `blue-600` | Interactive buttons, primary actions |
| Blue Hover | `#3b82f6` | `blue-500` | Button hover states |

### Neutral Colors (Light Mode)
| Color Name | Hex Code | Tailwind Class | Usage |
|------------|----------|----------------|-------|
| Background | `#ffffff` | `bg-white` | Page background |
| Foreground | `#171717` | Custom var (`var(--foreground)`) | Primary text |
| Surface Light | `#f9fafb` | `gray-50` | Card backgrounds, secondary surfaces |
| Surface | `#f3f4f6` | `gray-100` | Upload zones, input backgrounds |
| Border | `#d1d5db` | `gray-300` | Borders, dividers |
| Text Secondary | `#9ca3af` | `gray-400` | Placeholder text |
| Text Tertiary | `#6b7280` | `gray-500` | Helper text |
| Text Muted | `#4b5563` | `gray-600` | Secondary text |

### Dark Mode Colors
| Color Name | Hex Code | Tailwind Class | Usage |
|------------|----------|----------------|-------|
| Background Dark | `#0a0a0a` | Custom var | Dark mode background |
| Foreground Dark | `#ededed` | Custom var | Dark mode text |
| Surface Dark | `#030712` | `gray-950` | Dark surfaces |
| Surface Medium | `#1f2937` | `gray-800` | Cards in dark mode |
| Surface Light | `#111827` | `gray-900` | Input backgrounds dark |
| Border Dark | `#4b5563` | `gray-600` | Dark mode borders |

---

## Typography

### Font Families
```css
--font-geist-sans: 'Geist', system-ui, -apple-system, sans-serif;
--font-geist-mono: 'Geist Mono', 'Courier New', monospace;
```

| Font Family | Usage | CSS Variable |
|-------------|-------|--------------|
| Geist Sans | Primary UI text | `var(--font-geist-sans)` |
| Geist Mono | Code blocks, JSON display | `var(--font-geist-mono)` |

### Font Sizes & Scale
| Name | Size | Tailwind Class | Usage |
|------|------|----------------|-------|
| XS | 0.75rem (12px) | `text-xs` | Labels, captions |
| SM | 0.875rem (14px) | `text-sm` | Body text, descriptions |
| Base | 1rem (16px) | `text-base` | Default text |
| LG | 1.125rem (18px) | `text-lg` | Emphasized text |
| XL | 1.25rem (20px) | `text-xl` | Section headings |
| 2XL | 1.5rem (24px) | `text-2xl` | Page titles |
| 3XL | 1.875rem (30px) | `text-3xl` | Hero headings |

### Font Weights
| Weight | Value | Tailwind Class | Usage |
|--------|-------|----------------|-------|
| Semibold | 600 | `font-semibold` | Navigation items, buttons |
| Bold | 700 | `font-bold` | Headings, emphasis |
| Extrabold | 800 | `font-extrabold` | Logo, hero text |

### Text Utilities
```css
tracking-tight      /* -0.025em - Headings */
tracking-wide       /* 0.025em - Body text */
tracking-widest     /* 0.1em - Logo, labels */
uppercase           /* Uppercase labels */
antialiased         /* Smooth text rendering */
```

---

## Spacing System

Using Tailwind's default spacing scale (1 unit = 0.25rem = 4px):

| Size | Value | Common Usage |
|------|-------|--------------|
| 1 | 4px | Tight gaps |
| 2 | 8px | Icon spacing |
| 3 | 12px | Small gaps |
| 4 | 16px | Standard padding |
| 5 | 20px | Medium padding |
| 6 | 24px | Large padding |
| 8 | 32px | Section spacing |
| 16 | 64px | Large section spacing |
| 20 | 80px | Upload zone padding |

---

## Border Radius

| Name | Value | Tailwind Class | Usage |
|------|-------|----------------|-------|
| Default | 0.25rem (4px) | `rounded` | Small elements |
| Large | 0.5rem (8px) | `rounded-lg` | Cards, containers |
| XL | 0.75rem (12px) | `rounded-xl` | Buttons, inputs |
| 2XL | 1rem (16px) | `rounded-2xl` | Large cards |

---

## Shadows

| Name | Tailwind Class | CSS Value | Usage |
|------|----------------|-----------|-------|
| Medium | `shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Buttons, small cards |
| XL | `shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Modal dialogs, elevated cards |

---

## Component Patterns

### Buttons

#### Primary Button (Red)
```tsx
<button className="bg-red-700 text-white font-bold px-8 py-3 rounded-xl 
                   transition hover:bg-red-800 active:scale-[0.98]">
  Upload File
</button>
```

#### Primary Button (Blue)
```tsx
<button className="bg-blue-600 text-white font-semibold py-2.5 px-4 rounded-xl 
                   shadow-md transition-all duration-150 hover:bg-blue-500 
                   active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed">
  Generate
</button>
```

### Cards

#### Light Surface Card
```tsx
<div className="rounded-2xl bg-white p-5 shadow-xl ring-1 ring-white/5">
  {/* Content */}
</div>
```

### Navigation

#### Sidebar
```tsx
<aside className="w-56 min-h-screen bg-red-700 flex flex-col">
  {/* Sidebar content */}
</aside>
```

#### Navigation Items
```tsx
{/* Active state */}
<a className="px-4 py-2 rounded font-semibold text-sm bg-white text-red-700">
  Convert
</a>

{/* Inactive state */}
<a className="px-4 py-2 rounded font-semibold text-sm text-white hover:bg-red-600 transition">
  History
</a>
```

### Forms & Inputs

#### Text Input
```tsx
<input className="w-full px-4 py-2 rounded-xl bg-gray-100 border border-gray-300 
                  focus:ring-2 focus:ring-blue-500 outline-none" />
```

#### Textarea
```tsx
<textarea className="flex-1 resize-none rounded-xl bg-gray-900 p-4 
                     font-mono text-sm leading-relaxed text-gray-100 
                     outline-none placeholder:text-gray-600 
                     focus:ring-2 focus:ring-blue-500" />
```

### Upload Zone
```tsx
<label className="border-2 border-dashed rounded-lg p-20 
                  flex flex-col items-center justify-center gap-3 
                  transition-colors cursor-pointer
                  border-gray-300 bg-gray-100
                  hover:border-red-600 hover:bg-red-50">
  {/* Upload content */}
</label>
```

### Alerts & Messages

#### Error Alert
```tsx
<div className="flex items-start gap-2 rounded-lg border border-red-400 
                bg-red-50 p-3 text-sm text-red-700" role="alert">
  <span className="mt-0.5 shrink-0 text-red-500">⚠</span>
  <span>{errorMessage}</span>
</div>
```

### Loading States

#### Skeleton Loader
```tsx
<div className="animate-pulse space-y-3 pt-2">
  <div className="h-4 w-full rounded bg-gray-600" />
  <div className="h-4 w-5/6 rounded bg-gray-600" />
  <div className="h-4 w-4/6 rounded bg-gray-600" />
</div>
```

---

## Layout Guidelines

### Grid System
- Use Tailwind's grid system with responsive breakpoints
- Default: Single column on mobile
- Desktop (lg): Two columns for forms

```tsx
<div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
  {/* Content */}
</div>
```

### Container Sizing
```tsx
<div className="mx-auto max-w-5xl">  {/* Centered container, max 64rem */}
<div className="max-w-3xl">          {/* Medium container, max 48rem */}
<div className="max-w-md">           {/* Small container, max 28rem */}
```

### Sidebar Layout
```tsx
<div className="flex min-h-screen">
  <Sidebar />
  <main className="flex-1 bg-gray-50">
    {/* Page content */}
  </main>
</div>
```

---

## CSS Architecture

### Technology Stack
- **CSS Framework**: Tailwind CSS v4
- **Preprocessor**: PostCSS with @tailwindcss/postcss
- **Methodology**: Utility-first with component composition

### File Structure
```
src/
  app/
    globals.css          # Global styles, CSS variables, Tailwind imports
    layout.tsx           # Font definitions, root layout
  components/            # React components with inline Tailwind classes
```

### CSS Variables
Defined in `globals.css`:
```css
:root {
  --background: #ffffff;
  --foreground: #171717;
}

@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}
```

---

## Animations & Transitions

### Transition Classes
```tsx
transition              /* All properties, 150ms */
transition-all          /* All properties, explicit */
transition-colors       /* Color properties only */
duration-150            /* 150ms */
```

### Interactive Feedback
```tsx
hover:bg-red-800        /* Hover state */
active:scale-[0.98]     /* Click feedback */
disabled:opacity-50     /* Disabled state */
disabled:cursor-not-allowed
```

### Loading Animation
```tsx
animate-pulse           /* Skeleton loaders */
```

---

## Accessibility Guidelines

### Focus States
All interactive elements should have visible focus states:
```tsx
focus:ring-2 focus:ring-blue-500
focus:outline-none
```

### ARIA Labels
```tsx
aria-label="File upload drop zone"
role="alert"
```

### Keyboard Navigation
- All buttons and links should be keyboard accessible
- Maintain logical tab order
- Provide skip links for navigation

---

## Responsive Design

### Breakpoints (Tailwind Defaults)
| Breakpoint | Min Width | Prefix |
|------------|-----------|--------|
| Mobile | < 640px | (default) |
| Tablet | 640px | `sm:` |
| Desktop | 1024px | `lg:` |
| Large Desktop | 1280px | `xl:` |

### Mobile-First Approach
```tsx
{/* Mobile default, desktop override */}
<div className="px-4 lg:px-8">
<div className="grid-cols-1 lg:grid-cols-2">
```

---

## Best Practices

### 1. Component Composition
- Keep components small and focused
- Use Tailwind classes directly in components
- Avoid custom CSS unless absolutely necessary

### 2. Consistency
- Use the defined color palette consistently
- Maintain spacing rhythm (multiples of 4px)
- Follow established component patterns

### 3. Performance
- Minimize custom CSS
- Leverage Tailwind's purge for production builds
- Use semantic HTML elements

### 4. Maintainability
- Document any deviations from these guidelines
- Update this document when adding new patterns
- Keep color palette centralized

---

## Browser Support
- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Edge (latest 2 versions)

---

## Tools & Resources
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Geist Font](https://vercel.com/font)
- [Heroicons](https://heroicons.com/) (recommended icon set)

---

**Last Updated**: March 2026  
**Version**: 1.0.0

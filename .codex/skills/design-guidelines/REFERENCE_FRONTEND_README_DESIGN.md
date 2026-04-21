## Design System


EQUITEK uses a cohesive design system built with Tailwind CSS. For complete design guidelines, see **[DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md)**.

### Core Design Principles

#### Color Palette

**Brand Colors**
- Primary: Red-700 (`#b91c1c`) - Main brand color used for sidebar, primary buttons
- Accent: Blue-600 (`#2563eb`) - Interactive elements, CTAs

**Neutral Colors**
- Backgrounds: White (`#ffffff`), Gray-50 (`#f9fafb`), Gray-100 (`#f3f4f6`)
- Text: Gray-900 (`#171717`), Gray-600 (`#4b5563`), Gray-400 (`#9ca3af`)

**Dark Mode**
- Background: `#0a0a0a`
- Foreground: `#ededed`
- Surfaces: Gray-950, Gray-900, Gray-800

See [DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md#color-palette) for the complete color palette with hex codes.

#### Typography

**Font Families**
- **Primary**: Geist Sans - Clean, modern sans-serif for UI text
- **Monospace**: Geist Mono - Code blocks and JSON display

**Font Scale**
- Headings: `text-3xl` (Hero), `text-2xl` (Page titles), `text-xl` (Sections)
- Body: `text-sm` (Default), `text-xs` (Labels)
- Weights: `font-extrabold` (Logo), `font-bold` (Headings), `font-semibold` (Buttons)

#### Spacing & Layout

- **Spacing Scale**: 4px base unit (Tailwind default)
- **Border Radius**: `rounded-xl` (buttons), `rounded-2xl` (cards), `rounded-lg` (containers)
- **Shadows**: `shadow-md` (buttons), `shadow-xl` (cards)

#### Component Patterns

**Buttons**
```tsx
// Primary Red Button
<button className="bg-red-700 text-white font-bold px-8 py-3 rounded-xl 
                   hover:bg-red-800 transition active:scale-[0.98]">
  Upload File
</button>

// Primary Blue Button
<button className="bg-blue-600 text-white font-semibold py-2.5 rounded-xl 
                   shadow-md hover:bg-blue-500 disabled:opacity-50">
  Generate
</button>
```

**Cards**
```tsx
<div className="rounded-2xl bg-gray-800/60 p-5 shadow-xl ring-1 ring-white/5">
  {/* Content */}
</div>
```

**Navigation**
```tsx
// Active navigation item
<a className="px-4 py-2 rounded font-semibold text-sm bg-white text-red-700">

// Inactive navigation item  
<a className="px-4 py-2 rounded font-semibold text-sm text-white hover:bg-red-600">
```

For detailed component patterns, responsive design guidelines, and accessibility best practices, refer to **[DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md)**.

### CSS Architecture

- **Approach**: Utility-first with Tailwind CSS
- **Customization**: CSS variables in `globals.css` for theming
- **Components**: Inline Tailwind classes for component styling
- **No custom CSS**: Avoid writing custom CSS files; use Tailwind utilities

```css
/* globals.css - CSS Variables */
:root {
  --background: #ffffff;
  --foreground: #171717;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}
```

### Responsive Design

Mobile-first approach using Tailwind breakpoints:
- **Mobile**: < 640px (default)
- **Tablet**: 640px+ (`sm:`)
- **Desktop**: 1024px+ (`lg:`)

```tsx
<div className="px-4 lg:px-8">              {/* Responsive padding */}
<div className="grid-cols-1 lg:grid-cols-2"> {/* Responsive grid */}
```

---


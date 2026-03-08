# EQUITEK Frontend

This is the frontend application for EQUITEK Excel Generator, built with Next.js 16 and React 19. The application provides an AI-driven interface for automating data structuring and Excel template mapping.

## Table of Contents
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Design System](#design-system)
- [Testing](#testing)
- [Development Guidelines](#development-guidelines)

---

## Tech Stack

- **Framework**: [Next.js](https://nextjs.org) 16.1.6 (App Router)
- **UI Library**: React 19.2.4
- **Styling**: [Tailwind CSS](https://tailwindcss.com) v4
- **Language**: TypeScript 5
- **Testing**: Vitest with React Testing Library
- **Fonts**: Geist Sans & Geist Mono
- **Code Quality**: ESLint with Next.js config

---

## Getting Started

### Prerequisites
- Node.js 18+ or 20+
- npm, yarn, pnpm, or bun

### Installation

```bash
npm install
```

### Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
npm run build
npm start
```

### Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage
```

### Linting

```bash
npm run lint
```

---

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── globals.css         # Global styles & Tailwind imports
│   │   ├── layout.tsx          # Root layout with font configuration
│   │   ├── page.tsx            # Homepage
│   │   └── convert/            # Convert page route
│   ├── components/             # Reusable React components
│   │   ├── LLMClient.tsx       # LLM JSON generator interface
│   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   └── UploadZone.tsx      # File upload component
│   ├── hooks/                  # Custom React hooks
│   │   └── useLLMGenerator.ts  # LLM generation logic
│   ├── lib/                    # Utilities and interfaces
│   │   ├── api.ts              # API helper functions
│   │   └── ILLMService.ts      # LLM service interface
│   ├── services/               # API service layers
│   │   ├── llm.ts              # LLM service
│   │   ├── health.ts           # Health check service
│   │   └── ...                 # Other services
│   ├── constants/              # Application constants
│   └── utils/                  # Utility functions
├── tests/                      # Test files (mirrors src/ structure)
│   ├── setup.ts                # Test setup configuration
│   └── mocks/                  # MSW mock handlers
├── public/                     # Static assets
├── DESIGN_GUIDELINES.md        # Comprehensive design system documentation
└── package.json
```

---

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

## Testing

### Test Structure
- Tests mirror the `src/` directory structure
- Component tests use React Testing Library
- API mocking with MSW (Mock Service Worker)

### Running Tests

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage
```

Coverage reports are generated in `coverage/` directory.

---

## Development Guidelines

### Code Style

1. **TypeScript**: Use TypeScript for all files
2. **Functional Components**: Prefer function components with hooks
3. **Props**: Use `readonly` interface properties
4. **Naming**: PascalCase for components, camelCase for functions/variables

```tsx
interface ComponentProps {
    readonly title: string
    readonly onSubmit?: () => void
}

export default function Component({ title, onSubmit }: ComponentProps) {
    // Component logic
}
```

### Styling Guidelines

1. **Use Tailwind utilities** - Avoid custom CSS
2. **Follow design system** - Reference DESIGN_GUIDELINES.md
3. **Maintain consistency** - Use established color palette and spacing
4. **Responsive design** - Mobile-first approach

### Component Organization

```tsx
'use client' // If using client-side features

import { useState } from 'react'
import Component from '@/components/Component'

// Types/Interfaces
interface Props { }

// Component
export default function MyComponent({ }: Props) {
    // Hooks
    const [state, setState] = useState()
    
    // Handlers
    const handleClick = () => { }
    
    // Render
    return <div>...</div>
}
```

### Accessibility

- Use semantic HTML elements
- Add `aria-label` for interactive elements without visible labels
- Include `role` attributes for dynamic content
- Maintain keyboard navigation support
- Ensure focus states are visible: `focus:ring-2 focus:ring-blue-500`

---

## Additional Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [React Testing Library](https://testing-library.com/react)
- [Vitest Documentation](https://vitest.dev/)
- [DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md) - Complete design system reference

---

## Contributing

1. Follow the design guidelines in [DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md)
2. Write tests for new features
3. Ensure all tests pass before committing
4. Run linting: `npm run lint`
5. Maintain TypeScript strict mode compliance

---

**Project**: EQUITEK Excel Generator  
**Frontend Version**: 0.1.0  
**Last Updated**: March 2026

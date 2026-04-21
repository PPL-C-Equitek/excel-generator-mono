---
name: equitek-frontend-design-guidelines
description: Apply EQUITEK frontend design system (colors, typography, spacing, Tailwind patterns, and accessibility) when creating or modifying UI in frontend/. Use this for page/component styling requests so outputs stay consistent with project guidelines.
---

# EQUITEK Frontend Design Guidelines Skill

Use this skill whenever generating or editing UI in `frontend/`.

## Source of truth
- Follow the design system copied from `frontend/README.md` in `REFERENCE_FRONTEND_README_DESIGN.md`.
- For complete token/pattern detail, use `DESIGN_GUIDELINES.md`.
- For quick Tailwind snippets, use `DESIGN_QUICK_REFERENCE.md`.

## Core rules
- Keep EQUITEK brand color discipline:
  - Primary brand: `red-700` (`#b91c1c`)
  - Interactive accent: `blue-600` (`#2563eb`)
- Use Geist fonts consistently (`Geist Sans`, `Geist Mono`).
- Maintain spacing/radius/shadow consistency:
  - spacing base 4px
  - `rounded-xl` / `rounded-2xl` / `rounded-lg`
  - `shadow-md` / `shadow-xl`
- Follow existing component patterns for button, card, nav, input, upload zone, alert.
- Prefer Tailwind utility classes over new custom CSS.
- Keep responsive behavior mobile-first (`sm:`, `lg:`).
- Always include interactive and accessibility states (`hover`, `focus:ring`, `disabled`, semantic roles/labels).
- Error handling UI must be consistent:
  - do not use browser/system popup errors (`window.alert`, `window.confirm`, `window.prompt`) for failure states
  - show errors with UI components (inline alert, form error text, banner, or toast) using project error styles (`border-red-400`, `bg-red-50`, `text-red-700`)
  - for form validation, prefer field-level messages close to the related input plus an optional summary alert

## References
- `REFERENCE_FRONTEND_README_DESIGN.md`
- `DESIGN_GUIDELINES.md`
- `DESIGN_QUICK_REFERENCE.md`

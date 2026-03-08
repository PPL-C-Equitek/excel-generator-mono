# Design Quick Reference

Quick reference guide for EQUITEK design system. For complete documentation, see [DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md).

---

## Colors Quick Reference

### Brand
```tsx
bg-red-700          // Primary brand (#b91c1c)
bg-red-600          // Hover state (#dc2626)
bg-red-800          // Active/pressed (#991b1b)
bg-blue-600         // Interactive (#2563eb)
bg-blue-500         // Interactive hover (#3b82f6)
```

### Backgrounds
```tsx
bg-white            // Main background (#ffffff)
bg-gray-50          // Surface light (#f9fafb)
bg-gray-100         // Input backgrounds (#f3f4f6)
bg-gray-900         // Dark backgrounds (#111827)
bg-gray-950         // Darkest (#030712)
```

### Text
```tsx
text-gray-900       // Primary text (#171717)
text-gray-600       // Secondary text (#4b5563)
text-gray-400       // Placeholder (#9ca3af)
text-white          // White text
```

### Borders
```tsx
border-gray-300     // Default border (#d1d5db)
border-red-400      // Error border (#f87171)
```

---

## Typography Quick Reference

### Sizes
```tsx
text-xs             // 12px - Labels, captions
text-sm             // 14px - Body text
text-xl             // 20px - Section headings
text-2xl            // 24px - Page titles
text-3xl            // 30px - Hero headings
```

### Weights
```tsx
font-semibold       // 600 - Buttons, nav items
font-bold           // 700 - Headings
font-extrabold      // 800 - Logo
```

### Utilities
```tsx
tracking-tight      // Headings
tracking-widest     // Logo, labels
uppercase           // Labels
```

---

## Spacing Quick Reference

```tsx
gap-1               // 4px
gap-2               // 8px
gap-3               // 12px
gap-6               // 24px

px-4 py-2           // Button padding
px-6 py-5           // Card padding
p-3                 // Alert padding
p-5                 // Component padding
```

---

## Component Snippets

### Button - Primary Red
```tsx
<button className="bg-red-700 text-white font-bold px-8 py-3 rounded-xl 
                   hover:bg-red-800 transition active:scale-[0.98]">
  Click Me
</button>
```

### Button - Primary Blue
```tsx
<button className="bg-blue-600 text-white font-semibold py-2.5 px-4 rounded-xl 
                   shadow-md hover:bg-blue-500 disabled:opacity-50">
  Submit
</button>
```

### Button - Secondary
```tsx
<button className="px-4 py-2 rounded font-semibold text-sm text-white 
                   bg-red-600 hover:bg-red-700 transition">
  Action
</button>
```

### Card - Light
```tsx
<div className="rounded-2xl bg-white p-5 shadow-xl">
  {/* Content */}
</div>
```

### Card - Dark
```tsx
<div className="rounded-2xl bg-gray-800/60 p-5 shadow-xl ring-1 ring-white/5">
  {/* Content */}
</div>
```

### Input - Text
```tsx
<input className="w-full px-4 py-2 rounded-xl bg-gray-100 border border-gray-300 
                  outline-none focus:ring-2 focus:ring-blue-500" />
```

### Input - Textarea
```tsx
<textarea className="w-full resize-none rounded-xl bg-gray-100 p-4 
                     border border-gray-300 outline-none 
                     focus:ring-2 focus:ring-blue-500" />
```

### Alert - Error
```tsx
<div className="flex items-start gap-2 rounded-lg border border-red-400 
                bg-red-50 p-3 text-sm text-red-700" role="alert">
  <span className="text-red-500">⚠</span>
  <span>Error message here</span>
</div>
```

### Navigation Item - Active
```tsx
<a className="px-4 py-2 rounded font-semibold text-sm bg-white text-red-700">
  Active
</a>
```

### Navigation Item - Inactive
```tsx
<a className="px-4 py-2 rounded font-semibold text-sm text-white 
              hover:bg-red-600 transition">
  Inactive
</a>
```

### Upload Zone
```tsx
<label className="border-2 border-dashed rounded-lg p-20 
                  flex flex-col items-center justify-center gap-3 
                  border-gray-300 bg-gray-100 hover:border-red-600 
                  hover:bg-red-50 transition-colors cursor-pointer">
  <input type="file" className="hidden" />
  <span className="bg-red-700 text-white font-bold px-8 py-3 rounded-xl">
    Upload File
  </span>
  <p className="text-gray-400 text-sm">Or drop file here</p>
</label>
```

### Skeleton Loader
```tsx
<div className="animate-pulse space-y-3 pt-2">
  <div className="h-4 w-full rounded bg-gray-600" />
  <div className="h-4 w-5/6 rounded bg-gray-600" />
  <div className="h-4 w-4/6 rounded bg-gray-600" />
</div>
```

---

## Layout Patterns

### Page Layout with Sidebar
```tsx
<div className="flex min-h-screen">
  <Sidebar activeMenu="convert" username="User" />
  <main className="flex-1 bg-gray-50 px-16">
    {/* Content */}
  </main>
</div>
```

### Centered Container
```tsx
<div className="mx-auto max-w-5xl px-4 lg:px-8">
  {/* Content */}
</div>
```

### Two-Column Grid
```tsx
<div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
  <div>{/* Column 1 */}</div>
  <div>{/* Column 2 */}</div>
</div>
```

---

## Responsive Utilities

```tsx
px-4 lg:px-8                    // Responsive padding
grid-cols-1 lg:grid-cols-2      // Responsive grid
hidden lg:block                 // Show on desktop only
block lg:hidden                 // Show on mobile only
```

---

## Animation & Transition

```tsx
transition                      // All properties, 150ms
transition-all duration-150     // Explicit all
transition-colors               // Colors only
hover:bg-red-800               // Hover state
active:scale-[0.98]            // Click feedback
disabled:opacity-50            // Disabled state
animate-pulse                  // Loading animation
```

---

## Accessibility

```tsx
// Focus states
focus:ring-2 focus:ring-blue-500
focus:outline-none

// ARIA attributes
aria-label="Description"
role="alert"

// Keyboard navigation
disabled={isLoading}
tabIndex={0}
```

---

## Common Patterns

### Loading State
```tsx
{loading ? (
  <div className="animate-pulse">Loading...</div>
) : (
  <div>Content</div>
)}
```

### Error State
```tsx
{error && (
  <div className="rounded-lg border border-red-400 bg-red-50 p-3 text-red-700">
    {error}
  </div>
)}
```

### Conditional Styling
```tsx
<div className={`px-4 py-2 ${isActive ? 'bg-white text-red-700' : 'text-white'}`}>
  Item
</div>
```

---

## Do's and Don'ts

### ✅ DO
- Use Tailwind utility classes
- Follow the established color palette
- Maintain consistent spacing (multiples of 4px)
- Add focus states to interactive elements
- Use semantic HTML
- Keep components responsive

### ❌ DON'T
- Write custom CSS files
- Use arbitrary hex codes (use Tailwind colors)
- Mix different border radius sizes randomly
- Forget accessibility attributes
- Use inline styles
- Skip responsive design

---

For complete guidelines including color hex codes, comprehensive examples, and best practices, see **[DESIGN_GUIDELINES.md](./DESIGN_GUIDELINES.md)**.

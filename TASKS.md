# Tasks

## BUG-1: Desktop Layout Issues
**Priority:** High
**Status:** ✅ Done

### Problems:
- ✅ Weekly plan shows 6 days instead of 7
- ✅ Recipe card not fully displayed (truncated/cut off)
- ✅ Day header not aligned correctly
- ✅ Calories display looks odd (formatting)
- ✅ Shopping list appears huge (font/spacing too large)
- ✅ Too many decimal places throughout (max should be 2-3)
- ✅ Recipe search bar is invisible/easy to miss — users don't see it
- ✅ Sort-by dropdown is too wide/large on desktop
- ✅ Mobile layout untouched

---

## BUG-2: Shopping List — Ingredients Not Combined
**Priority:** High
**Status:** ✅ Done

Ingredients from different meals that are the same item are not being
combined into a single line. E.g., multiple recipes each needing "garlic"
should result in one combined "garlic" line with total quantity.

---

## BUG-3: Shopping List — Spurious "serving" Unit
**Priority:** Medium
**Status:** ✅ Done

Items with no unit are showing as "0.6875 serving tomato" instead of
"0.6875 tomato". The word "serving" should not appear; if no unit is
present the item should just show quantity + item name.

---

## FEAT-1: Add Recipe to Meal Plan from Recipe Detail Page
**Priority:** High

From the recipe detail page, the user should be able to directly add
that recipe to a specific day/meal-type in the current week's plan
without leaving the page. Should use a simple dropdown or modal.

---

## FEAT-2: Respect Daily Calorie Limit When Generating Plan
**Priority:** High
**Status:** ✅ Done

The meal plan generator currently ignores the configured daily calorie
limit. When generating a plan it should:
- ✅ Aim for plans where daily calories stay within the configured limit
- ✅ Prefer lower-calorie recipes when the day is near the limit
- ✅ Falls back to lowest-calorie if no recipe fits (never leaves slot empty)

---

## FEAT-3: Simpler Meal Slot Assignment in Weekly Plan
**Priority:** High

Currently adding a recipe to a meal slot asks the user to type a recipe
ID, which is not usable for regular users. Replace this with a proper
recipe picker: searchable list / autocomplete, or a scrollable modal
showing recipe cards, filtered by meal type.

---

## DESIGN-1: Navigation & Discoverability Rethink
**Priority:** High
**Status:** Ready to implement

### Confirmed Decisions:
- **Navigation:** Sidebar on desktop, bottom tab bar on mobile
- **Add Recipe:** FAB (floating action button) that expands to Import / Create / Scan
- **Settings:** Dedicated `/settings` page containing ALL app settings (schedule, calorie
  limit, portions, nutrition goals, theme, etc.)
- **Page structure:** Single scrolling page with sticky section headers; sidebar/tabs
  scroll to the relevant section
- **Meal editing:** Edit icon on meal card → searchable recipe picker modal

### Implementation Plan:

#### 1. App Shell Restructure
- Add a persistent left sidebar on desktop (≥1024px):
  - App logo + name
  - Nav links: Plan / Recipes / Shopping List / Settings
  - Each link scrolls to / shows that section
  - Collapsed icon-only mode at medium widths (768–1023px)
- Add a bottom tab bar on mobile (<768px):
  - Tabs: Plan / Recipes / Shopping / Settings
  - Replaces current header-only navigation
  - Active tab highlighted

#### 2. FAB for Recipe Actions
- Floating "+" button fixed bottom-right (above bottom tab bar on mobile)
- On click, expands into three options:
  - 📷 Import from Photo
  - 🔗 Import from URL
  - ✏️ Create Manually
- Replaces the current import buttons in the hero and section header

#### 3. Settings Page / Section
- New `/settings` route (or anchored section in the single page)
- Sections:
  - **Meal Schedule** (moved from current modal)
  - **Household** (portions, calorie limit)
  - **Nutrition Goals** (protein, carbs, fat targets)
  - **App Preferences** (placeholder for future theme, language, etc.)

#### 4. Recipe Picker Modal (for meal slot editing)
- Replaces the current text-prompt recipe ID input
- Triggered by edit icon on any meal card
- Shows searchable, scrollable list of recipe cards filtered by meal type
- Select a recipe → confirm → updates the slot

#### 5. Remove / Relocate Redundant Controls
- Remove "Configure Schedule" from the plan header — lives in Settings now
- Remove import buttons from the hero — FAB covers this
- Clean up the top header to just logo + (future) user avatar

---

## FEAT-4: Ingredient-Based Search
**Priority:** High

Extend the existing `/api/recipes` search to also match against ingredient
names (e.g. searching "chicken" returns recipes that contain chicken as an
ingredient, not just recipes named "chicken something").

- Backend only — no frontend changes needed
- Extend search logic to query `recipe.ingredients[].item` in addition to recipe name
- TDD: add tests for ingredient search before implementing

---

## FEAT-5: Servings Scaling on Recipe Detail Page
**Priority:** High

On the recipe detail page, let the user change the serving count and see
all ingredient quantities update instantly.

- Frontend only — pure JavaScript, no backend changes
- Add a serving size input/stepper next to the servings count
- All ingredient quantities re-scale in real time relative to the original serving count
- Original quantities preserved so the user can reset

---

## FEAT-6: Recipe Editing from Detail Page
**Priority:** High

Currently recipes can only be edited via the API. Add an inline edit mode
to the recipe detail page so users can update recipe fields without leaving
the page.

- Edit button toggles the page into edit mode
- Editable fields: name, servings, prep/cook time, tags, ingredients, instructions, image URL
- Save calls the existing PUT /api/recipes/<id> endpoint
- Cancel restores the original values
- Show a success/error toast after saving

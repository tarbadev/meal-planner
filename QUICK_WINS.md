# Quick Win Features

**Criteria:** Backend-heavy features that add major user value with MINIMAL frontend work (just buttons, badges, or simple displays).

Focus: Features where Flutter will reuse the backend logic but rebuild the UI anyway.

---

## Tier 1: Minimal Frontend, High Value ⭐

### 1. **Recipe Difficulty Auto-Calculation** 🌶️
**Backend:** (2 hours)
- Auto-calculate difficulty on recipe import/create
- Based on: ingredient count, steps, cook time, techniques
- Store as `difficulty: "easy" | "medium" | "hard"`
- Add to existing API: `/api/recipes?difficulty=easy`

**Frontend:** (15 minutes)
- Show 🌶️ / 🌶️🌶️ / 🌶️🌶️🌶️ badge on recipe cards
- Add "Difficulty" filter button (already have filter UI)

**Value:** Users can find recipes matching their skill level

**Why Quick:** All logic in backend, just display a badge

---

### 2. **Ingredient-Based Search** 🔍
**Backend:** (1 hour)
- Extend existing search logic to query ingredients list
- Search through `recipe.ingredients[].item` field
- Already have structured ingredient data

**Frontend:** (0 minutes)
- No changes needed! Use existing search bar
- Backend just returns more results

**Value:** "What can I make with chicken?" searches work

**Why Quick:** Backend extension, zero frontend work

---

### 3. **Recipe View Count & Popularity** 📊
**Backend:** (2 hours)
- Add `view_count: int` field to recipes (default 0)
- `POST /api/recipes/{id}/view` endpoint (increment counter)
- Add `sort=popular` to existing API
- Auto-call on recipe detail page load

**Frontend:** (15 minutes)
- Show "🔥 123 views" on recipe cards
- Add "Popular" to sort dropdown (already exists)

**Value:** Discover most-used recipes

**Why Quick:** Backend counting, just show a number

---

### 4. **Export Meal Plan to PDF** 📄
**Backend:** (3 hours)
- Use ReportLab/WeasyPrint to generate PDF
- Same data as Google Sheets export
- Endpoint: `GET /export/meal-plan.pdf`

**Frontend:** (5 minutes)
- Add "Download PDF" button next to "Export to Sheets"
- `<a href="/export/meal-plan.pdf" download>`

**Value:** Printable meal plans for kitchen

**Why Quick:** All work in backend, just a download link

---

### 5. **Nutrition Goal Tracking** 🎯
**Backend:** (2 hours)
- Add goals to config: `PROTEIN_GOAL`, `CARBS_GOAL`, `FAT_GOAL`
- Calculate "% of goal" for current plan
- Return in `/current-plan` response

**Frontend:** (30 minutes)
- Add progress bars under existing stats
- `<progress value="120" max="150">120/150g protein</progress>`
- Color coding with CSS

**Value:** Track macro goals visually

**Why Quick:** Backend calculation, simple progress bars

---

### 6. **Multi-Week Planning** 📅
**Backend:** (4 hours)
- Generate N weeks of plans
- Store as `current_plans: list[WeeklyPlan]`
- Endpoints: `POST /generate-plan?weeks=2`, `GET /plan/week/{n}`

**Frontend:** (20 minutes)
- Add week selector: `<select>Week 1, Week 2...</select>`
- Load different week on change
- Reuse existing calendar display

**Value:** Plan ahead for busy weeks

**Why Quick:** Backend generates, just pagination UI

---

### 7. **Recipe Rating (Auto from Views)** ⭐
**Backend:** (1 hour)
- Calculate rating from views + user feedback
- Add `rating: float` (1.0-5.0) field
- Update on each view (weighted average)
- Add to API: `sort=rating_desc`

**Frontend:** (10 minutes)
- Show ⭐⭐⭐⭐⭐ on recipe cards
- Add "Top Rated" to sort dropdown

**Value:** Surface best recipes

**Why Quick:** Backend calculation, just show stars

---

## Tier 2: Moderate Backend, Minimal Frontend

### 8. **Skip Days in Meal Schedule** ⏭️
**Backend:** (2 hours)
- Add `SKIPPED_DAYS: list[str]` to config
- Filter out skipped days in plan generation
- Respect in nutrition calculations

**Frontend:** (15 minutes)
- Add checkboxes to schedule config modal
- Existing modal, just add checkbox per day

**Value:** Don't plan for eating out days

**Why Quick:** Backend filtering, just checkboxes

---

### 9. **Shopping List Price Tracking** 💰
**Backend:** (3 hours)
- Add `estimated_price: float` per ingredient
- Sum for total shopping list cost
- Track historical prices
- Endpoint: `GET /shopping-list?with_prices=true`

**Frontend:** (10 minutes)
- Show "Est. total: $45" at bottom of shopping list
- Price per item (optional)

**Value:** Budget tracking

**Why Quick:** Backend tracking, just display totals

---

### 10. **Batch Cooking Suggestions** 👨‍🍳
**Backend:** (4 hours)
- Analyze meal plan for common ingredients
- Suggest batch prep tasks (e.g., "Chop 3 lbs chicken")
- Group by prep technique
- Endpoint: `GET /meal-prep-schedule`

**Frontend:** (20 minutes)
- New "Meal Prep" section (collapsible)
- List of prep tasks with checkboxes

**Value:** Save cooking time

**Why Quick:** Complex backend logic, simple task list UI

---

## Tier 3: Backend Heavy, Worth the Investment

### 11. **Smart Recipe Recommendations** 🤖
**Backend:** (6 hours)
- Track which recipes are cooked together
- Suggest "If you liked X, try Y"
- Based on tags, ingredients, user history
- Endpoint: `GET /api/recipes/{id}/similar`

**Frontend:** (15 minutes)
- "Similar Recipes" section on recipe detail page
- Use existing recipe card component

**Value:** Recipe discovery

**Why Quick:** AI/ML in backend, just display cards

---

### 12. **Calendar Export (iCal)** 📆
**Backend:** (4 hours)
- Generate .ics file from meal plan
- Include prep times, cooking times
- Add reminders
- Endpoint: `GET /export/calendar.ics`

**Frontend:** (5 minutes)
- "Add to Calendar" button
- `<a href="/export/calendar.ics" download>`

**Value:** Sync with phone calendar

**Why Quick:** iCal generation in backend, just a link

---

### 13. **Recipe Substitution Suggestions Enhanced** 🔄
**Backend:** (4 hours)
- Expand beyond current simple substitutions
- Use ingredient taxonomy (oils, dairy, proteins)
- Nutrition-aware (similar macros)
- API: `GET /api/ingredients/{name}/substitutes?nutrition_match=true`

**Frontend:** (0 minutes)
- Already have substitution display!
- Just returns better suggestions

**Value:** More flexible cooking

**Why Quick:** Enhanced backend, existing UI

---

### 14. **Leftover Management** 🥡
**Backend:** (5 hours)
- Track "cooked portions" vs "consumed portions"
- Auto-suggest leftover recipes
- Endpoint: `POST /meals/{id}/leftovers`, `GET /recipes?uses_leftovers=true`

**Frontend:** (20 minutes)
- "Mark as leftover" button after cooking
- Badge showing leftover meals in fridge

**Value:** Reduce food waste

**Why Quick:** Complex tracking in backend, simple buttons

---

### 15. **Grocery Delivery Integration** 🛒
**Backend:** (8 hours)
- Generate Instacart/Amazon Fresh cart URLs
- Map ingredients to store products
- Endpoint: `GET /shopping-list/export/instacart`

**Frontend:** (10 minutes)
- "Order on Instacart" button
- Opens pre-filled cart in new tab

**Value:** One-click grocery ordering

**Why Quick:** Complex API integration, just a button

---

## Quick Wins Summary

**Top 5 Fastest Wins (Frontend < 30 min each):**
1. Ingredient-based search (0 min frontend)
2. Recipe view count/popularity (15 min)
3. Export PDF (5 min)
4. Recipe rating (10 min)
5. Recipe difficulty (15 min)

**Best Value/Effort Ratio:**
1. Ingredient search (huge value, 1 hr total)
2. Difficulty calculation (great UX, 2.5 hrs total)
3. Multi-week planning (high value, 4.5 hrs total)
4. Nutrition goals (motivating, 2.5 hrs total)
5. PDF export (printable, 3 hrs total)

---

## Why These Are "Quick Wins"

✅ **Backend does heavy lifting** - Logic reusable in Flutter
✅ **Minimal HTML/CSS/JS** - Just buttons, badges, displays
✅ **High user value** - Solve real problems
✅ **Not throwaway** - Flutter will call same APIs
✅ **Build on existing** - Extend current patterns

**Avoid:**
- Features needing custom UI components
- Complex forms or modals
- Heavy JavaScript interactions
- Features that duplicate future Flutter work

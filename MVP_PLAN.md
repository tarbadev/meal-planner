# Meal Planner MVP - Ready for Next Friday

## Goal

Have a working mobile-friendly app by next Friday that you can use to:
1. **Plan meals** for the week
2. **Generate shopping list** from selected recipes
3. **Check off items** while grocery shopping
4. **View recipes** on your phone while cooking

## Simplified Architecture

### Keep It Simple
- **No Flutter** (yet) - Just make the current Flask app mobile-responsive
- **No PostgreSQL** (yet) - Stick with recipes.json or add SQLite if needed
- **No complex auth** - Single user (you) for now
- **No background workers** - Synchronous is fine for MVP

### What We Already Have ✅
- Recipe import from URL
- Recipe detail view with ingredients and instructions
- Automatic nutrition generation
- Tag inference
- Source URL tracking

### What We Need to Build 🛠️
1. **Mobile-responsive UI** - Make current templates work well on phone
2. **Meal planner** - Simple weekly calendar to select recipes
3. **Shopping list** - Generate from selected recipes, allow checking off items
4. **Mobile-optimized recipe view** - Large text, easy to read while cooking

## Implementation Plan

### Day 1-2: Mobile-Responsive UI (2-3 hours)
**Files to modify:**
- `app/templates/base.html` - Add viewport meta tag, mobile CSS
- `app/templates/index.html` - Responsive recipe cards
- `app/templates/recipe_detail.html` - Large, readable text for cooking
- Create `app/static/css/mobile.css` - Mobile-specific styles

**Key features:**
- Responsive grid layout for recipe cards
- Bottom navigation for mobile (Recipes / Meal Plan / Shopping List)
- Large tap targets (min 44x44px)
- Readable font sizes (16px+ body text)
- Dark mode for cooking in dim light

### Day 3-4: Meal Planner (3-4 hours)
**New files:**
- `app/meal_plan.py` - Simple meal plan data structure
- `app/templates/meal_plan.html` - Weekly calendar view

**Data structure:**
```python
# meal_plans.json
{
  "daily_calorie_limit": 2000,  # Default cap, user can adjust
  "2024-02-12": {  # Monday
    "lunch": {"recipe_id": "chicken-pasta", "servings": 4},
    "dinner": {"recipe_id": "beef-stew", "servings": 6}
  },
  "2024-02-13": {  # Tuesday
    "lunch": {"recipe_id": "leftover-beef-stew", "servings": 2},
    "dinner": {"recipe_id": "salmon-rice", "servings": 4}
  }
}
```

**Features:**
- Simple 7-day view (Monday-Sunday)
- Click day to add recipe (modal with recipe list)
- Edit servings per meal
- Remove meals
- Clear "This Week" button
- **Daily calorie limit** - Set target calories per day
- **Daily nutrition totals** - Show calories/protein/carbs/fat per day
- **Visual indicator** - Warn when exceeding daily calorie limit

### Day 5-6: Shopping List (3-4 hours)
**New files:**
- `app/shopping_list.py` - Shopping list generator
- `app/templates/shopping_list.html` - Checklist view

**Logic:**
```python
def generate_shopping_list(meal_plan):
    """
    1. Get all ingredients from recipes in meal plan
    2. Scale quantities by servings
    3. Consolidate duplicate ingredients
    4. Group by category (produce, dairy, meat, pantry, spices)
    5. Sort within categories
    """
```

**UI Features:**
- Grouped by category with collapsible sections
- Large checkboxes (easy to tap with wet hands)
- Strike-through checked items
- "Add custom item" button
- "Uncheck all" for next week
- Save state to localStorage for offline use

### Day 7: Testing & Polish (2 hours)
- Test on actual phone while cooking a recipe
- Test in grocery store (bring phone)
- Fix any UX issues
- Add loading states
- Improve error messages

## Simplified Tech Stack

### Frontend
- **HTML/CSS/JavaScript** - No framework needed yet
- **Bootstrap 5** or **Tailwind CSS** - For responsive components
- **localStorage** - For shopping list state (offline support)
- **PWA manifest** - Allow "Add to Home Screen" on phone

### Backend
- **Flask** - Keep current setup
- **JSON files** - recipes.json, meal_plans.json, shopping_list.json
- **SQLite** (optional) - If JSON becomes cumbersome

### Deployment
- **Current setup** - Whatever you're using now
- **Railway** - Recommended for free tier with custom domain and no auto-sleep.
- **HTTPS required** - For PWA features and camera access

## Feature Priorities

### Must-Have for Friday ✅
1. Mobile-responsive recipe list
2. Mobile-responsive recipe detail (cooking mode)
3. Weekly meal planner (drag or click to add recipes)
4. **Daily nutrition cap** - Set calorie limit, see daily totals
5. Shopping list generator
6. Shopping list with checkboxes (persistent state)

### Nice-to-Have (if time permits) 🎯
1. Serving size adjuster on recipe detail
2. "Add to meal plan" button directly from recipe detail
3. Shopping list "Smart Sort" by store layout (produce → dairy → meat → pantry)
4. Export shopping list to Notes app
5. Dark mode toggle

### Defer to Later 🚫
- Multi-user / family sharing
- Recipe editing
- Pantry tracking
- Nutrition tracking
- Social features
- Voice commands
- Offline sync (beyond localStorage)
- Push notifications

## UI Mockup (Simple)

### Bottom Navigation
```
┌─────────────────────────────────┐
│                                 │
│    [Content Area]               │
│                                 │
│                                 │
└─────────────────────────────────┘
┌─────────────────────────────────┐
│  📖 Recipes  |  📅 Plan  |  🛒 List │
└─────────────────────────────────┘
```

### Meal Plan View
```
┌─────────────────────────────────┐
│  Week of Feb 12, 2024    [←][→] │
├─────────────────────────────────┤
│  MON Feb 12                     │
│    Lunch:  [+ Add Recipe]       │
│    Dinner: Chicken Pasta (4)    │
├─────────────────────────────────┤
│  TUE Feb 13                     │
│    Lunch:  Leftover Chicken     │
│    Dinner: [+ Add Recipe]       │
├─────────────────────────────────┤
│  ...                            │
└─────────────────────────────────┘
│  [Generate Shopping List]       │
└─────────────────────────────────┘
```

### Shopping List View
```
┌─────────────────────────────────┐
│  Shopping List                  │
│  [Uncheck All] [+ Add Item]     │
├─────────────────────────────────┤
│  ▼ Produce                      │
│    ☐ Lettuce (1 head)           │
│    ☑ Tomatoes (4)               │
│    ☐ Onion (2)                  │
├─────────────────────────────────┤
│  ▼ Dairy                        │
│    ☐ Milk (1 gallon)            │
│    ☐ Cheese (8 oz)              │
├─────────────────────────────────┤
│  ▼ Meat                         │
│    ☐ Chicken breast (1.5 lbs)   │
└─────────────────────────────────┘
```

## Success Criteria

By next Friday, you should be able to:

1. ✅ **Import 3-5 recipes** for the week using your phone
2. ✅ **Add them to a meal plan** for Monday-Sunday
3. ✅ **Generate a shopping list** with all ingredients
4. ✅ **Use the shopping list** in the grocery store (check off items)
5. ✅ **View recipes while cooking** (large text, clear instructions)

## Timeline - Revised for Production Use

### ✅ Phase 1 Complete: Foundation (Days 1-3)
- ✅ Mobile-responsive UI (Commits: 995ed1c, 16831e6)
- ✅ Daily calorie tracking with limits (Commits: 69a87f1, ec857b3)
- ✅ Interactive shopping list with persistence (Commits: 53c30b4, 56a08ff)

### 🚧 Phase 2: Manual Meal Planning (Days 4-5, Mon-Tue)
**Goal**: Replace auto-generation with full manual control

**Day 4 (Monday) - Interactive Weekly Calendar**
- [ ] Weekly calendar view (7 days, configurable meal slots)
- [ ] Click day/meal slot to add recipe
- [ ] Recipe selector modal (search/filter from your recipes)
- [ ] Display meals with portions and nutrition
- [ ] Delete meals from calendar
- [ ] Real-time daily calorie totals with limit warnings

**Day 5 (Tuesday) - Editable Portions & Refinements**
- [ ] Edit servings per meal (adjust portions for specific meals)
- [ ] Recalculate nutrition when portions change
- [ ] Persist meal plan to JSON (save/load between sessions)
- [ ] "Clear Week" button to start fresh
- [ ] Mobile-optimized meal planning interface

### 🌐 Phase 3: Deployment & PWA (Day 6, Wednesday)
**Goal**: Make it accessible to family with zero setup

- [ ] Deploy to Railway (free tier)
  - One-click deployment
  - Environment variables for API keys
  - Custom domain (optional)
- [ ] Add PWA (Progressive Web App) support
  - Manifest.json for "Add to Home Screen"
  - Service worker for offline caching
  - App icon and splash screen
- [ ] Share URL with family
- [ ] Test on multiple devices

### 🧪 Phase 4: Testing & Polish (Day 7, Thursday)
**Goal**: Production-ready for Friday grocery trip

- [ ] End-to-end testing on real phone
- [ ] Family testing and feedback
- [ ] Bug fixes and UX improvements
- [ ] Performance optimization
- [ ] Final deployment

### 🎯 Launch Day (Friday)
**Use it for real!**
1. Plan meals for next week
2. Generate shopping list
3. Go grocery shopping with the app
4. Cook meals using recipe view

**Success Metrics**:
- ✅ Can plan full week in < 5 minutes
- ✅ Shopping list accurate and complete
- ✅ No showstopper bugs during shopping
- ✅ Family can access and use the app

## Progress Summary

### ✅ Completed Features (Phase 1)
1. **Mobile-responsive UI** - Recipe list and detail pages work well on phones
2. **Cooking mode** - Large, readable text for following recipes while cooking
3. **Daily calorie tracking** - Shows per-day nutrition totals with configurable calorie limit
4. **Over-limit warnings** - Visual alerts (red header + ⚠️) when daily calories exceed limit
5. **Interactive shopping list** - Checkboxes with localStorage persistence
6. **Progress tracking** - Shows checked/total items count while shopping
7. **Mobile-optimized shopping** - Large touch targets, clear text for use in grocery store

### 🚧 In Progress (Phase 2)
**Manual Meal Planning** - Full control over your weekly meal plan:
- Interactive weekly calendar view
- Add/remove meals to specific days and meal slots
- Edit portions per meal (not just global household portions)
- Real-time nutrition totals per day
- Persistent meal plans (save/load between sessions)

### 📋 Next Up (Phase 3-4)
- Cloud deployment (Railway/Render)
- PWA support for phone "installation"
- Family sharing via URL
- Production testing and polish

## Architecture Decision: Flask + PWA First, Then Flutter

### Why NOT Flutter in 4 Days?
**Flutter + FastAPI migration would require**:
- Set up entire Flutter project from scratch
- Set up FastAPI backend from scratch
- Port all Python logic to new backend
- Build complete mobile UI in Flutter
- Handle deployment and testing
- **High risk of missing Friday deadline**

### Why Flask is NOT Throwaway Code
**All business logic is reusable**:
- ✅ Recipe parsing (Schema.org, WPRM, HTML patterns) → Direct port to FastAPI
- ✅ Nutrition generation (USDA API integration) → Same Python code
- ✅ Tag inference → Same logic
- ✅ Meal planning algorithms → Same algorithms
- ✅ Shopping list generation → Same logic
- ✅ Only the web UI templates get replaced → Flutter rebuilds UI from scratch anyway

**The Flask → FastAPI → Flutter path**:
1. **This week**: Flask with manual planning + PWA deployment (working app by Friday)
2. **Next sprint**: Port Flask routes to FastAPI (1-2 days, mostly copy-paste)
3. **Future sprint**: Build Flutter app with offline support (2-3 weeks)

### PWA vs Native App (Short Term)
**Flask + PWA gives you**:
- ✅ "Install" on phone (home screen icon)
- ✅ Offline caching (cached pages work without internet)
- ✅ Works on iOS and Android
- ✅ Zero app store submission process
- ✅ Instant updates (just refresh)
- ✅ Family shares via URL
- ❌ Not true offline-first (needs internet for first load)
- ❌ No background sync while offline

**This is sufficient for MVP testing**. After Friday, if offline-first is critical, we migrate to Flutter.

## Post-Friday Migration Plan

### After Successful Friday Test
1. **Week 2**: Evaluate what worked/what needs improvement
2. **Week 3-4**: Port to FastAPI + PostgreSQL
   - Multi-user authentication
   - Shared family meal plans
   - Better data persistence
3. **Month 2**: Build Flutter mobile app
   - True offline-first with Drift SQLite
   - Background sync
   - Native mobile UX
   - App store distribution

### The Pragmatic Path
- **Don't build the perfect solution in 4 days**
- **Build the working solution, then iterate**
- **Learn from real usage before committing to full architecture**

## Key Simplifications from Original Plan

### What We're NOT Building (Yet)
- ❌ Flutter mobile app → Use responsive web app
- ❌ FastAPI backend → Keep Flask
- ❌ PostgreSQL → Keep JSON files
- ❌ Multi-user auth → Single user for now
- ❌ Family sharing → Just you
- ❌ Offline sync → localStorage only
- ❌ Background workers → Synchronous operations
- ❌ Recipe search → Browse list is fine
- ❌ Advanced meal planning AI → Manual selection
- ❌ Pantry management → Not needed for MVP
- ❌ Social features → Not needed for MVP

### Why This Approach Is Better
1. **Fast to build** - Can finish in a week
2. **Easy to test** - Use it for real next Friday
3. **Low risk** - No infrastructure changes
4. **Validates concept** - Learn what you actually need
5. **Progressive enhancement** - Can add features later if useful

### If It Works Well
After using it for 2-4 weeks, we can decide:
- Keep it simple and just add polish?
- Migrate to Flutter for better mobile app experience?
- Add multi-user support for family?
- Scale up architecture?

### If It Doesn't Work
No problem! We learned quickly and cheaply. Can pivot or abandon without wasting weeks building the wrong thing.

---

**Next step**: Should I start implementing the mobile-responsive UI and meal planner, or do you want to adjust the plan further?

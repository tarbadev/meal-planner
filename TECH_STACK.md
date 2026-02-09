# Tech Stack & System Design

## Recommended Tech Stack

### Frontend

#### Mobile App: Flutter
**Pros:**
- Single codebase for iOS and Android
- Excellent performance (compiled to native code)
- Rich widget ecosystem
- Great offline support with local databases
- Strong developer experience
- Hot reload for rapid development
- Good community and package ecosystem

**Key Packages:**
- `flutter_bloc` / `riverpod` - State management
- `drift` (formerly Moor) - Local SQLite database with type-safe queries
- `dio` - HTTP client with interceptors
- `cached_network_image` - Image caching
- `shared_preferences` - Simple key-value storage
- `firebase_messaging` - Push notifications
- `camera` - Photo capture for recipe import
- `share_plus` - Share functionality
- `url_launcher` - Deep linking

#### Web App: Flutter Web or React
**Option 1: Flutter Web (Recommended for consistency)**
- Share codebase with mobile
- Consistent UI/UX across platforms
- Single team skillset

**Option 2: React + TypeScript**
- Better SEO (if needed)
- More mature web ecosystem
- Easier progressive web app (PWA) features

**Recommendation:** Flutter Web for MVP, consider React if web-specific features become critical

### Backend

#### API: FastAPI (Python)
**Pros:**
- Excellent performance (comparable to Node.js)
- Automatic API documentation (OpenAPI/Swagger)
- Type hints for better code quality
- Async support for high concurrency
- Easy integration with ML/AI libraries (for recipe parsing, recommendations)
- Fast development with Python ecosystem
- Built-in data validation (Pydantic)

**Alternative Considerations:**
- **Node.js + NestJS**: If team is more JavaScript-focused
- **Go + Gin/Fiber**: For maximum performance and lower costs
- **Rust + Actix**: For extreme performance, but slower development

**Recommendation:** FastAPI - Best balance of productivity, performance, and AI/ML integration

#### Database: PostgreSQL
**Pros:**
- Robust relational data model (users, recipes, plans, families)
- JSONB support for flexible recipe data
- Full-text search capabilities
- Excellent performance and scalability
- Strong consistency guarantees
- Rich ecosystem (PostGIS for future location features)
- Great migration tools (Alembic)

**Schema Design Considerations:**
- Multi-tenancy via home/family model
- Recipe versioning
- Shopping list state management
- Audit trails for changes

### Additional Services

#### Search & Analytics
**Elasticsearch or Typesense**
- Fast recipe search across millions of recipes
- Fuzzy matching for ingredients
- Autocomplete
- Faceted search (filters)

**Recommendation:** Typesense (easier to manage, lower cost)

#### Cache Layer
**Redis**
- Session management
- API response caching
- Rate limiting
- Real-time features (online users, notifications)
- Queue for background jobs

#### Object Storage
**AWS S3 / CloudFlare R2 / DigitalOcean Spaces**
- Recipe images
- User profile photos
- Imported recipe photos
- Generated PDF exports

**Recommendation:** CloudFlare R2 (S3-compatible, zero egress fees)

#### Message Queue
**Redis Queue (RQ) or Celery**
- Background recipe import jobs
- Nutrition calculation
- Meal plan generation
- Email notifications
- Image processing

#### Email Service
**SendGrid / AWS SES / Resend**
- Transactional emails (verification, password reset)
- Meal plan summaries
- Shopping list emails

**Recommendation:** Resend (modern, developer-friendly)

#### Push Notifications
**Firebase Cloud Messaging (FCM)**
- Cross-platform push notifications
- Free tier sufficient for most use cases

#### Authentication
**Option 1: Self-hosted (FastAPI + JWT)**
- Pros: Full control, no vendor lock-in, lower cost
- Cons: More code to maintain, handle security yourself

**Option 2: Supabase Auth / Firebase Auth**
- Pros: Quick setup, proven security, social login built-in
- Cons: Vendor lock-in, monthly costs

**Recommendation:** Self-hosted JWT for MVP, migrate to Supabase if needed

#### AI/ML Services
**OpenAI API (GPT-4)**
- Recipe extraction from text/images/video
- Smart meal suggestions
- Ingredient substitutions

**USDA FoodData Central API**
- Nutrition data (existing)

**Google Cloud Vision API**
- OCR for recipe photos
- Alternative to OpenAI for image processing

#### Monitoring & Observability
**Sentry**
- Error tracking and monitoring
- Performance monitoring
- Release tracking

**Grafana + Prometheus or DataDog**
- Metrics and dashboards
- Alerting
- Log aggregation

#### Infrastructure

**Container Orchestration: Kubernetes or Docker Compose**
- **Kubernetes (GKE/EKS/DigitalOcean)**: For production scale
- **Docker Compose**: For development and small-scale deployment

**CI/CD: GitHub Actions**
- Automated testing
- Automated deployments
- Docker image builds

**Hosting Options:**

1. **DigitalOcean (Recommended for MVP)**
   - Managed PostgreSQL
   - Managed Redis
   - App Platform or Kubernetes
   - Simple, predictable pricing
   - Good performance

2. **AWS**
   - Most flexible
   - Best for scale
   - More complex
   - Higher cost

3. **Google Cloud Platform**
   - Good for ML/AI integration
   - Competitive pricing
   - Cloud Run for serverless

4. **Fly.io**
   - Global edge deployment
   - Great for low latency
   - Simple deployment
   - Affordable

**Recommendation:** DigitalOcean for MVP, migrate to AWS/GCP if scaling beyond 100K users

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Clients                               │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Flutter iOS │ Flutter Android│ Flutter Web│ Mobile Browser│
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │                │
       └──────────────┴──────────────┴────────────────┘
                           │
                    [Load Balancer]
                           │
       ┌───────────────────┴───────────────────┐
       │                                       │
  [API Gateway]                          [CDN]
       │                                  (Images, Static Assets)
       │
┌──────┴─────────────────────────────────────────────────┐
│                  FastAPI Backend                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Auth    │  │  Recipe  │  │  Meal    │            │
│  │  Service │  │  Service │  │  Planner │   ...      │
│  └──────────┘  └──────────┘  └──────────┘            │
└────┬────────┬────────┬────────┬────────┬──────────────┘
     │        │        │        │        │
     │        │        │        │        └────> [Redis Cache]
     │        │        │        └────────────> [Message Queue]
     │        │        └─────────────────────> [Typesense]
     │        └──────────────────────────────> [S3/R2]
     └───────────────────────────────────────> [PostgreSQL]
                                                    │
                                            [Read Replicas]
```

### Database Schema (Simplified)

```sql
-- Users & Authentication
users (
  id, email, hashed_password, name, created_at, updated_at,
  email_verified, avatar_url, preferences_jsonb
)

user_dietary_restrictions (
  id, user_id, restriction_type, severity, notes
)

-- Multi-tenancy
homes (
  id, name, created_by, created_at, settings_jsonb
)

home_members (
  id, home_id, user_id, role, joined_at, portion_multiplier
)

home_invitations (
  id, home_id, email, token, invited_by, expires_at, status
)

-- Recipes
recipes (
  id, home_id, name, source_url, source_type,
  servings, prep_time_minutes, cook_time_minutes,
  created_by, created_at, updated_at, version,
  nutrition_jsonb, tags_array, difficulty,
  is_public, parent_recipe_id
)

recipe_ingredients (
  id, recipe_id, item, quantity, unit, category,
  notes, order_index
)

recipe_instructions (
  id, recipe_id, step_text, order_index,
  duration_minutes, media_url
)

recipe_media (
  id, recipe_id, url, type, order_index
)

recipe_ratings (
  id, recipe_id, user_id, rating, review, created_at
)

-- Meal Planning
meal_plans (
  id, home_id, week_start_date, status,
  created_by, created_at, updated_at,
  settings_jsonb
)

planned_meals (
  id, meal_plan_id, recipe_id, day_of_week,
  meal_type, servings, date, notes
)

-- Shopping
shopping_lists (
  id, home_id, meal_plan_id, created_at, status
)

shopping_list_items (
  id, shopping_list_id, item, quantity, unit,
  category, checked, added_by, recipe_id,
  estimated_price, store_section
)

-- Pantry
pantry_items (
  id, home_id, item, quantity, unit,
  expiration_date, added_by, updated_at,
  location, barcode
)

-- Analytics & Tracking
meal_history (
  id, home_id, recipe_id, date, actual_servings,
  rating, notes, cooked_by
)

-- Background Jobs
job_queue (
  id, job_type, payload_jsonb, status,
  created_at, started_at, completed_at,
  error_message, retry_count
)
```

### API Design

**RESTful Endpoints with OpenAPI:**

```
Authentication:
  POST   /api/v1/auth/register
  POST   /api/v1/auth/login
  POST   /api/v1/auth/refresh
  POST   /api/v1/auth/logout
  POST   /api/v1/auth/forgot-password
  POST   /api/v1/auth/reset-password

Users:
  GET    /api/v1/users/me
  PATCH  /api/v1/users/me
  GET    /api/v1/users/me/preferences
  PATCH  /api/v1/users/me/preferences

Homes:
  GET    /api/v1/homes
  POST   /api/v1/homes
  GET    /api/v1/homes/{home_id}
  PATCH  /api/v1/homes/{home_id}
  DELETE /api/v1/homes/{home_id}
  GET    /api/v1/homes/{home_id}/members
  POST   /api/v1/homes/{home_id}/invitations
  DELETE /api/v1/homes/{home_id}/members/{user_id}

Recipes:
  GET    /api/v1/homes/{home_id}/recipes
  POST   /api/v1/homes/{home_id}/recipes
  GET    /api/v1/homes/{home_id}/recipes/{recipe_id}
  PATCH  /api/v1/homes/{home_id}/recipes/{recipe_id}
  DELETE /api/v1/homes/{home_id}/recipes/{recipe_id}
  POST   /api/v1/homes/{home_id}/recipes/import
  POST   /api/v1/homes/{home_id}/recipes/{recipe_id}/rate
  GET    /api/v1/recipes/public (public recipe discovery)

Meal Plans:
  GET    /api/v1/homes/{home_id}/meal-plans
  POST   /api/v1/homes/{home_id}/meal-plans/generate
  GET    /api/v1/homes/{home_id}/meal-plans/{plan_id}
  PATCH  /api/v1/homes/{home_id}/meal-plans/{plan_id}
  POST   /api/v1/homes/{home_id}/meal-plans/{plan_id}/meals
  PATCH  /api/v1/homes/{home_id}/meal-plans/{plan_id}/meals/{meal_id}
  DELETE /api/v1/homes/{home_id}/meal-plans/{plan_id}/meals/{meal_id}

Shopping Lists:
  GET    /api/v1/homes/{home_id}/shopping-lists
  GET    /api/v1/homes/{home_id}/shopping-lists/{list_id}
  PATCH  /api/v1/homes/{home_id}/shopping-lists/{list_id}/items/{item_id}
  POST   /api/v1/homes/{home_id}/shopping-lists/{list_id}/items

Pantry:
  GET    /api/v1/homes/{home_id}/pantry
  POST   /api/v1/homes/{home_id}/pantry
  PATCH  /api/v1/homes/{home_id}/pantry/{item_id}
  DELETE /api/v1/homes/{home_id}/pantry/{item_id}

Search:
  GET    /api/v1/search/recipes
  GET    /api/v1/search/ingredients

Analytics:
  GET    /api/v1/homes/{home_id}/analytics/nutrition
  GET    /api/v1/homes/{home_id}/analytics/meals
  GET    /api/v1/homes/{home_id}/analytics/budget
```

### Offline-First Strategy

**Flutter Local Storage:**
```dart
// Use Drift for local SQLite database
- Mirror server schema locally
- Store user data, recipes, meal plans, shopping lists
- Queue API mutations (POST, PATCH, DELETE)
- Background sync when online

// Sync Strategy:
1. On app startup: Fetch latest data if online
2. On mutation:
   - Apply locally immediately (optimistic update)
   - Queue for server sync
   - Retry with exponential backoff
3. Conflict resolution:
   - Last-write-wins for most data
   - Merge strategy for shopping list checks
   - User prompt for meal plan conflicts
```

### Scalability Considerations

**Horizontal Scaling:**
- Stateless API servers (JWT, no sessions)
- Database connection pooling
- Read replicas for read-heavy operations
- Sharding by home_id if needed

**Caching Strategy:**
```python
# Redis cache layers:
1. User session cache (30 min TTL)
2. Recipe search results (1 hour TTL)
3. Public recipe catalog (24 hour TTL)
4. Nutrition data from USDA (indefinite)
5. Computed meal plans (until modified)
```

**CDN Strategy:**
- Recipe images served from CDN
- Static assets (app bundles, web assets)
- API responses for public recipes

**Performance Targets:**
- API response time: p95 < 200ms, p99 < 500ms
- Recipe import: < 10 seconds
- Meal plan generation: < 3 seconds
- Search results: < 100ms
- App startup (warm): < 2 seconds

### Security Architecture

**Authentication Flow:**
```
1. User registers/logs in
2. Server validates credentials
3. Server generates JWT access token (15 min) + refresh token (30 days)
4. Client stores tokens securely (Flutter Secure Storage)
5. Client includes access token in Authorization header
6. Server validates JWT on each request
7. Client refreshes access token when expired
```

**Authorization:**
- Home-based access control
- Role-based permissions (admin, member, viewer)
- Resource-level checks (can user access this home's data?)

**Data Security:**
- HTTPS only (TLS 1.3)
- Password hashing (bcrypt)
- SQL injection prevention (parameterized queries)
- Rate limiting (per IP, per user)
- Input validation (Pydantic models)
- XSS prevention
- CORS configuration

**Privacy:**
- GDPR compliance (data export, deletion)
- User data isolation by home
- Optional data sharing (public recipes)
- Audit logs for sensitive operations

### Cost Estimation (Monthly)

**MVP (1,000 active users):**
- DigitalOcean Kubernetes: $50
- Managed PostgreSQL: $60
- Managed Redis: $30
- Object Storage (100GB): $5
- OpenAI API (500 imports/mo): $100
- SendGrid/Resend: $15
- Domain + SSL: $3
- **Total: ~$263/month**

**Growth (10,000 users):**
- Infrastructure: $300
- Database: $120
- Redis: $50
- Storage: $20
- AI APIs: $500
- Email: $50
- Monitoring: $50
- **Total: ~$1,090/month**

**Scale (100,000 users):**
- Infrastructure: $1,500
- Database: $500
- Cache/Queue: $200
- Storage: $100
- AI APIs: $3,000
- Email: $200
- Monitoring: $200
- CDN: $100
- **Total: ~$5,800/month**

### Development Roadmap

**Phase 1: MVP (3-4 months)**
- Core authentication and home management
- Recipe import (URL, manual)
- Basic meal planning
- Shopping list generation
- Mobile app (iOS + Android)
- Basic web app

**Phase 2: Enhancement (2-3 months)**
- Offline support
- Advanced recipe import (photos, video)
- Smart meal suggestions
- Pantry management
- Push notifications
- Recipe ratings and favorites

**Phase 3: Growth (2-3 months)**
- Public recipe sharing
- Social features
- Advanced analytics
- Budget tracking
- Grocery delivery integration
- Voice commands

**Phase 4: Scale (ongoing)**
- Performance optimization
- Advanced AI features
- Smart appliance integration
- Marketplace features
- Regional expansion

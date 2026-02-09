# Software Architecture

## Overview

This document details the software architecture for the Meal Planner application, covering both the Flutter mobile/web frontend and the FastAPI backend. The architecture emphasizes:

- **Offline-first mobile experience** with local data persistence
- **Clean architecture** with clear separation of concerns
- **Scalability** through stateless services and horizontal scaling
- **Maintainability** through modular design and dependency injection
- **Testability** with mockable dependencies and isolated business logic

---

## Flutter Frontend Architecture

### State Management: Riverpod

**Why Riverpod over BLoC/Provider:**
- Compile-safe: Catches errors at compile time, not runtime
- No BuildContext needed for most operations
- Better testability with overrides
- Reactive and declarative
- Great for offline-first apps with async state

**Core Concepts:**
```dart
// Example: Recipe list state with caching
@riverpod
class RecipeList extends _$RecipeList {
  @override
  Future<List<Recipe>> build() async {
    // Load from local DB first (offline support)
    final localRecipes = await ref.read(recipeRepositoryProvider).getLocal();

    // Attempt to sync from server if online
    if (await ref.read(connectivityProvider).future) {
      try {
        final serverRecipes = await ref.read(recipeRepositoryProvider).sync();
        return serverRecipes;
      } catch (e) {
        // Fallback to local if sync fails
        return localRecipes;
      }
    }

    return localRecipes;
  }

  Future<void> addRecipe(Recipe recipe) async {
    // Optimistic update
    state = AsyncValue.data([...state.value!, recipe]);

    // Queue for sync
    await ref.read(syncQueueProvider).enqueue(
      SyncOperation.create(entityType: 'recipe', data: recipe)
    );
  }
}
```

### Folder Structure

```
lib/
├── main.dart                           # App entry point
├── app.dart                            # Root widget with routing, theme
│
├── core/                               # Core utilities and base classes
│   ├── network/
│   │   ├── api_client.dart            # HTTP client with interceptors
│   │   ├── api_endpoints.dart         # Centralized endpoint definitions
│   │   └── network_info.dart          # Connectivity checker
│   ├── database/
│   │   ├── app_database.dart          # Drift database definition
│   │   ├── tables.dart                # Table schemas
│   │   └── dao/                       # Data Access Objects
│   ├── sync/
│   │   ├── sync_manager.dart          # Background sync orchestration
│   │   ├── sync_queue.dart            # Operation queue
│   │   └── conflict_resolver.dart     # Merge strategies
│   ├── error/
│   │   ├── failures.dart              # Failure types
│   │   └── exceptions.dart            # Custom exceptions
│   └── utils/
│       ├── constants.dart
│       ├── extensions.dart
│       └── validators.dart
│
├── features/                           # Feature modules
│   ├── auth/
│   │   ├── data/
│   │   │   ├── models/
│   │   │   │   ├── user_model.dart
│   │   │   │   └── auth_token_model.dart
│   │   │   ├── repositories/
│   │   │   │   └── auth_repository_impl.dart
│   │   │   └── data_sources/
│   │   │       ├── auth_remote_data_source.dart
│   │   │       └── auth_local_data_source.dart
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   │   └── user.dart
│   │   │   ├── repositories/
│   │   │   │   └── auth_repository.dart
│   │   │   └── use_cases/
│   │   │       ├── login_use_case.dart
│   │   │       ├── logout_use_case.dart
│   │   │       └── refresh_token_use_case.dart
│   │   └── presentation/
│   │       ├── providers/
│   │       │   └── auth_provider.dart
│   │       ├── screens/
│   │       │   ├── login_screen.dart
│   │       │   └── register_screen.dart
│   │       └── widgets/
│   │           └── auth_form.dart
│   │
│   ├── recipes/
│   │   ├── data/
│   │   │   ├── models/
│   │   │   │   ├── recipe_model.dart
│   │   │   │   ├── ingredient_model.dart
│   │   │   │   └── nutrition_model.dart
│   │   │   ├── repositories/
│   │   │   │   └── recipe_repository_impl.dart
│   │   │   └── data_sources/
│   │   │       ├── recipe_remote_data_source.dart
│   │   │       └── recipe_local_data_source.dart
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   │   ├── recipe.dart
│   │   │   │   ├── ingredient.dart
│   │   │   │   └── nutrition.dart
│   │   │   ├── repositories/
│   │   │   │   └── recipe_repository.dart
│   │   │   └── use_cases/
│   │   │       ├── get_recipes_use_case.dart
│   │   │       ├── import_recipe_use_case.dart
│   │   │       ├── update_recipe_use_case.dart
│   │   │       └── delete_recipe_use_case.dart
│   │   └── presentation/
│   │       ├── providers/
│   │       │   ├── recipe_list_provider.dart
│   │       │   ├── recipe_detail_provider.dart
│   │       │   └── recipe_import_provider.dart
│   │       ├── screens/
│   │       │   ├── recipe_list_screen.dart
│   │       │   ├── recipe_detail_screen.dart
│   │       │   ├── recipe_import_screen.dart
│   │       │   └── recipe_edit_screen.dart
│   │       └── widgets/
│   │           ├── recipe_card.dart
│   │           ├── ingredient_list.dart
│   │           └── nutrition_badge.dart
│   │
│   ├── meal_planning/
│   │   ├── data/
│   │   ├── domain/
│   │   └── presentation/
│   │
│   ├── shopping_list/
│   │   ├── data/
│   │   ├── domain/
│   │   └── presentation/
│   │
│   └── pantry/
│       ├── data/
│       ├── domain/
│       └── presentation/
│
└── shared/                             # Shared UI components
    ├── widgets/
    │   ├── app_bar.dart
    │   ├── loading_indicator.dart
    │   ├── error_view.dart
    │   └── empty_state.dart
    ├── theme/
    │   ├── app_theme.dart
    │   ├── colors.dart
    │   └── text_styles.dart
    └── routes/
        └── app_router.dart
```

### Clean Architecture Layers

**1. Domain Layer (Business Logic)**
- Pure Dart code, no Flutter dependencies
- Contains entities, use cases, and repository interfaces
- Independent and testable

```dart
// domain/entities/recipe.dart
class Recipe {
  final String id;
  final String name;
  final List<Ingredient> ingredients;
  final List<String> instructions;
  final Nutrition? nutrition;
  final int servings;
  final DateTime createdAt;
  final DateTime updatedAt;

  Recipe({
    required this.id,
    required this.name,
    required this.ingredients,
    required this.instructions,
    this.nutrition,
    required this.servings,
    required this.createdAt,
    required this.updatedAt,
  });
}

// domain/repositories/recipe_repository.dart
abstract class RecipeRepository {
  Future<List<Recipe>> getRecipes({String? homeId});
  Future<Recipe> getRecipeById(String id);
  Future<Recipe> createRecipe(Recipe recipe);
  Future<Recipe> updateRecipe(Recipe recipe);
  Future<void> deleteRecipe(String id);
  Future<Recipe> importRecipeFromUrl(String url);
  Stream<List<Recipe>> watchRecipes({String? homeId});
}

// domain/use_cases/import_recipe_use_case.dart
class ImportRecipeUseCase {
  final RecipeRepository _repository;

  ImportRecipeUseCase(this._repository);

  Future<Recipe> execute(String url) async {
    // Business logic: validate URL, import, generate nutrition
    if (!_isValidUrl(url)) {
      throw InvalidUrlException();
    }

    return await _repository.importRecipeFromUrl(url);
  }

  bool _isValidUrl(String url) {
    return Uri.tryParse(url)?.hasAbsolutePath ?? false;
  }
}
```

**2. Data Layer (Implementation)**
- Implements repository interfaces from domain layer
- Handles data sources (remote API, local database)
- Performs data transformation (models ↔ entities)

```dart
// data/models/recipe_model.dart
@freezed
class RecipeModel with _$RecipeModel {
  const factory RecipeModel({
    required String id,
    required String name,
    required List<IngredientModel> ingredients,
    required List<String> instructions,
    NutritionModel? nutrition,
    required int servings,
    required DateTime createdAt,
    required DateTime updatedAt,
    String? sourceUrl,
    List<String>? tags,
  }) = _RecipeModel;

  factory RecipeModel.fromJson(Map<String, dynamic> json) =>
      _$RecipeModelFromJson(json);

  factory RecipeModel.fromEntity(Recipe entity) {
    return RecipeModel(
      id: entity.id,
      name: entity.name,
      ingredients: entity.ingredients.map(IngredientModel.fromEntity).toList(),
      instructions: entity.instructions,
      nutrition: entity.nutrition != null
          ? NutritionModel.fromEntity(entity.nutrition!)
          : null,
      servings: entity.servings,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }
}

extension RecipeModelX on RecipeModel {
  Recipe toEntity() {
    return Recipe(
      id: id,
      name: name,
      ingredients: ingredients.map((i) => i.toEntity()).toList(),
      instructions: instructions,
      nutrition: nutrition?.toEntity(),
      servings: servings,
      createdAt: createdAt,
      updatedAt: updatedAt,
    );
  }
}

// data/repositories/recipe_repository_impl.dart
class RecipeRepositoryImpl implements RecipeRepository {
  final RecipeRemoteDataSource _remoteDataSource;
  final RecipeLocalDataSource _localDataSource;
  final NetworkInfo _networkInfo;
  final SyncQueue _syncQueue;

  RecipeRepositoryImpl(
    this._remoteDataSource,
    this._localDataSource,
    this._networkInfo,
    this._syncQueue,
  );

  @override
  Future<List<Recipe>> getRecipes({String? homeId}) async {
    // Try remote first if online
    if (await _networkInfo.isConnected) {
      try {
        final remoteRecipes = await _remoteDataSource.getRecipes(homeId: homeId);

        // Update local cache
        await _localDataSource.cacheRecipes(remoteRecipes);

        return remoteRecipes.map((m) => m.toEntity()).toList();
      } catch (e) {
        // Fall back to local cache
        print('Failed to fetch remote recipes, using cache: $e');
      }
    }

    // Return local cache
    final localRecipes = await _localDataSource.getRecipes(homeId: homeId);
    return localRecipes.map((m) => m.toEntity()).toList();
  }

  @override
  Future<Recipe> createRecipe(Recipe recipe) async {
    final model = RecipeModel.fromEntity(recipe);

    // Save locally first (optimistic update)
    await _localDataSource.insertRecipe(model);

    // Queue for server sync
    await _syncQueue.enqueue(
      SyncOperation(
        type: SyncOperationType.create,
        entityType: 'recipe',
        entityId: recipe.id,
        data: model.toJson(),
      ),
    );

    return recipe;
  }

  @override
  Stream<List<Recipe>> watchRecipes({String? homeId}) {
    return _localDataSource.watchRecipes(homeId: homeId).map(
      (models) => models.map((m) => m.toEntity()).toList(),
    );
  }
}
```

**3. Presentation Layer (UI)**
- Flutter widgets and screens
- State management with Riverpod
- Reacts to state changes from providers

```dart
// presentation/providers/recipe_list_provider.dart
@riverpod
class RecipeList extends _$RecipeList {
  @override
  Future<List<Recipe>> build() async {
    final repository = ref.watch(recipeRepositoryProvider);
    return repository.getRecipes();
  }

  Future<void> importRecipe(String url) async {
    state = const AsyncValue.loading();

    final useCase = ref.read(importRecipeUseCaseProvider);
    state = await AsyncValue.guard(() => useCase.execute(url));

    // Refresh list after import
    if (state.hasValue) {
      ref.invalidateSelf();
    }
  }

  Future<void> deleteRecipe(String id) async {
    final repository = ref.read(recipeRepositoryProvider);
    await repository.deleteRecipe(id);
    ref.invalidateSelf();
  }
}

// presentation/screens/recipe_list_screen.dart
class RecipeListScreen extends ConsumerWidget {
  const RecipeListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recipesAsync = ref.watch(recipeListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Recipes'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showImportDialog(context, ref),
          ),
        ],
      ),
      body: recipesAsync.when(
        data: (recipes) => recipes.isEmpty
            ? const EmptyStateWidget(message: 'No recipes yet')
            : ListView.builder(
                itemCount: recipes.length,
                itemBuilder: (context, index) {
                  return RecipeCard(recipe: recipes[index]);
                },
              ),
        loading: () => const LoadingIndicator(),
        error: (error, stack) => ErrorView(
          message: error.toString(),
          onRetry: () => ref.invalidate(recipeListProvider),
        ),
      ),
    );
  }

  void _showImportDialog(BuildContext context, WidgetRef ref) {
    // Show import URL dialog
  }
}
```

### Offline-First Implementation with Drift

**Database Definition:**
```dart
// core/database/app_database.dart
@DriftDatabase(tables: [Recipes, Ingredients, MealPlans, ShoppingLists, SyncQueue])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (Migrator m) async {
      await m.createAll();
    },
    onUpgrade: (Migrator m, int from, int to) async {
      // Handle schema migrations
    },
  );
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'meal_planner.db'));
    return NativeDatabase(file);
  });
}

// core/database/tables.dart
class Recipes extends Table {
  TextColumn get id => text()();
  TextColumn get homeId => text().nullable()();
  TextColumn get name => text()();
  TextColumn get sourceUrl => text().nullable()();
  IntColumn get servings => integer()();
  IntColumn get prepTimeMinutes => integer().nullable()();
  IntColumn get cookTimeMinutes => integer().nullable()();
  TextColumn get tagsJson => text().nullable()();
  TextColumn get nutritionJson => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();
  BoolColumn get isSynced => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}

class SyncQueue extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get operationType => text()(); // create, update, delete
  TextColumn get entityType => text()(); // recipe, meal_plan, etc.
  TextColumn get entityId => text()();
  TextColumn get dataJson => text()();
  DateTimeColumn get createdAt => dateTime()();
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  TextColumn get errorMessage => text().nullable()();
}
```

**Sync Manager:**
```dart
// core/sync/sync_manager.dart
class SyncManager {
  final AppDatabase _database;
  final ApiClient _apiClient;
  final NetworkInfo _networkInfo;

  SyncManager(this._database, this._apiClient, this._networkInfo);

  Future<void> syncAll() async {
    if (!await _networkInfo.isConnected) return;

    final operations = await _database.syncQueueDao.getPendingOperations();

    for (final op in operations) {
      try {
        await _processOperation(op);
        await _database.syncQueueDao.deleteOperation(op.id);
      } catch (e) {
        // Increment retry count
        await _database.syncQueueDao.incrementRetry(op.id, e.toString());

        // Remove after 5 failed attempts
        if (op.retryCount >= 5) {
          await _database.syncQueueDao.deleteOperation(op.id);
        }
      }
    }
  }

  Future<void> _processOperation(SyncQueueData op) async {
    switch (op.entityType) {
      case 'recipe':
        await _syncRecipe(op);
        break;
      case 'meal_plan':
        await _syncMealPlan(op);
        break;
      // ... more entity types
    }
  }

  Future<void> _syncRecipe(SyncQueueData op) async {
    final data = jsonDecode(op.dataJson);

    switch (op.operationType) {
      case 'create':
        await _apiClient.post('/recipes', data: data);
        break;
      case 'update':
        await _apiClient.patch('/recipes/${op.entityId}', data: data);
        break;
      case 'delete':
        await _apiClient.delete('/recipes/${op.entityId}');
        break;
    }

    // Mark as synced in local database
    await _database.recipesDao.markAsSynced(op.entityId);
  }

  // Background sync setup
  void startBackgroundSync() {
    // Sync every 15 minutes when online
    Timer.periodic(const Duration(minutes: 15), (_) async {
      if (await _networkInfo.isConnected) {
        await syncAll();
      }
    });
  }
}
```

### Dependency Injection with Riverpod

```dart
// Core providers
@riverpod
AppDatabase appDatabase(AppDatabaseRef ref) {
  return AppDatabase();
}

@riverpod
ApiClient apiClient(ApiClientRef ref) {
  final authToken = ref.watch(authTokenProvider);
  return ApiClient(
    baseUrl: Config.apiBaseUrl,
    authToken: authToken,
  );
}

@riverpod
NetworkInfo networkInfo(NetworkInfoRef ref) {
  return NetworkInfoImpl();
}

// Repository providers
@riverpod
RecipeRepository recipeRepository(RecipeRepositoryRef ref) {
  return RecipeRepositoryImpl(
    RecipeRemoteDataSource(ref.watch(apiClientProvider)),
    RecipeLocalDataSource(ref.watch(appDatabaseProvider)),
    ref.watch(networkInfoProvider),
    ref.watch(syncQueueProvider),
  );
}

// Use case providers
@riverpod
ImportRecipeUseCase importRecipeUseCase(ImportRecipeUseCaseRef ref) {
  return ImportRecipeUseCase(ref.watch(recipeRepositoryProvider));
}
```

---

## FastAPI Backend Architecture

### Project Structure

```
backend/
├── app/
│   ├── main.py                         # Application entry point
│   ├── config.py                       # Configuration management
│   ├── dependencies.py                 # Dependency injection
│   │
│   ├── core/                           # Core utilities
│   │   ├── security.py                # JWT, password hashing
│   │   ├── database.py                # DB connection, session management
│   │   ├── cache.py                   # Redis client
│   │   ├── exceptions.py              # Custom exceptions
│   │   └── middleware.py              # Request logging, error handling
│   │
│   ├── models/                         # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── home.py
│   │   ├── recipe.py
│   │   ├── meal_plan.py
│   │   ├── shopping_list.py
│   │   └── pantry.py
│   │
│   ├── schemas/                        # Pydantic schemas (API contracts)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── home.py
│   │   ├── recipe.py
│   │   ├── meal_plan.py
│   │   ├── shopping_list.py
│   │   └── pantry.py
│   │
│   ├── api/                            # API routes
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   ├── homes.py
│   │   │   │   ├── recipes.py
│   │   │   │   ├── meal_plans.py
│   │   │   │   ├── shopping_lists.py
│   │   │   │   └── pantry.py
│   │   │   └── api.py              # Route aggregation
│   │   └── deps.py                 # Route dependencies
│   │
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── home_service.py
│   │   ├── recipe_service.py
│   │   ├── recipe_parser_service.py
│   │   ├── nutrition_service.py
│   │   ├── meal_plan_service.py
│   │   ├── shopping_list_service.py
│   │   └── pantry_service.py
│   │
│   ├── repositories/                   # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user_repository.py
│   │   ├── home_repository.py
│   │   ├── recipe_repository.py
│   │   ├── meal_plan_repository.py
│   │   ├── shopping_list_repository.py
│   │   └── pantry_repository.py
│   │
│   ├── tasks/                          # Background tasks (Celery/RQ)
│   │   ├── __init__.py
│   │   ├── recipe_import.py
│   │   ├── nutrition_generation.py
│   │   └── notifications.py
│   │
│   └── utils/                          # Helper functions
│       ├── __init__.py
│       ├── validators.py
│       ├── formatters.py
│       └── helpers.py
│
├── alembic/                            # Database migrations
│   ├── versions/
│   └── env.py
│
├── tests/                              # Test suite
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

### Layered Architecture

**1. API Layer (Routes/Endpoints)**
```python
# api/v1/endpoints/recipes.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.recipe import Recipe, RecipeCreate, RecipeUpdate, RecipeImport
from app.services.recipe_service import RecipeService
from app.api.deps import get_current_user, get_recipe_service
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[Recipe])
async def get_recipes(
    home_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    recipe_service: RecipeService = Depends(get_recipe_service),
):
    """Get all recipes for a home."""
    # Verify user has access to this home
    if not await recipe_service.user_has_home_access(current_user.id, home_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this home"
        )

    return await recipe_service.get_recipes(
        home_id=home_id,
        skip=skip,
        limit=limit
    )

@router.post("/import", response_model=Recipe, status_code=status.HTTP_201_CREATED)
async def import_recipe(
    home_id: str,
    recipe_import: RecipeImport,
    current_user: User = Depends(get_current_user),
    recipe_service: RecipeService = Depends(get_recipe_service),
):
    """Import a recipe from URL."""
    if not await recipe_service.user_has_home_access(current_user.id, home_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this home"
        )

    try:
        recipe = await recipe_service.import_recipe(
            home_id=home_id,
            url=recipe_import.url,
            created_by=current_user.id
        )
        return recipe
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.patch("/{recipe_id}", response_model=Recipe)
async def update_recipe(
    home_id: str,
    recipe_id: str,
    recipe_update: RecipeUpdate,
    current_user: User = Depends(get_current_user),
    recipe_service: RecipeService = Depends(get_recipe_service),
):
    """Update a recipe."""
    if not await recipe_service.user_has_home_access(current_user.id, home_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this home"
        )

    recipe = await recipe_service.update_recipe(
        recipe_id=recipe_id,
        recipe_update=recipe_update
    )

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    return recipe
```

**2. Service Layer (Business Logic)**
```python
# services/recipe_service.py
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.home_repository import HomeRepository
from app.services.recipe_parser_service import RecipeParserService
from app.services.nutrition_service import NutritionService
from app.schemas.recipe import Recipe, RecipeCreate, RecipeUpdate
from app.core.cache import cache
from app.tasks.recipe_import import import_recipe_async

class RecipeService:
    def __init__(
        self,
        recipe_repository: RecipeRepository,
        home_repository: HomeRepository,
        parser_service: RecipeParserService,
        nutrition_service: NutritionService,
    ):
        self.recipe_repo = recipe_repository
        self.home_repo = home_repository
        self.parser = parser_service
        self.nutrition = nutrition_service

    async def get_recipes(
        self,
        home_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Recipe]:
        """Get recipes with caching."""
        cache_key = f"recipes:{home_id}:{skip}:{limit}"

        # Try cache first
        cached = await cache.get(cache_key)
        if cached:
            return cached

        # Fetch from database
        recipes = await self.recipe_repo.get_by_home(
            home_id=home_id,
            skip=skip,
            limit=limit
        )

        # Cache for 1 hour
        await cache.set(cache_key, recipes, ttl=3600)

        return recipes

    async def import_recipe(
        self,
        home_id: str,
        url: str,
        created_by: str
    ) -> Recipe:
        """Import recipe from URL with nutrition generation."""
        # Parse recipe from URL
        parsed_recipe = await self.parser.parse_from_url(url)

        # Generate nutrition data
        nutrition = await self.nutrition.generate_from_ingredients(
            parsed_recipe.ingredients
        )

        # Create recipe
        recipe_create = RecipeCreate(
            home_id=home_id,
            name=parsed_recipe.name,
            source_url=url,
            ingredients=parsed_recipe.ingredients,
            instructions=parsed_recipe.instructions,
            servings=parsed_recipe.servings,
            prep_time_minutes=parsed_recipe.prep_time_minutes,
            cook_time_minutes=parsed_recipe.cook_time_minutes,
            tags=parsed_recipe.tags,
            nutrition=nutrition,
            created_by=created_by,
        )

        recipe = await self.recipe_repo.create(recipe_create)

        # Invalidate cache
        await self._invalidate_cache(home_id)

        return recipe

    async def update_recipe(
        self,
        recipe_id: str,
        recipe_update: RecipeUpdate
    ) -> Optional[Recipe]:
        """Update recipe."""
        recipe = await self.recipe_repo.update(recipe_id, recipe_update)

        if recipe:
            # Invalidate cache
            await self._invalidate_cache(recipe.home_id)

        return recipe

    async def user_has_home_access(
        self,
        user_id: str,
        home_id: str
    ) -> bool:
        """Check if user has access to home."""
        return await self.home_repo.user_is_member(user_id, home_id)

    async def _invalidate_cache(self, home_id: str):
        """Invalidate all recipe caches for a home."""
        pattern = f"recipes:{home_id}:*"
        await cache.delete_pattern(pattern)
```

**3. Repository Layer (Data Access)**
```python
# repositories/base.py
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: str) -> Optional[ModelType]:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        result = await self.db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        obj = self.model(**obj_in.dict())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(
        self,
        id: str,
        obj_in: UpdateSchemaType
    ) -> Optional[ModelType]:
        obj = await self.get(id)
        if not obj:
            return None

        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(obj, field, value)

        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: str) -> Optional[ModelType]:
        obj = await self.get(id)
        if obj:
            await self.db.delete(obj)
            await self.db.commit()
        return obj

# repositories/recipe_repository.py
from typing import List
from sqlalchemy import select
from app.models.recipe import Recipe
from app.schemas.recipe import RecipeCreate, RecipeUpdate
from app.repositories.base import BaseRepository

class RecipeRepository(BaseRepository[Recipe, RecipeCreate, RecipeUpdate]):
    async def get_by_home(
        self,
        home_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Recipe]:
        result = await self.db.execute(
            select(Recipe)
            .where(Recipe.home_id == home_id)
            .offset(skip)
            .limit(limit)
            .order_by(Recipe.created_at.desc())
        )
        return result.scalars().all()

    async def search(
        self,
        home_id: str,
        query: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Recipe]:
        result = await self.db.execute(
            select(Recipe)
            .where(Recipe.home_id == home_id)
            .where(Recipe.name.ilike(f"%{query}%"))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
```

**4. Dependency Injection**
```python
# api/deps.py
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_jwt
from app.models.user import User
from app.repositories.user_repository import UserRepository

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials

    try:
        payload = decode_jwt(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user

# dependencies.py
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.home_repository import HomeRepository
from app.services.recipe_service import RecipeService
from app.services.recipe_parser_service import RecipeParserService
from app.services.nutrition_service import NutritionService

def get_recipe_service(
    db: AsyncSession = Depends(get_db),
) -> RecipeService:
    """Get recipe service with all dependencies."""
    recipe_repo = RecipeRepository(db)
    home_repo = HomeRepository(db)
    parser_service = RecipeParserService()
    nutrition_service = NutritionService()

    return RecipeService(
        recipe_repository=recipe_repo,
        home_repository=home_repo,
        parser_service=parser_service,
        nutrition_service=nutrition_service,
    )
```

### Background Tasks with Celery

```python
# tasks/__init__.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "meal_planner",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# tasks/recipe_import.py
from app.tasks import celery_app
from app.services.recipe_service import RecipeService

@celery_app.task(bind=True, max_retries=3)
def import_recipe_async(self, home_id: str, url: str, user_id: str):
    """Async task for recipe import with retry logic."""
    try:
        # Create service with DB session
        with get_db_context() as db:
            recipe_service = get_recipe_service(db)
            recipe = recipe_service.import_recipe(
                home_id=home_id,
                url=url,
                created_by=user_id
            )
            return recipe.id
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

---

## Migration Strategy: Flask POC → FastAPI Production

### Phase 1: Parallel Development (Weeks 1-2)

**Goal:** Set up FastAPI backend alongside existing Flask app

1. **Create new backend/ directory**
   - Initialize FastAPI project structure
   - Set up PostgreSQL database
   - Create Alembic migrations

2. **Port existing functionality**
   - Recipe parser (reuse existing Python code)
   - Nutrition generator (reuse USDA API logic)
   - Tag inference (reuse existing logic)

3. **Implement authentication**
   - JWT-based auth with refresh tokens
   - User registration/login endpoints

4. **Data migration script**
   - Read recipes.json from POC
   - Bulk insert into PostgreSQL
   - Preserve IDs for continuity

### Phase 2: API Parity (Weeks 3-4)

**Goal:** Achieve feature parity with Flask POC

1. **Complete API endpoints**
   - All recipe CRUD operations
   - Recipe import (URL and text)
   - Recipe search

2. **Testing**
   - Unit tests for services
   - Integration tests for endpoints
   - Load testing with Locust

3. **Deploy to staging**
   - DigitalOcean App Platform or Kubernetes
   - Connect to managed PostgreSQL
   - Set up Redis cache

### Phase 3: Flutter App Development (Weeks 5-8)

**Goal:** Build mobile app with offline support

1. **Set up Flutter project**
   - Configure Drift database
   - Implement Riverpod state management
   - Create API client with auth

2. **Core features**
   - Authentication screens
   - Recipe list and detail
   - Recipe import
   - Basic meal planning

3. **Offline support**
   - Local data persistence
   - Sync queue implementation
   - Conflict resolution

### Phase 4: Migration & Launch (Weeks 9-10)

**Goal:** Switch to production

1. **User migration**
   - Email existing users about new app
   - Provide export/import functionality
   - Run both systems in parallel for 2 weeks

2. **Monitor and iterate**
   - Track error rates with Sentry
   - Monitor performance with DataDog
   - Collect user feedback

3. **Deprecate Flask POC**
   - Redirect old URLs to new app
   - Keep POC in read-only mode for 1 month
   - Archive POC codebase

### Code Reuse Strategy

**Reusable from POC:**
- Recipe parser logic (HTML parsing, Schema.org)
- USDA API integration
- Tag inference logic
- Ingredient parsing patterns
- Nutrition calculations

**Port to FastAPI as-is:**
```python
# POC: app/recipe_parser.py
# FastAPI: backend/app/services/recipe_parser_service.py
# → Copy and adapt with async/await, type hints, better error handling
```

**Flutter will reimplement:**
- UI/UX from scratch (better mobile experience)
- Local database schema (Drift instead of JSON)
- State management (Riverpod instead of Flask sessions)

---

## Testing Strategy

### Flutter Tests

```dart
// Unit test: Use case
void main() {
  group('ImportRecipeUseCase', () {
    late MockRecipeRepository mockRepository;
    late ImportRecipeUseCase useCase;

    setUp(() {
      mockRepository = MockRecipeRepository();
      useCase = ImportRecipeUseCase(mockRepository);
    });

    test('should import recipe from valid URL', () async {
      // Arrange
      const url = 'https://example.com/recipe';
      final expectedRecipe = Recipe(/* ... */);

      when(mockRepository.importRecipeFromUrl(url))
          .thenAnswer((_) async => expectedRecipe);

      // Act
      final result = await useCase.execute(url);

      // Assert
      expect(result, expectedRecipe);
      verify(mockRepository.importRecipeFromUrl(url)).called(1);
    });

    test('should throw InvalidUrlException for invalid URL', () async {
      // Act & Assert
      expect(
        () => useCase.execute('not a url'),
        throwsA(isA<InvalidUrlException>()),
      );
    });
  });
}

// Widget test: Recipe card
void main() {
  testWidgets('RecipeCard displays recipe info', (tester) async {
    final recipe = Recipe(
      id: '1',
      name: 'Test Recipe',
      servings: 4,
      /* ... */
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: RecipeCard(recipe: recipe),
          ),
        ),
      ),
    );

    expect(find.text('Test Recipe'), findsOneWidget);
    expect(find.text('Servings: 4'), findsOneWidget);
  });
}
```

### FastAPI Tests

```python
# tests/unit/test_recipe_service.py
import pytest
from unittest.mock import AsyncMock, Mock
from app.services.recipe_service import RecipeService

@pytest.mark.asyncio
async def test_get_recipes_returns_from_cache():
    # Arrange
    mock_repo = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = [{"id": "1", "name": "Cached Recipe"}]

    service = RecipeService(
        recipe_repository=mock_repo,
        cache=mock_cache,
        # ... other deps
    )

    # Act
    recipes = await service.get_recipes(home_id="home1")

    # Assert
    assert len(recipes) == 1
    assert recipes[0]["name"] == "Cached Recipe"
    mock_cache.get.assert_called_once()
    mock_repo.get_by_home.assert_not_called()  # Should not hit DB

# tests/integration/test_recipe_api.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_import_recipe(async_client: AsyncClient, auth_headers):
    # Arrange
    payload = {
        "url": "https://example.com/recipe"
    }

    # Act
    response = await async_client.post(
        "/api/v1/homes/home1/recipes/import",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] is not None
    assert data["source_url"] == payload["url"]
```

---

## Security Best Practices

### Authentication & Authorization

```python
# JWT with refresh token rotation
def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=15)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=30)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Refresh endpoint
@router.post("/auth/refresh")
async def refresh_access_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_jwt(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")

    # Create new access token and new refresh token (rotation)
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }
```

### Input Validation

```python
# Pydantic models with validators
from pydantic import BaseModel, validator, HttpUrl
from typing import List

class RecipeImport(BaseModel):
    url: HttpUrl  # Automatically validates URL format

    @validator('url')
    def validate_url_domain(cls, v):
        # Block potentially malicious domains
        blocked = ['localhost', '127.0.0.1', '0.0.0.0']
        if any(blocked_domain in str(v) for blocked_domain in blocked):
            raise ValueError('URL domain not allowed')
        return v

class RecipeCreate(BaseModel):
    name: str
    ingredients: List[Ingredient]
    servings: int

    @validator('name')
    def validate_name(cls, v):
        if len(v) < 3:
            raise ValueError('Name must be at least 3 characters')
        if len(v) > 200:
            raise ValueError('Name must be less than 200 characters')
        return v

    @validator('servings')
    def validate_servings(cls, v):
        if v < 1 or v > 100:
            raise ValueError('Servings must be between 1 and 100')
        return v
```

### Rate Limiting

```python
# Middleware with Redis
from fastapi import Request
from app.core.cache import redis_client

async def rate_limit_middleware(request: Request, call_next):
    # Get user IP or user ID
    client_id = request.client.host
    if request.state.user:
        client_id = f"user:{request.state.user.id}"

    # Check rate limit (max 100 requests per minute)
    key = f"rate_limit:{client_id}"
    count = await redis_client.incr(key)

    if count == 1:
        await redis_client.expire(key, 60)  # 1 minute window

    if count > 100:
        raise HTTPException(
            status_code=429,
            detail="Too many requests"
        )

    response = await call_next(request)
    return response
```

---

## Performance Optimization

### Database Query Optimization

```python
# Use select_in loading to avoid N+1 queries
from sqlalchemy.orm import selectinload

async def get_recipes_with_ingredients(home_id: str):
    result = await db.execute(
        select(Recipe)
        .where(Recipe.home_id == home_id)
        .options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.instructions),
        )
        .limit(100)
    )
    return result.scalars().all()

# Use database indexes
class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(String, primary_key=True)
    home_id = Column(String, index=True)  # Index for filtering
    name = Column(String, index=True)  # Index for search
    created_at = Column(DateTime, index=True)  # Index for sorting

    # Composite index for common queries
    __table_args__ = (
        Index('ix_recipes_home_created', 'home_id', 'created_at'),
    )
```

### Caching Strategy

```python
# Multi-level caching
class CacheService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.local_cache = {}  # In-memory cache for frequently accessed data

    async def get(self, key: str):
        # Check local cache first (fastest)
        if key in self.local_cache:
            return self.local_cache[key]

        # Check Redis (fast)
        value = await self.redis.get(key)
        if value:
            self.local_cache[key] = value
            return value

        return None

    async def set(self, key: str, value: any, ttl: int = 3600):
        # Set in both caches
        self.local_cache[key] = value
        await self.redis.setex(key, ttl, value)
```

---

## Deployment & DevOps

### Docker Configuration

```dockerfile
# Dockerfile for FastAPI
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini .

# Run migrations and start server
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mealplanner
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=mealplanner

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  celery_worker:
    build: .
    command: celery -A app.tasks worker --loglevel=info
    depends_on:
      - redis
      - db

volumes:
  postgres_data:
  redis_data:
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest --cov=app tests/

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-flutter:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.16.0'

      - name: Install dependencies
        run: flutter pub get

      - name: Run tests
        run: flutter test --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  deploy:
    needs: [test-backend, test-flutter]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Deploy to DigitalOcean
        run: |
          # Deploy backend
          doctl apps create-deployment ${{ secrets.APP_ID }}
```

---

## Monitoring & Observability

### Logging

```python
# Structured logging with loguru
from loguru import logger

logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    serialize=True,  # JSON format
)

# Usage
@router.post("/recipes/import")
async def import_recipe(url: str):
    logger.info(f"Recipe import started", extra={"url": url})

    try:
        recipe = await recipe_service.import_recipe(url)
        logger.info(f"Recipe imported successfully", extra={
            "recipe_id": recipe.id,
            "url": url,
        })
        return recipe
    except Exception as e:
        logger.error(f"Recipe import failed", extra={
            "url": url,
            "error": str(e),
        })
        raise
```

### Metrics

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

# Define metrics
recipe_imports_total = Counter(
    'recipe_imports_total',
    'Total number of recipe imports',
    ['status']
)

recipe_import_duration = Histogram(
    'recipe_import_duration_seconds',
    'Time spent importing recipes'
)

# Use in endpoints
@recipe_import_duration.time()
async def import_recipe(url: str):
    try:
        recipe = await service.import_recipe(url)
        recipe_imports_total.labels(status='success').inc()
        return recipe
    except Exception:
        recipe_imports_total.labels(status='failure').inc()
        raise
```

---

## Summary

This architecture provides:

✅ **Scalability**: Horizontal scaling, caching, database optimization
✅ **Maintainability**: Clean architecture, separation of concerns, dependency injection
✅ **Testability**: Unit, integration, and widget tests with mocking
✅ **Offline-First**: Local persistence with background sync
✅ **Security**: JWT authentication, input validation, rate limiting
✅ **Performance**: Multi-level caching, query optimization, async operations
✅ **Observability**: Structured logging, metrics, error tracking
✅ **Developer Experience**: Type safety, code generation, hot reload

The architecture is production-ready and follows industry best practices for both mobile and backend development.

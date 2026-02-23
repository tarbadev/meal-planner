"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-21

"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS households (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id                  TEXT PRIMARY KEY,
            household_id        UUID REFERENCES households(id) ON DELETE CASCADE,
            name                TEXT NOT NULL,
            servings            INTEGER NOT NULL DEFAULT 4,
            prep_time_minutes   INTEGER NOT NULL DEFAULT 0,
            cook_time_minutes   INTEGER NOT NULL DEFAULT 0,
            nutrition           JSONB NOT NULL DEFAULT '{}',
            tags                TEXT[] NOT NULL DEFAULT '{}',
            ingredients         JSONB NOT NULL DEFAULT '[]',
            instructions        JSONB NOT NULL DEFAULT '[]',
            source_url          TEXT,
            image_url           TEXT,
            reheats_well        BOOLEAN NOT NULL DEFAULT FALSE,
            stores_days         INTEGER NOT NULL DEFAULT 0,
            packs_well_as_lunch BOOLEAN NOT NULL DEFAULT FALSE,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_recipes_household_id ON recipes (household_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recipes_tags ON recipes USING GIN (tags)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS weekly_plans (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            household_id        UUID REFERENCES households(id) ON DELETE CASCADE,
            daily_calorie_limit FLOAT,
            manual_overrides    JSONB,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_weekly_plans_household_created
        ON weekly_plans (household_id, created_at DESC)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS planned_meals (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id             UUID REFERENCES weekly_plans(id) ON DELETE CASCADE,
            recipe_id           TEXT REFERENCES recipes(id) ON DELETE RESTRICT,
            day                 TEXT NOT NULL,
            meal_type           TEXT NOT NULL,
            household_portions  FLOAT NOT NULL,
            meal_source         TEXT NOT NULL DEFAULT 'fresh',
            linked_meal         TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_planned_meals_plan_id ON planned_meals (plan_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS shopping_list_items (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id     UUID REFERENCES weekly_plans(id) ON DELETE CASCADE,
            item        TEXT NOT NULL,
            quantity    FLOAT,
            unit        TEXT NOT NULL DEFAULT '',
            category    TEXT NOT NULL DEFAULT 'other',
            sources     JSONB NOT NULL DEFAULT '[]',
            checked     BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order  INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_shopping_list_items_plan_sort
        ON shopping_list_items (plan_id, sort_order)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS excluded_ingredients (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            household_id UUID REFERENCES households(id) ON DELETE CASCADE,
            ingredient   TEXT NOT NULL,
            UNIQUE (household_id, ingredient)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS excluded_ingredients")
    op.execute("DROP TABLE IF EXISTS shopping_list_items")
    op.execute("DROP TABLE IF EXISTS planned_meals")
    op.execute("DROP TABLE IF EXISTS weekly_plans")
    op.execute("DROP TABLE IF EXISTS recipes")
    op.execute("DROP TABLE IF EXISTS households")

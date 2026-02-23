"""Recipe UUID primary key + slug column + public recipes

Revision ID: 002
Revises: 001
Create Date: 2026-02-23

Changes:
  - recipes.id TEXT → UUID (PostgreSQL-generated)
  - Add recipes.slug TEXT UNIQUE NOT NULL  (the old id values)
  - planned_meals.recipe_id TEXT → UUID FK → recipes.id
  - Null out household_id on existing seeded recipes (making them public)
    so every household can see them.
"""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add slug column, back-fill from current TEXT id, add UNIQUE idx
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE recipes ADD COLUMN slug TEXT")
    op.execute("UPDATE recipes SET slug = id")
    op.execute("ALTER TABLE recipes ALTER COLUMN slug SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX ix_recipes_slug ON recipes (slug)")

    # ------------------------------------------------------------------
    # 2. Add new UUID id column (auto-generated for every existing row)
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE recipes ADD COLUMN new_id UUID DEFAULT gen_random_uuid() NOT NULL"
    )

    # ------------------------------------------------------------------
    # 3. Migrate planned_meals.recipe_id TEXT → UUID
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE planned_meals ADD COLUMN new_recipe_id UUID")
    op.execute(
        """
        UPDATE planned_meals
        SET new_recipe_id = (
            SELECT new_id FROM recipes WHERE recipes.id = planned_meals.recipe_id
        )
        """
    )
    # Delete orphaned meals whose recipe no longer exists (safety net)
    op.execute("DELETE FROM planned_meals WHERE new_recipe_id IS NULL")
    op.execute(
        "ALTER TABLE planned_meals ALTER COLUMN new_recipe_id SET NOT NULL"
    )

    # Drop old FK + column, rename new column
    op.execute(
        "ALTER TABLE planned_meals DROP CONSTRAINT planned_meals_recipe_id_fkey"
    )
    op.execute("ALTER TABLE planned_meals DROP COLUMN recipe_id")
    op.execute(
        "ALTER TABLE planned_meals RENAME COLUMN new_recipe_id TO recipe_id"
    )

    # ------------------------------------------------------------------
    # 4. Swap recipes primary key TEXT → UUID
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE recipes DROP CONSTRAINT recipes_pkey")
    op.execute("ALTER TABLE recipes DROP COLUMN id")
    op.execute("ALTER TABLE recipes RENAME COLUMN new_id TO id")
    op.execute("ALTER TABLE recipes ADD PRIMARY KEY (id)")

    # ------------------------------------------------------------------
    # 5. Re-add FK on planned_meals pointing at new UUID PK
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE planned_meals
        ADD CONSTRAINT planned_meals_recipe_id_fkey
        FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE RESTRICT
        """
    )

    # ------------------------------------------------------------------
    # 6. Make existing seeded recipes public (NULL household_id).
    #    Recipes that came from the seed script belonged to the default
    #    household only for lack of a better owner.  Now that we have a
    #    public/private distinction we clear that FK so they're visible
    #    to every household.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE recipes
        SET household_id = NULL
        WHERE household_id = '00000000-0000-0000-0000-000000000001'::uuid
        """
    )


def downgrade() -> None:
    # Reverse the UUID → TEXT migration.
    # Note: UUIDs are converted back to their slug values.

    # Re-add TEXT recipe_id column on planned_meals
    op.execute("ALTER TABLE planned_meals ADD COLUMN old_recipe_id TEXT")
    op.execute(
        """
        UPDATE planned_meals
        SET old_recipe_id = (
            SELECT slug FROM recipes WHERE recipes.id = planned_meals.recipe_id
        )
        """
    )
    op.execute("DELETE FROM planned_meals WHERE old_recipe_id IS NULL")
    op.execute("ALTER TABLE planned_meals ALTER COLUMN old_recipe_id SET NOT NULL")
    op.execute(
        "ALTER TABLE planned_meals DROP CONSTRAINT planned_meals_recipe_id_fkey"
    )
    op.execute("ALTER TABLE planned_meals DROP COLUMN recipe_id")
    op.execute("ALTER TABLE planned_meals RENAME COLUMN old_recipe_id TO recipe_id")

    # Swap recipes PK back to slug TEXT
    op.execute("ALTER TABLE recipes DROP CONSTRAINT recipes_pkey")
    op.execute("ALTER TABLE recipes DROP COLUMN id")
    op.execute("ALTER TABLE recipes RENAME COLUMN slug TO id")
    op.execute("ALTER TABLE recipes ADD PRIMARY KEY (id)")

    # Re-add original TEXT FK
    op.execute(
        """
        ALTER TABLE planned_meals
        ADD CONSTRAINT planned_meals_recipe_id_fkey
        FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE RESTRICT
        """
    )

    # Restore household_id for previously-seeded recipes
    op.execute(
        """
        UPDATE recipes
        SET household_id = '00000000-0000-0000-0000-000000000001'::uuid
        WHERE household_id IS NULL
        """
    )

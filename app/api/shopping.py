"""Shopping list and excluded ingredients routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.db import crud
from app.db.engine import get_db
from app.shopping_list import ShoppingListItem

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_plan_id(db: AsyncSession):
    """Helper: return current plan_id or raise 404."""
    _, plan_id, _wsd = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)
    if plan_id is None:
        raise HTTPException(404, detail="No shopping list available")
    return plan_id


@router.post("/shopping-list/update-item")
async def update_shopping_item(request: Request, db: AsyncSession = Depends(get_db)):
    """Update quantity or name of a shopping list item."""
    logger.debug("Updating shopping list item")
    plan_id = await _get_plan_id(db)
    sl = await crud.get_shopping_list(db, plan_id)

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    item_index = data.get("index")
    if item_index is None:
        raise HTTPException(400, detail="Missing item index")
    if item_index < 0 or item_index >= len(sl.items):
        raise HTTPException(400, detail="Invalid item index")

    item = sl.items[item_index]

    new_quantity = data.get("quantity")
    if new_quantity is not None:
        try:
            item.quantity = float(new_quantity)
        except ValueError:
            raise HTTPException(400, detail="Invalid quantity") from None

    new_name = data.get("name")
    if new_name is not None:
        item.item = new_name.strip()

    await crud.save_shopping_list(db, plan_id, sl)

    return {
        "success": True,
        "message": "Item updated",
        "item": {
            "item": item.item,
            "quantity": item.quantity,
            "unit": item.unit,
            "category": item.category,
        },
    }


@router.post("/shopping-list/delete-item")
async def delete_shopping_item(request: Request, db: AsyncSession = Depends(get_db)):
    """Delete an item from the shopping list."""
    logger.debug("Deleting shopping list item")
    plan_id = await _get_plan_id(db)
    sl = await crud.get_shopping_list(db, plan_id)

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    item_index = data.get("index")
    if item_index is None:
        raise HTTPException(400, detail="Missing item index")
    if item_index < 0 or item_index >= len(sl.items):
        raise HTTPException(400, detail="Invalid item index")

    deleted_item = sl.items.pop(item_index)
    await crud.save_shopping_list(db, plan_id, sl)

    return {
        "success": True,
        "message": f"Deleted {deleted_item.item}",
        "deleted_item": deleted_item.item,
    }


@router.post("/shopping-list/add-item")
async def add_shopping_item(request: Request, db: AsyncSession = Depends(get_db)):
    """Add a custom item to the shopping list."""
    logger.debug("Adding custom item to shopping list")
    plan_id = await _get_plan_id(db)
    sl = await crud.get_shopping_list(db, plan_id)

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    item_name = data.get("name")
    quantity = data.get("quantity", 1)
    unit = data.get("unit", "")
    raw_category = data.get("category", "other")

    if not item_name or not item_name.strip():
        raise HTTPException(400, detail="Item name is required")

    try:
        quantity = float(quantity)
        if quantity <= 0:
            raise HTTPException(400, detail="Quantity must be positive")
    except ValueError:
        raise HTTPException(400, detail="Invalid quantity") from None

    from app.ingredient_normalizer import canonicalise_category
    category = canonicalise_category(raw_category)

    new_item = ShoppingListItem(
        item=item_name.strip(),
        quantity=quantity,
        unit=unit.strip(),
        category=category,
    )
    sl.items.append(new_item)
    sl.items.sort(key=lambda x: (x.category, x.item))
    await crud.save_shopping_list(db, plan_id, sl)

    return {
        "success": True,
        "message": f"Added {item_name}",
        "item": {
            "item": new_item.item,
            "quantity": new_item.quantity,
            "unit": new_item.unit,
            "category": new_item.category,
        },
    }


@router.get("/excluded-ingredients")
async def get_excluded_ingredients(db: AsyncSession = Depends(get_db)):
    """Return the list of excluded ingredients."""
    logger.debug("Fetching excluded ingredients")
    return await crud.get_excluded_ingredients(db, config.DEFAULT_HOUSEHOLD_ID)


@router.post("/excluded-ingredients")
async def update_excluded_ingredients(
    request: Request, db: AsyncSession = Depends(get_db)
):
    """Replace the excluded ingredients list."""
    logger.info("Updating excluded ingredients list")
    data = await request.json()
    items = data.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(400, detail="items must be a list")
    await crud.save_excluded_ingredients(
        db, config.DEFAULT_HOUSEHOLD_ID, [str(i).strip() for i in items if str(i).strip()]
    )
    return {"success": True}

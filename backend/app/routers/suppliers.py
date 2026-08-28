from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from backend.app.database import get_db
from backend.app.models.supplier import Supplier
from backend.app.schemas.supplier import SupplierCreate, SupplierUpdate, SupplierResponse
from backend.app.routers.ws import ws_manager

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])


@router.get("", response_model=List[SupplierResponse])
async def get_suppliers(
    active_only: bool = True,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Returns list of suppliers from PostgreSQL."""
    query = select(Supplier)
    if active_only:
        query = query.where(Supplier.is_active != False)
    if search:
        query = query.where(Supplier.name.ilike(f"%{search.strip()}%"))
    query = query.order_by(Supplier.name.asc())

    res = await db.execute(query)
    suppliers = res.scalars().all()
    return suppliers


@router.post("", response_model=SupplierResponse)
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db)
):
    """Registers a new supplier in PostgreSQL."""
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Supplier name cannot be empty.")

    # Check for duplicate
    existing = await db.execute(select(Supplier).where(Supplier.name.ilike(clean_name)))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail=f"Supplier '{clean_name}' already exists.")

    supp_id = payload.id or f"SUPP-{uuid.uuid4().hex[:6].upper()}"
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    supplier = Supplier(
        id=supp_id,
        name=clean_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        lead_time_days=int(payload.lead_time_days or 5),
        category=payload.category,
        status=str(payload.status or "Active"),
        is_active=True,
        created_at=now_utc
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    await ws_manager.broadcast({
        "event": "SUPPLIER_CREATED",
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "timestamp": now_utc.isoformat()
    })

    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Updates supplier parameters in PostgreSQL."""
    res = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = res.scalars().first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    if payload.name is not None:
        supplier.name = payload.name.strip()
    if payload.contact_email is not None:
        supplier.contact_email = payload.contact_email
    if payload.contact_phone is not None:
        supplier.contact_phone = payload.contact_phone
    if payload.lead_time_days is not None:
        supplier.lead_time_days = int(payload.lead_time_days)
    if payload.category is not None:
        supplier.category = payload.category
    if payload.status is not None:
        supplier.status = str(payload.status)
    if payload.is_active is not None:
        supplier.is_active = bool(payload.is_active)

    await db.commit()
    await db.refresh(supplier)

    await ws_manager.broadcast({
        "event": "SUPPLIER_UPDATED",
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return supplier


@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Deletes or deactivates a supplier in PostgreSQL."""
    res = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = res.scalars().first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    supplier_name = supplier.name
    await db.delete(supplier)
    await db.commit()

    await ws_manager.broadcast({
        "event": "SUPPLIER_DELETED",
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"success": True, "message": f"Supplier '{supplier_name}' successfully removed from database."}

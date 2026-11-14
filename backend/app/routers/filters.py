"""Saved filters: create, list, update, delete reusable search presets."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SavedFilter
from app.schemas import SavedFilterIn, SavedFilterOut

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("", response_model=list[SavedFilterOut])
def list_filters(db: Session = Depends(get_db)) -> list[SavedFilter]:
    return db.query(SavedFilter).order_by(SavedFilter.updated_at.desc()).all()


@router.post("", response_model=SavedFilterOut, status_code=201)
def create_filter(payload: SavedFilterIn, db: Session = Depends(get_db)) -> SavedFilter:
    record = SavedFilter(name=payload.name.strip(), description=payload.description, params=payload.params)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A filter with this name already exists.")
    db.refresh(record)
    return record


@router.get("/{filter_id}", response_model=SavedFilterOut)
def get_filter(filter_id: str, db: Session = Depends(get_db)) -> SavedFilter:
    record = db.get(SavedFilter, filter_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Filter not found.")
    return record


@router.put("/{filter_id}", response_model=SavedFilterOut)
def update_filter(filter_id: str, payload: SavedFilterIn, db: Session = Depends(get_db)) -> SavedFilter:
    record = db.get(SavedFilter, filter_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Filter not found.")
    record.name = payload.name.strip()
    record.description = payload.description
    record.params = payload.params
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A filter with this name already exists.")
    db.refresh(record)
    return record


@router.delete("/{filter_id}", status_code=204)
def delete_filter(filter_id: str, db: Session = Depends(get_db)) -> None:
    record = db.get(SavedFilter, filter_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Filter not found.")
    db.delete(record)
    db.commit()

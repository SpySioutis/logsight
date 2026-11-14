"""Import endpoints: upload log files, history, deletion."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import import_service
from app.database import get_db
from app.models import Import
from app.schemas import ImportCreateOut, ImportOut

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload", response_model=ImportCreateOut, status_code=201)
def upload_log(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportCreateOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    record, duplicate = import_service.import_upload(db, file)
    if record.status == "failed":
        raise HTTPException(status_code=422, detail=record.error_message or "Import failed.")
    payload = ImportOut.model_validate(record).model_dump()
    return ImportCreateOut(**payload, duplicate=duplicate)


@router.get("", response_model=list[ImportOut])
def list_imports(db: Session = Depends(get_db)) -> list[Import]:
    return db.query(Import).order_by(Import.started_at.desc()).all()


@router.get("/{import_id}", response_model=ImportOut)
def get_import(import_id: str, db: Session = Depends(get_db)) -> Import:
    record = db.get(Import, import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Import not found.")
    return record


@router.delete("/{import_id}", status_code=204)
def delete_import(import_id: str, db: Session = Depends(get_db)) -> None:
    record = db.get(Import, import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Import not found.")
    db.delete(record)
    db.commit()

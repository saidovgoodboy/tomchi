from contextlib import asynccontextmanager
from datetime import datetime
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crud import (
    DEFAULT_BOX_ID,
    DEFAULT_BOX_NAME,
    create_box,
    ensure_box,
    get_bonus_settings,
    get_display_text,
    get_stats,
    is_valid_plate,
    list_boxes,
    list_recent_cars,
    list_recent_visits,
    press_bonus,
    normalize_plate,
    process_plate_detection,
    update_bonus_settings,
)
from app.db import Base, SessionLocal, engine, get_db
from app.image_store import (
    cleanup_detection_images,
    live_frame_path,
    save_detection_image,
    save_live_frame,
)
from app.models import DetectionRecord, DeviceLog, Visit, WashBox
from app.schemas import (
    BonusPressRequest,
    BonusPressResponse,
    DisplayResponse,
    PlateDetectionRequest,
    StatsOut,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("visits")}
        if "box_id" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE visits ADD COLUMN box_id VARCHAR(40)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_visits_box_id ON visits (box_id)"))
        columns = {column["name"] for column in inspect(engine).get_columns("visits")}
        if "plate_override" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE visits ADD COLUMN plate_override VARCHAR(20)"))
    with SessionLocal() as db:
        if db.get(WashBox, DEFAULT_BOX_ID) is None:
            db.add(WashBox(id=DEFAULT_BOX_ID, name=DEFAULT_BOX_NAME))
            db.commit()
        db.execute(
            text("UPDATE visits SET box_id = :box_id WHERE box_id IS NULL"),
            {"box_id": DEFAULT_BOX_ID},
        )
        get_bonus_settings(db)
        cleanup_detection_images(
            db,
            settings.storage_dir,
            settings.image_retention_days,
            settings.image_storage_max_bytes,
        )
        db.commit()
    yield


app = FastAPI(title="Tomchi API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def enforce_device_key(header_value: str | None, required: bool = False):
    if header_value is None and not required:
        return
    if header_value != settings.device_key:
        raise HTTPException(status_code=401, detail="Invalid device key")


class BonusSettingsUpdate(BaseModel):
    bonus_amount: int | None = Field(default=None, ge=1000, multiple_of=1000)
    bonus_per_press: int | None = Field(default=None, ge=1000, le=100000, multiple_of=1000)
    bonus_every_visits: int | None = Field(default=None, ge=1)


class BoxCreate(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)


class DetectionPlateCorrection(BaseModel):
    plate: str = Field(min_length=8, max_length=20)


class VisitPlateUpdate(BaseModel):
    plate: str = Field(min_length=8, max_length=20)


@app.get("/health")
def health():
    return {"ok": True, "service": "tomchi-backend"}


@app.get("/api/stats", response_model=StatsOut)
def api_stats(db: Session = Depends(get_db), x_device_key: str | None = Header(default=None, alias="X-Device-Key")):
    enforce_device_key(x_device_key)
    return get_stats(db)


@app.get("/api/settings")
def api_settings(
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key)
    return get_bonus_settings(db)


@app.put("/api/settings")
def api_update_settings(
    body: BonusSettingsUpdate,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key)
    return update_bonus_settings(
        db,
        body.bonus_amount,
        body.bonus_per_press,
        body.bonus_every_visits,
    )


@app.get("/api/boxes")
def api_boxes(
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key)
    return list_boxes(db)


@app.post("/api/boxes")
def api_create_box(
    payload: BoxCreate,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key)
    try:
        return create_box(db, payload.id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/visits")
def api_visits(
    limit: int = Query(10, ge=1, le=100),
    box_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key)
    return list_recent_visits(db, limit=limit, box_id=box_id)


@app.put("/api/visits/{visit_id}/plate")
def api_update_visit_plate(
    visit_id: int,
    payload: VisitPlateUpdate,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key, required=True)
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")

    plate = normalize_plate(payload.plate)
    if not is_valid_plate(plate):
        raise HTTPException(status_code=400, detail="Invalid plate format")

    visit.plate_override = plate
    db.query(DetectionRecord).filter(DetectionRecord.visit_id == visit.id).update(
        {
            DetectionRecord.plate: plate,
            DetectionRecord.updated_at: datetime.utcnow(),
        },
        synchronize_session=False,
    )
    db.commit()
    return {"ok": True, "visit_id": visit.id, "plate": plate}


@app.get("/api/cars")
def api_cars(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db), x_device_key: str | None = Header(default=None, alias="X-Device-Key")):
    enforce_device_key(x_device_key)
    return list_recent_cars(db, limit=limit)


@app.post("/api/detect")
def api_detect(
    payload: PlateDetectionRequest,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id"),
):
    enforce_device_key(x_device_key, required=True)
    try:
        return process_plate_detection(db, payload.plate, x_box_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/display", response_model=DisplayResponse)
def api_display(
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id"),
):
    enforce_device_key(x_device_key, required=True)
    try:
        display = get_display_text(db, x_box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DisplayResponse(**display)


@app.post("/api/bonus/press", response_model=BonusPressResponse)
def api_bonus_press(
    payload: BonusPressRequest,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id"),
):
    enforce_device_key(x_device_key, required=True)
    try:
        result = press_bonus(db, payload.plate, x_box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BonusPressResponse(**result)


@app.post("/api/detect-image")
async def api_detect_image(
    image: UploadFile = File(...),
    event_id: str = Form(..., min_length=1, max_length=100),
    frame_index: int = Form(0, ge=0, le=4),
    frame_count: int = Form(1, ge=1, le=5),
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id"),
):
    enforce_device_key(x_device_key, required=True)
    if not event_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid event ID")
    if frame_index >= frame_count:
        raise HTTPException(status_code=400, detail="Frame index must be smaller than frame count")
    if image.content_type != "image/jpeg":
        raise HTTPException(status_code=415, detail="Only JPEG images are supported")

    content = await image.read(1_048_577)
    if not content:
        raise HTTPException(status_code=400, detail="Empty image")
    if len(content) > 1_048_576:
        raise HTTPException(status_code=413, detail="Image exceeds 1 MiB limit")
    if not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="Invalid JPEG image")

    try:
        box = ensure_box(db, x_box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        detection = (
            db.query(DetectionRecord)
            .filter(
                DetectionRecord.box_id == box.id,
                DetectionRecord.event_key == event_id,
            )
            .first()
        )
        if detection is None:
            detection = DetectionRecord(
                box_id=box.id,
                event_key=event_id,
                image_key=uuid4().hex,
                frame_index=-1,
                frame_count=frame_count,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(detection)
            db.flush()

        if frame_index >= detection.frame_index:
            save_detection_image(settings.storage_dir, detection.image_key, content)
            detection.frame_index = frame_index
            detection.frame_count = frame_count
            detection.updated_at = datetime.utcnow()
            db.add(DeviceLog(
                event="image_received",
                payload=f"{box.id}:{detection.id}:{frame_index + 1}/{frame_count}",
            ))
        db.commit()
        if frame_index + 1 == frame_count:
            cleanup_detection_images(
                db,
                settings.storage_dir,
                settings.image_retention_days,
                settings.image_storage_max_bytes,
            )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "detected": False,
        "detection_id": detection.id,
        "frame_index": frame_index,
        "frame_count": frame_count,
        "box_id": x_box_id,
        "status": detection.status,
        "plate": detection.plate,
        "message": "Image saved; ANPR/OCR provider is not configured",
    }


@app.post("/api/boxes/{box_id}/live-frame", status_code=204)
async def upload_live_frame(
    box_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key, required=True)
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "image/jpeg":
        raise HTTPException(status_code=415, detail="Expected image/jpeg")
    try:
        box = ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 1_048_576:
            raise HTTPException(status_code=413, detail="Live image exceeds 1 MiB limit")
    if not content or not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="Invalid JPEG image")
    try:
        save_live_frame(settings.storage_dir, box.id, bytes(content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@app.get("/api/boxes/{box_id}/live-frame")
def get_live_frame(
    box_id: str,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key, required=True)
    try:
        box = ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = live_frame_path(settings.storage_dir, box.id)
    try:
        modified_at = path.stat().st_mtime
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No live frame available for this box")
    if time.time() - modified_at > 15:
        raise HTTPException(status_code=404, detail="Live preview is stale")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/detections")
def list_detections(
    limit: int = Query(30, ge=1, le=100),
    box_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key, required=True)
    cleanup_detection_images(
        db,
        settings.storage_dir,
        settings.image_retention_days,
        settings.image_storage_max_bytes,
    )
    query = db.query(DetectionRecord)
    if box_id:
        query = query.filter(DetectionRecord.box_id == box_id)
    detections = query.order_by(DetectionRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "id": item.id,
            "box_id": item.box_id,
            "plate": item.plate,
            "status": item.status,
            "frame_index": item.frame_index,
            "frame_count": item.frame_count,
            "created_at": item.created_at.isoformat(),
            "image_url": f"/api/detections/{item.id}/image",
        }
        for item in detections
    ]


@app.get("/api/detections/{detection_id}/image")
def get_detection_image(
    detection_id: int,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key, required=True)
    detection = db.get(DetectionRecord, detection_id)
    if detection is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    path = settings.storage_dir / "detections" / f"{detection.image_key}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Detection image expired or missing")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})


@app.put("/api/detections/{detection_id}/plate")
def correct_detection_plate(
    detection_id: int,
    payload: DetectionPlateCorrection,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    enforce_device_key(x_device_key, required=True)
    detection = db.get(DetectionRecord, detection_id)
    if detection is None:
        raise HTTPException(status_code=404, detail="Detection not found")

    plate = normalize_plate(payload.plate)
    if not is_valid_plate(plate):
        raise HTTPException(status_code=400, detail="Invalid plate format")
    if detection.visit_id is not None and detection.plate != plate:
        raise HTTPException(
            status_code=409,
            detail="This detection is already registered; changing its plate would alter visit history",
        )

    result = None
    if detection.visit_id is None:
        try:
            result = process_plate_detection(db, plate, detection.box_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        detection.plate = plate
        detection.visit_id = result["visit_id"]
        detection.status = "confirmed"
        detection.updated_at = datetime.utcnow()
        db.commit()
    return {
        "ok": True,
        "detection_id": detection.id,
        "plate": detection.plate,
        "visit_id": detection.visit_id,
        "visit_no": result["visit_no"] if result else detection.visit.visit_no,
        "status": detection.status,
    }

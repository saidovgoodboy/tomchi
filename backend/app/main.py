from contextlib import asynccontextmanager
from datetime import date, timedelta
import json
import logging
import time
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.anpr import (
    OCRProcessingError,
    OCRUnavailableError,
    is_ocr_available,
    recognize_plate,
)
from app.auth import (
    authenticate_admin,
    enforce_login_rate_limit,
    require_admin_token,
    require_device_key,
)
from app.capture import CaptureSession, Decision
from app.config import get_settings
from app.crud import (
    DEFAULT_DISPLAY_COPY,
    DEFAULT_BOX_ID,
    DEFAULT_BOX_NAME,
    consume_box_test_pulse,
    create_box,
    daily_report,
    day_bounds,
    export_visits_csv,
    ensure_box,
    finish_box_test,
    get_box_test_status,
    get_bonus_settings,
    get_display_text,
    get_stats,
    is_valid_plate,
    list_boxes,
    list_recent_cars,
    list_recent_logs,
    list_recent_pulses,
    list_recent_visits,
    press_bonus,
    queue_box_test_pulse,
    start_box_test,
    normalize_plate,
    process_plate_detection,
    refund_pulse,
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
from app.timeutil import iso_utc, utcnow
from app.schemas import (
    BonusPressRequest,
    BonusPressResponse,
    DisplayResponse,
    PlateDetectionRequest,
    StatsOut,
    TestPulseRequest,
)

settings = get_settings()
logger = logging.getLogger(__name__)


# Har motion event uchun bitta CaptureSession. Kalit: "<box_id>:<event_id>".
# Single-process uvicorn uchun yetarli; sessiya tugagach eski yozuvlar tozalanadi.
_capture_sessions: dict[str, CaptureSession] = {}
_capture_sessions_lock = Lock()


def _session_key(box_id: str, event_id: str) -> str:
    return f"{box_id}:{event_id}"


def _get_or_create_capture_session(box_id: str, event_id: str) -> CaptureSession:
    key = _session_key(box_id, event_id)
    now = time.monotonic()
    with _capture_sessions_lock:
        session = _capture_sessions.get(key)
        if session is None:
            # Eski tugallangan sessiyalarni tozalash (xotira o'sib ketmasin).
            expiry = now - settings.anpr_max_session_seconds * 3
            for stale_key, stale in list(_capture_sessions.items()):
                if stale.finished and stale.started_at < expiry:
                    _capture_sessions.pop(stale_key, None)
            session = CaptureSession(
                event_id=key,
                min_frames=settings.anpr_min_frames,
                window_size=settings.anpr_window_size,
                agreement_threshold=settings.anpr_agreement_threshold,
                max_frames=settings.anpr_max_frames,
                max_session_seconds=settings.anpr_max_session_seconds,
                no_plate_abort_streak=settings.anpr_no_plate_abort_streak,
            )
            _capture_sessions[key] = session
        return session


def _apply_capture_decision(db: Session, detection: DetectionRecord, decision: Decision, box_id: str) -> None:
    """CaptureSession qarorini detection va visitga ko'chiradi."""
    if decision.status == "finalized" and detection.visit_id is None:
        result = process_plate_detection(db, decision.plate, box_id)
        detection.plate = decision.plate
        detection.visit_id = result["visit_id"]
        detection.status = "confirmed"
        detection.auto_confirmed = 1
    elif decision.status == "aborted" and detection.visit_id is None:
        detection.status = "aborted"
    elif decision.status == "pending" and detection.visit_id is None:
        # Raqam o'qilgan, lekin 80% ga yetmagan — admin tekshirishi uchun qoladi.
        detection.status = "pending"

    if decision.terminal:
        detection.agreement = decision.agreement
        detection.votes = decision.votes
        detection.updated_at = utcnow()


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
        columns = {column["name"] for column in inspect(engine).get_columns("detections")}
        if "ocr_confidence" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE detections ADD COLUMN ocr_confidence FLOAT"))
        columns = {column["name"] for column in inspect(engine).get_columns("bonus_pulses")}
        with engine.begin() as connection:
            if "press_id" not in columns:
                connection.execute(text("ALTER TABLE bonus_pulses ADD COLUMN press_id VARCHAR(64)"))
            if "refunded_at" not in columns:
                connection.execute(text("ALTER TABLE bonus_pulses ADD COLUMN refunded_at DATETIME"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_bonus_pulses_press_id "
                    "ON bonus_pulses (press_id)"
                )
            )
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


is_production = settings.app_env.lower() in {"prod", "production"}
app = FastAPI(
    title="Tomchi API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

allowed_origins = [
    origin.strip()
    for origin in settings.admin_origins.split(",")
    if origin.strip()
]
if "*" in allowed_origins:
    raise ValueError("ADMIN_ORIGINS must list explicit origins, not '*'.")
if is_production:
    allowed_hosts = [
        host.strip()
        for host in settings.allowed_hosts.split(",")
        if host.strip()
    ]
    if not allowed_hosts or "*" in allowed_hosts:
        raise ValueError("Production requires explicit ALLOWED_HOSTS.")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BonusSettingsUpdate(BaseModel):
    bonus_amount: int | None = Field(default=None, ge=1000, multiple_of=1000)
    bonus_per_press: int | None = Field(default=None, ge=1000, le=100000, multiple_of=1000)
    bonus_every_visits: int | None = Field(default=None, ge=1)
    pulse_polarity: Literal["HIGH", "LOW"] | None = None
    pulse_frequency_ms: Literal[50, 100, 200] | None = None
    display_idle_text: str | None = Field(default=None, min_length=1, max_length=48)
    display_visit_label: str | None = Field(default=None, min_length=1, max_length=16)
    display_reward_label: str | None = Field(default=None, min_length=1, max_length=16)
    display_remaining_label: str | None = Field(default=None, min_length=1, max_length=24)
    display_finished_text: str | None = Field(default=None, min_length=1, max_length=32)
    display_currency_label: str | None = Field(default=None, min_length=1, max_length=12)

    @field_validator(*DEFAULT_DISPLAY_COPY)
    @classmethod
    def display_copy_uses_printable_ascii(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or not all(32 <= ord(char) <= 126 for char in value):
            raise ValueError("P10 display text must use printable ASCII characters")
        return value


class BoxCreate(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)


class DetectionPlateCorrection(BaseModel):
    plate: str = Field(min_length=8, max_length=20)


class VisitPlateUpdate(BaseModel):
    plate: str = Field(min_length=8, max_length=20)


class AdminLogin(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:  # noqa: BLE001 - health endpoint reports instead of crashing
        logger.exception("Health check database query failed")
        database_ok = False
    return {
        "ok": database_ok,
        "service": "tomchi-backend",
        "database_ok": database_ok,
        "anpr_enabled": settings.anpr_enabled,
        "anpr_available": settings.anpr_enabled and is_ocr_available(settings.anpr_tesseract_cmd),
    }


@app.post("/api/auth/login")
def api_admin_login(payload: AdminLogin, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(client_ip)
    return authenticate_admin(payload.username, payload.password)


@app.get("/api/stats", response_model=StatsOut)
def api_stats(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    return get_stats(db)


@app.get("/api/settings")
def api_settings(
    box_id: str = Query(default=DEFAULT_BOX_ID, min_length=1, max_length=40),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return get_bonus_settings(db, box_id)


@app.put("/api/settings")
def api_update_settings(
    body: BonusSettingsUpdate,
    box_id: str = Query(default=DEFAULT_BOX_ID, min_length=1, max_length=40),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = update_bonus_settings(
        db,
        body.bonus_amount,
        body.bonus_per_press,
        body.bonus_every_visits,
        body.pulse_polarity,
        body.pulse_frequency_ms,
        box_id,
        display_copy={
            key: getattr(body, key)
            for key in DEFAULT_DISPLAY_COPY
        },
    )
    db.add(
        DeviceLog(
            event="admin_settings_update",
            payload=(
                f"{box_id}:amount={result['bonus_amount']},"
                f"per_press={result['bonus_per_press']},"
                f"every={result['bonus_every_visits']}"
            ),
        )
    )
    db.commit()
    return result


@app.get("/api/boxes")
def api_boxes(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    return list_boxes(db)


@app.get("/api/boxes/{box_id}/test")
def api_box_test_status(
    box_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        box = ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return get_box_test_status(db, box.id)


@app.post("/api/boxes/{box_id}/test/start")
def api_start_box_test(
    box_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        box = ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return start_box_test(db, box.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/boxes/{box_id}/test/pulses")
def api_queue_box_test_pulse(
    box_id: str,
    payload: TestPulseRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        box = ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return queue_box_test_pulse(db, box.id, payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/boxes/{box_id}/test/finish")
def api_finish_box_test(
    box_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        box = ensure_box(db, box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return finish_box_test(db, box.id)


@app.post("/api/boxes")
def api_create_box(
    payload: BoxCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        created = create_box(db, payload.id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.add(DeviceLog(event="admin_box_created", payload=f"{created['id']}:{created['name']}"))
    db.commit()
    return created


@app.get("/api/visits")
def api_visits(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    box_id: str | None = Query(default=None),
    plate: str | None = Query(default=None, max_length=20),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    return list_recent_visits(db, limit=limit, box_id=box_id, offset=offset, plate=plate)


@app.put("/api/visits/{visit_id}/plate")
def api_update_visit_plate(
    visit_id: int,
    payload: VisitPlateUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")

    plate = normalize_plate(payload.plate)
    if not is_valid_plate(plate):
        raise HTTPException(status_code=400, detail="Invalid plate format")

    visit_plate_before = visit.plate_override or visit.car.plate
    visit.plate_override = plate
    db.query(DetectionRecord).filter(DetectionRecord.visit_id == visit.id).update(
        {
            DetectionRecord.plate: plate,
            DetectionRecord.updated_at: utcnow(),
        },
        synchronize_session=False,
    )
    db.add(
        DeviceLog(
            event="admin_visit_plate_update",
            payload=f"{visit.id}:{visit_plate_before}->{plate}",
        )
    )
    db.commit()
    return {"ok": True, "visit_id": visit.id, "plate": plate}


@app.get("/api/cars")
def api_cars(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    plate: str | None = Query(default=None, max_length=20),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    return list_recent_cars(db, limit=limit, offset=offset, plate=plate)


@app.post("/api/detect")
def api_detect(
    payload: PlateDetectionRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id"),
):
    require_admin_token(authorization)
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
    require_device_key(x_device_key)
    try:
        display = get_display_text(db, x_box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    settings = get_bonus_settings(db, x_box_id)
    test_pulse = consume_box_test_pulse(db, x_box_id)
    return DisplayResponse(
        **display,
        pulse_polarity=settings["pulse_polarity"],
        pulse_frequency_ms=settings["pulse_frequency_ms"],
        **{
            key: settings[key]
            for key in DEFAULT_DISPLAY_COPY
        },
        **test_pulse,
    )


@app.post("/api/bonus/press", response_model=BonusPressResponse)
def api_bonus_press(
    payload: BonusPressRequest,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id"),
):
    require_device_key(x_device_key)
    try:
        result = press_bonus(db, payload.plate, x_box_id, payload.press_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BonusPressResponse(**result)


@app.get("/api/pulses")
def api_pulses(
    limit: int = Query(20, ge=1, le=100),
    box_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    return list_recent_pulses(db, limit=limit, box_id=box_id)


@app.get("/api/reports/daily")
def api_daily_report(
    day: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        target = date.fromisoformat(day) if day else (
            utcnow() + timedelta(minutes=settings.report_timezone_offset_minutes)
        ).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date, expected YYYY-MM-DD") from exc
    return daily_report(db, target, settings.report_timezone_offset_minutes)


@app.get("/api/visits/export.csv")
def api_export_visits(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    offset = timedelta(minutes=settings.report_timezone_offset_minutes)
    today = (utcnow() + offset).date()
    try:
        first = date.fromisoformat(date_from) if date_from else today
        last = date.fromisoformat(date_to) if date_to else today
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date, expected YYYY-MM-DD") from exc
    if last < first:
        raise HTTPException(status_code=400, detail="'to' must not be earlier than 'from'")
    start, _ = day_bounds(first, settings.report_timezone_offset_minutes)
    _, end = day_bounds(last, settings.report_timezone_offset_minutes)
    csv_text = export_visits_csv(db, start, end, settings.report_timezone_offset_minutes)
    filename = f"tomchi-visits-{first.isoformat()}_{last.isoformat()}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/logs")
def api_logs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    return list_recent_logs(db, limit=limit)


@app.post("/api/pulses/{pulse_id}/refund")
def api_refund_pulse(
    pulse_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    try:
        return refund_pulse(db, pulse_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
    require_device_key(x_device_key)
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
        ocr_status = "disabled" if not settings.anpr_enabled else "no_match"
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
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(detection)
            db.flush()

        if frame_index >= detection.frame_index:
            save_detection_image(settings.storage_dir, detection.image_key, content)
            detection.frame_index = frame_index
            detection.frame_count = frame_count
            detection.updated_at = utcnow()
            db.add(DeviceLog(
                event="image_received",
                payload=f"{box.id}:{detection.id}:{frame_index + 1}/{frame_count}",
            ))
            if settings.anpr_enabled:
                try:
                    candidate = await run_in_threadpool(
                        recognize_plate,
                        content,
                        settings.anpr_tesseract_cmd,
                        settings.anpr_timeout_seconds,
                    )
                except OCRUnavailableError as exc:
                    logger.error("ANPR OCR unavailable for detection %s: %s", detection.id, exc)
                    ocr_status = "unavailable"
                except OCRProcessingError as exc:
                    logger.warning("ANPR OCR failed for detection %s: %s", detection.id, exc)
                    ocr_status = "error"
                else:
                    if candidate is None:
                        ocr_status = "no_match"
                    elif candidate.confidence < settings.anpr_min_confidence:
                        ocr_status = "low_confidence"
                    else:
                        ocr_status = "recognized"
                        if (
                            detection.visit_id is None
                            and detection.status != "confirmed"
                            and (
                                detection.ocr_confidence is None
                                or candidate.confidence > detection.ocr_confidence
                            )
                        ):
                            detection.plate = candidate.plate
                            detection.ocr_confidence = candidate.confidence
        else:
            ocr_status = "stale_frame"
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
        "recognized": detection.plate is not None,
        "ocr_status": ocr_status,
        "plate": detection.plate,
        "ocr_confidence": detection.ocr_confidence,
    }


@app.post("/api/boxes/{box_id}/live-frame", status_code=204)
async def upload_live_frame(
    box_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
):
    require_device_key(x_device_key)
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
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
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
    offset: int = Query(0, ge=0, le=100000),
    box_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
    cleanup_detection_images(
        db,
        settings.storage_dir,
        settings.image_retention_days,
        settings.image_storage_max_bytes,
    )
    query = db.query(DetectionRecord)
    if box_id:
        query = query.filter(DetectionRecord.box_id == box_id)
    detections = query.order_by(DetectionRecord.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": item.id,
            "box_id": item.box_id,
            "plate": item.plate,
            "ocr_confidence": item.ocr_confidence,
            "status": item.status,
            "frame_index": item.frame_index,
            "frame_count": item.frame_count,
            "created_at": iso_utc(item.created_at),
            "image_url": f"/api/detections/{item.id}/image",
        }
        for item in detections
    ]


@app.get("/api/detections/{detection_id}/image")
def get_detection_image(
    detection_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
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
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    require_admin_token(authorization)
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
        detection.updated_at = utcnow()
        db.commit()
    return {
        "ok": True,
        "detection_id": detection.id,
        "plate": detection.plate,
        "visit_id": detection.visit_id,
        "visit_no": result["visit_no"] if result else detection.visit.visit_no,
        "status": detection.status,
    }

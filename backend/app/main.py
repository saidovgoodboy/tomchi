from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crud import (
    DEFAULT_BOX_ID,
    DEFAULT_BOX_NAME,
    create_box,
    get_bonus_settings,
    get_display_text,
    get_stats,
    list_boxes,
    list_recent_cars,
    list_recent_visits,
    press_bonus,
    process_plate_detection,
    update_bonus_settings,
)
from app.db import Base, SessionLocal, engine, get_db
from app.models import WashBox
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
    with SessionLocal() as db:
        if db.get(WashBox, DEFAULT_BOX_ID) is None:
            db.add(WashBox(id=DEFAULT_BOX_ID, name=DEFAULT_BOX_NAME))
            db.commit()
        db.execute(
            text("UPDATE visits SET box_id = :box_id WHERE box_id IS NULL"),
            {"box_id": DEFAULT_BOX_ID},
        )
        get_bonus_settings(db)
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


def enforce_device_key(header_value: str | None):
    if header_value is None:
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
    enforce_device_key(x_device_key)
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
    enforce_device_key(x_device_key)
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
    enforce_device_key(x_device_key)
    try:
        result = press_bonus(db, payload.plate, x_box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BonusPressResponse(**result)


@app.post("/api/detect-image")
def api_detect_image(payload: PlateDetectionRequest, db: Session = Depends(get_db), x_device_key: str | None = Header(default=None, alias="X-Device-Key"), x_box_id: str = Header(default=DEFAULT_BOX_ID, alias="X-Box-Id")):
    enforce_device_key(x_device_key)
    return process_plate_detection(db, payload.plate, x_box_id)

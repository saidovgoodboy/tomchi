from datetime import timedelta
import re

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.timeutil import iso_utc, utcnow
from app.models import (
    AppSetting,
    BonusPulse,
    BoxTestState,
    Car,
    DetectionRecord,
    DeviceLog,
    Visit,
    WashBox,
)

DEFAULT_BOX_ID = "box-1"
DEFAULT_BOX_NAME = "Box 1"
PULSE_VALUE = 1_000
DEFAULT_SETTINGS = {
    "bonus_amount": 20_000,
    "bonus_per_press": 5_000,
    "bonus_every_visits": 10,
}
DEFAULT_PULSE_SETTINGS = {
    "pulse_polarity": "HIGH",
    "pulse_frequency_ms": 100,
}
DEFAULT_DISPLAY_COPY = {
    "display_idle_text": "AVTOMOBIL YO'Q",
    "display_visit_label": "KELISH",
    "display_reward_label": "MUKOFOT",
    "display_remaining_label": "MUKOFOT QOLDI",
    "display_finished_text": "MUKOFOT TUGADI",
    "display_currency_label": "SO'M",
}
PLATE_PATTERN = re.compile(r"(?:[0-9]{2}[A-Z][0-9]{3}[A-Z]{2}|[0-9]{5}[A-Z]{3})")


def visit_plate(visit: Visit) -> str:
    return visit.plate_override or visit.car.plate


def get_bonus_settings(
    db: Session,
    box_id: str = DEFAULT_BOX_ID,
) -> dict[str, int | str]:
    values = {row.key: row.value for row in db.query(AppSetting).all()}
    result = {}
    created_default = False
    for key, default in DEFAULT_SETTINGS.items():
        if key in values:
            result[key] = int(values[key]) if isinstance(default, int) else values[key]
        else:
            result[key] = default
        if key not in values:
            db.add(AppSetting(key=key, value=str(default)))
            created_default = True
    for key, default in DEFAULT_PULSE_SETTINGS.items():
        storage_key = f"box:{box_id}:{key}"
        value = values.get(storage_key)
        if value is None:
            value = values.get(key, str(default))
            db.add(AppSetting(key=storage_key, value=value))
            created_default = True
        result[key] = int(value) if isinstance(default, int) else value
    for key, default in DEFAULT_DISPLAY_COPY.items():
        storage_key = f"box:{box_id}:{key}"
        value = values.get(storage_key)
        if value is None:
            value = default
            db.add(AppSetting(key=storage_key, value=value))
            created_default = True
        result[key] = value
    if created_default:
        db.flush()
    return result


def update_bonus_settings(
    db: Session,
    bonus_amount: int | None,
    bonus_per_press: int | None,
    bonus_every_visits: int | None,
    pulse_polarity: str | None,
    pulse_frequency_ms: int | None,
    box_id: str = DEFAULT_BOX_ID,
    display_copy: dict[str, str | None] | None = None,
) -> dict[str, int | str]:
    updates = {
        "bonus_amount": bonus_amount,
        "bonus_per_press": bonus_per_press,
        "bonus_every_visits": bonus_every_visits,
    }
    for key, value in updates.items():
        if value is None:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=str(value)))
        else:
            row.value = str(value)
    pulse_updates = {
        "pulse_polarity": pulse_polarity,
        "pulse_frequency_ms": pulse_frequency_ms,
    }
    for key, value in pulse_updates.items():
        if value is None:
            continue
        storage_key = f"box:{box_id}:{key}"
        row = db.get(AppSetting, storage_key)
        if row is None:
            db.add(AppSetting(key=storage_key, value=str(value)))
        else:
            row.value = str(value)
    for key, value in (display_copy or {}).items():
        if value is None:
            continue
        if key not in DEFAULT_DISPLAY_COPY:
            raise ValueError(f"Unknown display text setting: {key}")
        storage_key = f"box:{box_id}:{key}"
        row = db.get(AppSetting, storage_key)
        if row is None:
            db.add(AppSetting(key=storage_key, value=value))
        else:
            row.value = value
    db.flush()
    db.commit()
    return get_bonus_settings(db, box_id)


def ensure_box(db: Session, box_id: str = DEFAULT_BOX_ID) -> WashBox:
    box_id = (box_id or DEFAULT_BOX_ID).strip()
    box = db.get(WashBox, box_id)
    if box is None and box_id == DEFAULT_BOX_ID:
        box = WashBox(id=DEFAULT_BOX_ID, name=DEFAULT_BOX_NAME)
        db.add(box)
        db.commit()
        db.refresh(box)
    if box is None:
        raise ValueError(f"Unknown box: {box_id}")
    return box


def get_box_test_status(db: Session, box_id: str) -> dict[str, bool | int | None]:
    state = db.get(BoxTestState, box_id)
    return {
        "active": bool(state and state.is_active),
        "pending_amount": state.pending_amount if state else None,
    }


def start_box_test(db: Session, box_id: str) -> dict[str, bool | int | None]:
    ensure_box(db, box_id)
    state = db.get(BoxTestState, box_id)
    if state is not None and state.is_active:
        raise ValueError("Box test is already active")
    if state is None:
        state = BoxTestState(box_id=box_id)
        db.add(state)
    state.is_active = 1
    state.pending_amount = None
    state.pending_pulse_count = None
    db.commit()
    return get_box_test_status(db, box_id)


def queue_box_test_pulse(
    db: Session,
    box_id: str,
    amount: int,
) -> dict[str, bool | int | None]:
    state = db.get(BoxTestState, box_id)
    if state is None or not state.is_active:
        raise ValueError("Box test is not active")
    if state.pending_pulse_count is not None:
        raise ValueError("A test pulse is already waiting for the device")
    state.pending_amount = amount
    state.pending_pulse_count = amount // PULSE_VALUE
    state.updated_at = utcnow()
    db.add(DeviceLog(event="test_pulse_queued", payload=f"{box_id}:{amount}"))
    db.commit()
    return get_box_test_status(db, box_id)


def finish_box_test(db: Session, box_id: str) -> dict[str, bool | int | None]:
    state = db.get(BoxTestState, box_id)
    if state is not None:
        state.is_active = 0
        state.pending_amount = None
        state.pending_pulse_count = None
        state.updated_at = utcnow()
        db.commit()
    return get_box_test_status(db, box_id)


def consume_box_test_pulse(db: Session, box_id: str) -> dict[str, bool | int]:
    state = db.get(BoxTestState, box_id)
    result = {
        "test_mode": bool(state and state.is_active),
        "test_pulse_count": (
            state.pending_pulse_count or 0
            if state and state.is_active
            else 0
        ),
    }
    if state is not None and state.pending_pulse_count is not None:
        state.pending_amount = None
        state.pending_pulse_count = None
        state.updated_at = utcnow()
        db.commit()
    return result


def list_boxes(db: Session) -> list[dict]:
    boxes = db.query(WashBox).order_by(WashBox.id).all()
    result = []
    for box in boxes:
        latest = (
            db.query(Visit)
            .filter(Visit.box_id == box.id)
            .order_by(Visit.created_at.desc())
            .first()
        )
        result.append({
            "id": box.id,
            "name": box.name,
            "active_bonus_left": latest.bonus_left if latest and latest.is_active_bonus else 0,
            "current_plate": visit_plate(latest) if latest else None,
        })
    return result


def create_box(db: Session, box_id: str, name: str) -> dict:
    box_id = box_id.strip()
    name = name.strip()
    if not box_id or not name:
        raise ValueError("Box ID and name are required")
    if len(box_id) > 40 or len(name) > 100:
        raise ValueError("Box ID must be <= 40 and name <= 100 characters")
    if db.get(WashBox, box_id):
        raise ValueError(f"Box already exists: {box_id}")
    box = WashBox(id=box_id, name=name)
    db.add(box)
    db.commit()
    return {"id": box.id, "name": box.name, "active_bonus_left": 0, "current_plate": None}


def normalize_plate(plate: str) -> str:
    cleaned = (plate or "").strip().replace("-", "").replace(" ", "")
    return cleaned.upper() if cleaned.isascii() else cleaned


def is_valid_plate(plate: str) -> bool:
    plate = normalize_plate(plate)
    return PLATE_PATTERN.fullmatch(plate) is not None


def get_car_by_plate(db: Session, plate: str) -> Car | None:
    return db.query(Car).filter(Car.plate == plate).first()


def create_or_get_car(db: Session, plate: str) -> Car:
    car = get_car_by_plate(db, plate)
    if car:
        return car
    car = Car(plate=plate, created_at=utcnow())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


def get_visits_for_car(db: Session, car_id: int, limit: int = 20):
    return db.query(Visit).filter(Visit.car_id == car_id).order_by(Visit.created_at.desc()).limit(limit).all()


def expire_active_bonus(db: Session, visit: Visit) -> None:
    expired_amount = visit.bonus_left
    visit.bonus_expired += expired_amount
    visit.bonus_left = 0
    visit.is_active_bonus = 0
    if expired_amount > 0:
        db.add(
            DeviceLog(
                event="bonus_expired",
                payload=f"{visit.box_id}:{visit_plate(visit)}:{expired_amount}",
            )
        )


def create_visit_for_car(db: Session, car: Car, box_id: str) -> Visit:
    last_visit = db.query(Visit).filter(Visit.car_id == car.id).order_by(Visit.created_at.desc()).first()
    if last_visit and utcnow() - last_visit.created_at < timedelta(hours=24):
        active_bonus = (
            db.query(Visit)
            .filter(Visit.is_active_bonus == 1)
            .order_by(Visit.created_at.desc())
            .first()
        )
        if active_bonus and active_bonus.car_id != car.id:
            expire_active_bonus(db, active_bonus)
            db.commit()
        return last_visit

    box = ensure_box(db, box_id)
    active_bonus = (
        db.query(Visit)
        .filter(Visit.is_active_bonus == 1)
        .order_by(Visit.created_at.desc())
        .first()
    )
    if active_bonus:
        expire_active_bonus(db, active_bonus)

    visit_no = db.query(Visit).filter(Visit.car_id == car.id).count() + 1
    bonus_settings = get_bonus_settings(db)
    visit = Visit(
        car_id=car.id,
        box_id=box.id,
        created_at=utcnow(),
        visit_no=visit_no,
        bonus_total=0,
        bonus_left=0,
        bonus_expired=0,
        is_active_bonus=0,
    )

    if visit_no % bonus_settings["bonus_every_visits"] == 0:
        visit.bonus_total = bonus_settings["bonus_amount"]
        visit.bonus_left = bonus_settings["bonus_amount"]
        visit.is_active_bonus = 1

    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def get_display_text(db: Session, box_id: str = DEFAULT_BOX_ID) -> dict:
    box = ensure_box(db, box_id)
    display_copy = get_bonus_settings(db, box.id)
    latest_visit = (
        db.query(Visit)
        .filter(Visit.box_id == box.id)
        .order_by(Visit.created_at.desc())
        .first()
    )
    if not latest_visit:
        return {
            "version": 1,
            "text": display_copy["display_idle_text"],
            "status": "idle",
        }

    plate = visit_plate(latest_visit)
    if latest_visit.is_active_bonus:
        bonus_text = f"{latest_visit.bonus_left:,}".replace(",", " ")
        return {
            "version": 2,
            "text": (
                f"{plate} - {latest_visit.visit_no}-{display_copy['display_visit_label']}! "
                f"{display_copy['display_reward_label']} {bonus_text} "
                f"{display_copy['display_currency_label']}"
            ),
            "status": "bonus_active",
        }

    return {
        "version": 1,
        "text": f"{plate} - {latest_visit.visit_no}-{display_copy['display_visit_label']}",
        "status": "normal",
    }


def _pulse_response(visit: Visit, amount: int, pulse_count: int, message: str, duplicate: bool = False) -> dict:
    return {
        "ok": True,
        "bonus_left": visit.bonus_left,
        "amount": amount,
        "pulse_count": pulse_count,
        "duplicate": duplicate,
        "message": message,
    }


def find_pulse_by_press_id(db: Session, press_id: str) -> BonusPulse | None:
    return db.query(BonusPulse).filter(BonusPulse.press_id == press_id).first()


def press_bonus(
    db: Session,
    plate: str | None,
    box_id: str = DEFAULT_BOX_ID,
    press_id: str | None = None,
) -> dict:
    box = ensure_box(db, box_id)

    # Qurilma javobni olmay qayta yuborsa, pul ikki marta yechilmasin.
    if press_id:
        existing = find_pulse_by_press_id(db, press_id)
        if existing is not None:
            return _pulse_response(
                existing.visit,
                existing.amount,
                existing.amount // PULSE_VALUE,
                "Duplicate pulse ignored",
                duplicate=True,
            )

    test_state = db.get(BoxTestState, box.id)
    if test_state is not None and test_state.is_active:
        return {"ok": False, "bonus_left": 0, "message": "Box is in test mode"}
    query = db.query(Visit).filter(Visit.box_id == box.id, Visit.is_active_bonus == 1)
    if plate:
        car = get_car_by_plate(db, normalize_plate(plate))
        if not car:
            return {"ok": False, "bonus_left": 0, "message": "Car not found"}
        query = query.filter(Visit.car_id == car.id)
    visit = query.order_by(Visit.created_at.desc()).first()
    if not visit:
        return {"ok": False, "bonus_left": 0, "message": "No active bonus"}

    if visit.bonus_left <= 0:
        return {"ok": False, "bonus_left": 0, "message": "Bonus exhausted"}

    amount = min(get_bonus_settings(db)["bonus_per_press"], visit.bonus_left)
    visit.bonus_left -= amount
    if visit.bonus_left <= 0:
        visit.bonus_left = 0
        visit.is_active_bonus = 0

    pulse = BonusPulse(
        visit_id=visit.id,
        created_at=utcnow(),
        amount=amount,
        press_id=press_id,
    )
    db.add(pulse)
    db.add(DeviceLog(event="bonus_press", payload=f"{box.id}:{visit_plate(visit)}:{amount}"))
    try:
        db.commit()
    except IntegrityError:
        # Parallel retry bir xil press_id bilan yozib ulgurgan bo'lishi mumkin.
        db.rollback()
        existing = find_pulse_by_press_id(db, press_id) if press_id else None
        if existing is None:
            raise
        return _pulse_response(
            existing.visit,
            existing.amount,
            existing.amount // PULSE_VALUE,
            "Duplicate pulse ignored",
            duplicate=True,
        )

    return _pulse_response(visit, amount, amount // PULSE_VALUE, "Bonus pulse accepted")


def list_recent_pulses(db: Session, limit: int = 20, box_id: str | None = None) -> list[dict]:
    query = db.query(BonusPulse).join(Visit, BonusPulse.visit_id == Visit.id)
    if box_id:
        query = query.filter(Visit.box_id == box_id)
    pulses = query.order_by(BonusPulse.created_at.desc(), BonusPulse.id.desc()).limit(limit).all()
    return [
        {
            "id": pulse.id,
            "visit_id": pulse.visit_id,
            "box_id": pulse.visit.box_id,
            "plate": visit_plate(pulse.visit),
            "amount": pulse.amount,
            "created_at": iso_utc(pulse.created_at),
            "refunded_at": iso_utc(pulse.refunded_at),
        }
        for pulse in pulses
    ]


def refund_pulse(db: Session, pulse_id: int) -> dict:
    pulse = db.get(BonusPulse, pulse_id)
    if pulse is None:
        raise ValueError("Pulse not found")
    if pulse.refunded_at is not None:
        raise ValueError("Pulse is already refunded")

    visit = pulse.visit
    other_active = (
        db.query(Visit)
        .filter(Visit.is_active_bonus == 1, Visit.id != visit.id)
        .first()
    )
    if not visit.is_active_bonus and other_active is not None:
        # Bonus boshqa mashinaning kelishi bilan bekor qilingan; qaytarish uni
        # qayta tiklab, bir vaqtda ikkita faol bonus yaratmasligi kerak.
        raise ValueError("Bonus already expired by a newer visit")

    visit.bonus_left += pulse.amount
    if visit.bonus_left > visit.bonus_total:
        visit.bonus_left = visit.bonus_total
    if visit.bonus_expired >= pulse.amount:
        visit.bonus_expired -= pulse.amount
    if visit.bonus_left > 0:
        visit.is_active_bonus = 1
    pulse.refunded_at = utcnow()
    db.add(DeviceLog(event="bonus_refunded", payload=f"{visit.box_id}:{visit_plate(visit)}:{pulse.amount}"))
    db.commit()
    return {
        "ok": True,
        "pulse_id": pulse.id,
        "amount": pulse.amount,
        "bonus_left": visit.bonus_left,
        "refunded_at": iso_utc(pulse.refunded_at),
    }



def get_stats(db: Session) -> dict:
    cars_count = db.query(Car).count()
    visits_count = db.query(Visit).count()
    total_bonus_paid = db.query(func.coalesce(func.sum(BonusPulse.amount), 0)).scalar() or 0
    active_bonus_count = db.query(Visit).filter(Visit.is_active_bonus == 1).count()
    return {
        "cars_count": cars_count,
        "visits_count": visits_count,
        "total_bonus_paid": total_bonus_paid,
        "active_bonus_count": active_bonus_count,
    }


def list_recent_visits(
    db: Session,
    limit: int = 10,
    box_id: str | None = None,
    offset: int = 0,
    plate: str | None = None,
):
    query = db.query(Visit).join(Car, Visit.car_id == Car.id)
    if box_id is not None:
        query = query.filter(Visit.box_id == box_id)
    if plate:
        normalized = normalize_plate(plate)
        query = query.filter(
            or_(
                Car.plate.like(f"%{normalized}%"),
                Visit.plate_override.like(f"%{normalized}%"),
            )
        )
    visits = (
        query.order_by(Visit.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    visit_ids = [visit.id for visit in visits]
    detection_by_visit = {}
    if visit_ids:
        detections = (
            db.query(DetectionRecord)
            .filter(DetectionRecord.visit_id.in_(visit_ids))
            .order_by(DetectionRecord.created_at.desc(), DetectionRecord.id.desc())
            .all()
        )
        for detection in detections:
            detection_by_visit.setdefault(detection.visit_id, detection.id)

    items = []
    for visit in visits:
        detection_id = detection_by_visit.get(visit.id)
        items.append(
            {
                "id": visit.id,
                "plate": visit_plate(visit),
                "visit_no": visit.visit_no,
                "created_at": iso_utc(visit.created_at),
                "bonus_total": visit.bonus_total,
                "bonus_left": visit.bonus_left,
                "is_active_bonus": bool(visit.is_active_bonus),
                "box_id": visit.box_id,
                "image_url": f"/api/detections/{detection_id}/image" if detection_id else None,
            }
        )
    return items


def list_recent_cars(
    db: Session,
    limit: int = 10,
    offset: int = 0,
    plate: str | None = None,
):
    query = db.query(Car)
    if plate:
        query = query.filter(Car.plate.like(f"%{normalize_plate(plate)}%"))
    cars = (
        query.order_by(Car.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": car.id,
            "plate": car.plate,
            "created_at": iso_utc(car.created_at),
            "visit_count": db.query(Visit).filter(Visit.car_id == car.id).count(),
        }
        for car in cars
    ]


def process_plate_detection(db: Session, plate: str, box_id: str = DEFAULT_BOX_ID) -> dict:
    plate = normalize_plate(plate)
    if not is_valid_plate(plate):
        raise ValueError("Invalid plate format")

    box = ensure_box(db, box_id)
    car = create_or_get_car(db, plate)
    visit = create_visit_for_car(db, car, box.id)
    db.add(DeviceLog(event="detect", payload=f"{box.id}:{plate}"))
    db.commit()
    db.refresh(visit)
    return {
        "ok": True,
        "plate": plate,
        "visit_no": visit.visit_no,
        "bonus_total": visit.bonus_total,
        "bonus_left": visit.bonus_left,
        "is_active_bonus": bool(visit.is_active_bonus),
        "box_id": box.id,
        "visit_id": visit.id,
    }

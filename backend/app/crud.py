from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AppSetting, BonusPulse, Car, DeviceLog, Visit, WashBox

DEFAULT_BOX_ID = "box-1"
DEFAULT_BOX_NAME = "Box 1"
PULSE_VALUE = 1_000
DEFAULT_SETTINGS = {
    "bonus_amount": 20_000,
    "bonus_per_press": 5_000,
    "bonus_every_visits": 10,
}


def visit_plate(visit: Visit) -> str:
    return visit.plate_override or visit.car.plate


def get_bonus_settings(db: Session) -> dict[str, int]:
    values = {row.key: int(row.value) for row in db.query(AppSetting).all()}
    result = {}
    created_default = False
    for key, default in DEFAULT_SETTINGS.items():
        result[key] = values.get(key, default)
        if key not in values:
            db.add(AppSetting(key=key, value=str(default)))
            created_default = True
    if created_default:
        db.flush()
    return result


def update_bonus_settings(
    db: Session,
    bonus_amount: int | None,
    bonus_per_press: int | None,
    bonus_every_visits: int | None,
) -> dict[str, int]:
    current = get_bonus_settings(db)
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
    db.flush()
    db.commit()
    return {
        **current,
        **{key: value for key, value in updates.items() if value is not None},
    }


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
    cleaned = (plate or "").strip().upper().replace("-", "").replace(" ", "")
    return cleaned


def is_valid_plate(plate: str) -> bool:
    plate = normalize_plate(plate)
    if len(plate) != 8:
        return False

    if plate[:2].isdigit() and plate[2].isalpha() and plate[3:6].isdigit() and plate[6:].isalpha() and len(plate[6:]) == 2:
        return True

    if plate[:5].isdigit() and plate[5:].isalpha() and len(plate[5:]) == 3:
        return True

    return False


def get_car_by_plate(db: Session, plate: str) -> Car | None:
    return db.query(Car).filter(Car.plate == plate).first()


def create_or_get_car(db: Session, plate: str) -> Car:
    car = get_car_by_plate(db, plate)
    if car:
        return car
    car = Car(plate=plate, created_at=datetime.utcnow())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


def get_visits_for_car(db: Session, car_id: int, limit: int = 20):
    return db.query(Visit).filter(Visit.car_id == car_id).order_by(Visit.created_at.desc()).limit(limit).all()


def create_visit_for_car(db: Session, car: Car, box_id: str) -> Visit:
    last_visit = db.query(Visit).filter(Visit.car_id == car.id).order_by(Visit.created_at.desc()).first()
    if last_visit and datetime.utcnow() - last_visit.created_at < timedelta(hours=24):
        return last_visit

    box = ensure_box(db, box_id)
    active_bonus = (
        db.query(Visit)
        .filter(Visit.is_active_bonus == 1)
        .order_by(Visit.created_at.desc())
        .first()
    )
    if active_bonus:
        active_bonus.bonus_expired += active_bonus.bonus_left
        active_bonus.bonus_left = 0
        active_bonus.is_active_bonus = 0

    visit_no = db.query(Visit).filter(Visit.car_id == car.id).count() + 1
    bonus_settings = get_bonus_settings(db)
    visit = Visit(
        car_id=car.id,
        box_id=box.id,
        created_at=datetime.utcnow(),
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
    latest_visit = (
        db.query(Visit)
        .filter(Visit.box_id == box.id)
        .order_by(Visit.created_at.desc())
        .first()
    )
    if not latest_visit:
        return {"version": 1, "text": "NO VEHICLE", "status": "idle"}

    plate = visit_plate(latest_visit)
    if latest_visit.is_active_bonus:
        return {
            "version": 2,
            "text": f"{plate} - {latest_visit.visit_no}-KELISH! BONUS {latest_visit.bonus_left} SO'M",
            "status": "bonus_active",
        }

    return {"version": 1, "text": f"{plate} - {latest_visit.visit_no}-KELISH", "status": "normal"}


def press_bonus(db: Session, plate: str | None, box_id: str = DEFAULT_BOX_ID) -> dict:
    box = ensure_box(db, box_id)
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

    pulse = BonusPulse(visit_id=visit.id, created_at=datetime.utcnow(), amount=amount)
    db.add(pulse)
    db.add(DeviceLog(event="bonus_press", payload=f"{box.id}:{visit_plate(visit)}:{amount}"))
    db.commit()

    return {
        "ok": True,
        "bonus_left": visit.bonus_left,
        "amount": amount,
        "pulse_count": amount // PULSE_VALUE,
        "message": "Bonus pulse accepted",
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


def list_recent_visits(db: Session, limit: int = 10, box_id: str | None = None):
    query = db.query(Visit)
    if box_id is not None:
        query = query.filter(Visit.box_id == box_id)
    visits = query.order_by(Visit.created_at.desc()).limit(limit).all()
    items = []
    for visit in visits:
        items.append(
            {
                "id": visit.id,
                "plate": visit_plate(visit),
                "visit_no": visit.visit_no,
                "created_at": visit.created_at.isoformat(),
                "bonus_total": visit.bonus_total,
                "bonus_left": visit.bonus_left,
                "is_active_bonus": bool(visit.is_active_bonus),
                "box_id": visit.box_id,
            }
        )
    return items


def list_recent_cars(db: Session, limit: int = 10):
    cars = db.query(Car).order_by(Car.created_at.desc()).limit(limit).all()
    return [
        {
            "id": car.id,
            "plate": car.plate,
            "created_at": car.created_at.isoformat(),
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

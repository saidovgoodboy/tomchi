from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    plate = Column(String(20), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    visits = relationship("Visit", back_populates="car")


class WashBox(Base):
    __tablename__ = "wash_boxes"

    id = Column(String(40), primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    visits = relationship("Visit", back_populates="box")
    detections = relationship("DetectionRecord", back_populates="box")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(80), primary_key=True)
    value = Column(String(255), nullable=False)


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    box_id = Column(String(40), ForeignKey("wash_boxes.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    visit_no = Column(Integer, nullable=False)
    plate_override = Column(String(20), nullable=True)
    bonus_total = Column(Integer, default=0, nullable=False)
    bonus_left = Column(Integer, default=0, nullable=False)
    bonus_expired = Column(Integer, default=0, nullable=False)
    is_active_bonus = Column(Integer, default=0, nullable=False)

    car = relationship("Car", back_populates="visits")
    box = relationship("WashBox", back_populates="visits")
    pulses = relationship("BonusPulse", back_populates="visit")


class BonusPulse(Base):
    __tablename__ = "bonus_pulses"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    amount = Column(Integer, default=0, nullable=False)

    visit = relationship("Visit", back_populates="pulses")


class DetectionRecord(Base):
    __tablename__ = "detections"
    __table_args__ = (UniqueConstraint("box_id", "event_key", name="uq_detection_box_event"),)

    id = Column(Integer, primary_key=True, index=True)
    box_id = Column(String(40), ForeignKey("wash_boxes.id"), nullable=False, index=True)
    event_key = Column(String(100), nullable=False)
    image_key = Column(String(80), unique=True, nullable=False)
    frame_index = Column(Integer, default=0, nullable=False)
    frame_count = Column(Integer, default=1, nullable=False)
    plate = Column(String(20), nullable=True, index=True)
    status = Column(String(20), default="pending", nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    box = relationship("WashBox", back_populates="detections")
    visit = relationship("Visit")


class DeviceLog(Base):
    __tablename__ = "device_logs"

    id = Column(Integer, primary_key=True, index=True)
    event = Column(String(100), nullable=False)
    payload = Column(String(255), default="", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

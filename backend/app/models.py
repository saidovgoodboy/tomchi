from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
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


class DeviceLog(Base):
    __tablename__ = "device_logs"

    id = Column(Integer, primary_key=True, index=True)
    event = Column(String(100), nullable=False)
    payload = Column(String(255), default="", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

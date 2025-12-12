from __future__ import annotations

import datetime as dt
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Meter(Base):
    __tablename__ = "meters"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    unit_id = Column(Integer, default=1)
    baud_rate = Column(Integer, default=9600)
    model = Column(String, default="Acuvim-L")
    site_name = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)

    last_collected = Column(DateTime, nullable=True)
    last_timesync = Column(DateTime, nullable=True)
    last_drift_seconds = Column(Integer, nullable=True)
    last_record_index = Column(Integer, default=0)
    output_folder = Column(Text, nullable=True)

    created = Column(DateTime, default=dt.datetime.utcnow)
    updated = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

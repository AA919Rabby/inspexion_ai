import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, JSON, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base


class InspectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    google_id = Column(String(255), unique=True, index=True, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    inspections = relationship("InspectionSession", back_populates="owner", cascade="all, delete-orphan")

class InspectionSession(Base):
    __tablename__ = "inspection_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="Untitled Inspection")
    asset_type = Column(String(100), default="General Physical Asset")
    status = Column(Enum(InspectionStatus), default=InspectionStatus.PENDING)
    summary = Column(Text, nullable=True)
    critical_defects_count = Column(Integer, default=0)
    minor_defects_count = Column(Integer, default=0)
    total_images = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="inspections")
    images = relationship("InspectionImage", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("PDFReport", back_populates="session", cascade="all, delete-orphan")
    chunks = relationship("InspectionReportChunk", back_populates="session", cascade="all, delete-orphan")

class InspectionImage(Base):
    __tablename__ = "inspection_images"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inspection_sessions.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    yolo_detections = Column(JSON, default=list) # List of dicts: bbox, label, confidence
    detected_category = Column(String(100), default="Unknown")
    confidence_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("InspectionSession", back_populates="images")

class PDFReport(Base):
    __tablename__ = "pdf_reports"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inspection_sessions.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    report_title = Column(String(255), nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("InspectionSession", back_populates="reports")

class InspectionReportChunk(Base):
    __tablename__ = "inspection_report_chunks"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inspection_sessions.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("InspectionSession", back_populates="chunks")
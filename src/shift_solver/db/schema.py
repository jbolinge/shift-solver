"""SQLAlchemy database schema for shift-solver."""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class DBWorker(Base):
    """Database model for workers."""

    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    worker_type: Mapped[str | None] = mapped_column(String(50))
    restricted_shifts: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_shifts: Mapped[list[str]] = mapped_column(JSON, default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    assignments: Mapped[list["DBAssignment"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )
    availabilities: Mapped[list["DBAvailability"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )
    requests: Mapped[list["DBRequest"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )


class DBShiftType(Base):
    """Database model for shift types."""

    __tablename__ = "shift_types"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    is_undesirable: Mapped[bool] = mapped_column(Boolean, default=False)
    workers_required: Mapped[int] = mapped_column(Integer, default=1)
    required_attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    assignments: Mapped[list["DBAssignment"]] = relationship(back_populates="shift_type")


class DBSchedule(Base):
    """Database model for schedules."""

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), default="week")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    solver_objective: Mapped[float | None] = mapped_column(Float)
    solver_time_seconds: Mapped[float | None] = mapped_column(Float)

    # Relationships
    assignments: Mapped[list["DBAssignment"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


class DBAssignment(Base):
    """Database model for worker-shift assignments."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("schedules.id"), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("workers.id"), nullable=False
    )
    shift_type_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("shift_types.id"), nullable=False
    )
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)

    # Relationships
    schedule: Mapped["DBSchedule"] = relationship(back_populates="assignments")
    worker: Mapped["DBWorker"] = relationship(back_populates="assignments")
    shift_type: Mapped["DBShiftType"] = relationship(back_populates="assignments")


class DBAvailability(Base):
    """Database model for worker availability/unavailability."""

    __tablename__ = "availabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("workers.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    availability_type: Mapped[str] = mapped_column(String(20), nullable=False)
    shift_type_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("shift_types.id")
    )

    # Relationships
    worker: Mapped["DBWorker"] = relationship(back_populates="availabilities")


class DBRequest(Base):
    """Database model for scheduling requests."""

    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("workers.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)
    shift_type_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("shift_types.id"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    worker: Mapped["DBWorker"] = relationship(back_populates="requests")

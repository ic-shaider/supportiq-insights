"""Database models for SupportIQ Insights."""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Enum, Text, JSON, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()
DATABASE_URL = "sqlite:///./supportiq.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TicketCategory(str, PyEnum):
    PAYMENT_PROCESSING = "payment_processing"
    BILLER_CONFIGURATION = "biller_configuration"
    INTEGRATION = "integration"
    USER_ACCESS = "user_access"
    PERFORMANCE = "performance"
    DATA_ISSUES = "data_issues"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class TicketSeverity(str, PyEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, PyEnum):
    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    AUTO_RESOLVED = "auto_resolved"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AffectedSystem(str, PyEnum):
    PAYMENT_SERVICE = "payment_service"
    BILLER_CONFIG = "biller_config"
    GUIDEWIRE = "guidewire"
    SERVICEIQ = "serviceiq"
    IVR = "ivr"
    NBE_PORTAL = "nbe_portal"
    REPORTING = "reporting"
    API_GATEWAY = "api_gateway"
    NOTIFICATION = "notification"
    DATABASE = "database"
    AUTH = "auth"
    OTHER = "other"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(50), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    reporter_email = Column(String(200))
    reporter_name = Column(String(200))
    biller_name = Column(String(200))
    status = Column(Enum(TicketStatus), default=TicketStatus.NEW)

    # Classification (from Ticket Classifier Agent)
    category = Column(Enum(TicketCategory))
    severity = Column(Enum(TicketSeverity))
    affected_system = Column(Enum(AffectedSystem))
    classification_confidence = Column(Float, default=0.0)
    keywords = Column(JSON)

    # Escalation Prediction (from Escalation Predictor Agent)
    escalation_probability = Column(Float, default=0.0)
    escalation_risk = Column(String(20))  # high, medium, low
    escalation_factors = Column(JSON)
    predicted_resolution_hours = Column(Float)
    will_need_engineering = Column(Boolean, default=False)

    # Resolution (from Auto-Resolver Agent or human)
    resolution_notes = Column(Text)
    resolution_type = Column(String(50))  # auto_resolved, manual, escalated
    resolution_pattern_id = Column(Integer, ForeignKey("resolution_patterns.id"))
    resolved_by = Column(String(200))
    time_to_resolution_hours = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    escalated_at = Column(DateTime)

    resolution_pattern = relationship("ResolutionPattern", back_populates="tickets")


class ResolutionPattern(Base):
    """Knowledge base of known resolution patterns for auto-resolution."""
    __tablename__ = "resolution_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_name = Column(String(200), nullable=False)
    category = Column(Enum(TicketCategory), nullable=False)
    affected_system = Column(Enum(AffectedSystem))
    trigger_keywords = Column(JSON, nullable=False)
    resolution_steps = Column(Text, nullable=False)
    resolution_type = Column(String(50))  # config_change, known_bug, faq, restart, workaround
    auto_resolvable = Column(Boolean, default=False)
    auto_resolve_script = Column(Text)  # Script/command to auto-resolve
    success_rate = Column(Float, default=0.0)
    times_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    tickets = relationship("SupportTicket", back_populates="resolution_pattern")


class EscalationEvent(Base):
    """Tracks escalation events for analytics."""
    __tablename__ = "escalation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(50), nullable=False)
    escalated_to = Column(String(200))  # Engineering team
    reason = Column(Text)
    engineering_hours_spent = Column(Float, default=0.0)
    was_predicted = Column(Boolean, default=False)
    prediction_confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

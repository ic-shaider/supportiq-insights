"""Support Intelligence Orchestrator — Coordinates classify → predict → resolve pipeline."""

import logging
import time
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.agents.ticket_classifier import TicketClassifierAgent
from app.agents.escalation_predictor import EscalationPredictorAgent
from app.agents.auto_resolver import AutoResolverAgent
from app.models.database import SupportTicket, TicketStatus, TicketCategory, TicketSeverity, AffectedSystem

logger = logging.getLogger(__name__)


class SupportOrchestrator:
    def __init__(self):
        self.classifier = TicketClassifierAgent()
        self.predictor = EscalationPredictorAgent()
        self.resolver = AutoResolverAgent()
        self.start_time = datetime.utcnow()
        self.status = "healthy"
        self.pipeline_runs = 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "orchestrator_status": self.status,
            "pipeline_runs": self.pipeline_runs,
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "agents": [
                {"name": self.classifier.name, "status": self.classifier.status,
                 "last_run": self.classifier.last_run.isoformat() if self.classifier.last_run else None,
                 "records_processed": self.classifier.records_processed},
                {"name": self.predictor.name, "status": self.predictor.status,
                 "last_run": self.predictor.last_run.isoformat() if self.predictor.last_run else None,
                 "records_processed": self.predictor.records_processed},
                {"name": self.resolver.name, "status": self.resolver.status,
                 "last_run": self.resolver.last_run.isoformat() if self.resolver.last_run else None,
                 "records_processed": self.resolver.records_processed,
                 "auto_resolved": self.resolver.auto_resolved},
            ],
        }

    def get_dashboard(self, db: Session) -> Dict[str, Any]:
        total = db.query(func.count(SupportTicket.id)).scalar() or 0
        open_tickets = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.status.in_([TicketStatus.NEW, TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS])
        ).scalar() or 0
        escalated = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.status == TicketStatus.ESCALATED
        ).scalar() or 0
        auto_resolved = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.status == TicketStatus.AUTO_RESOLVED
        ).scalar() or 0
        resolved = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])
        ).scalar() or 0
        high_risk = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.escalation_risk == "high",
            SupportTicket.status.in_([TicketStatus.NEW, TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS])
        ).scalar() or 0

        # By category
        cat_counts = {}
        for cat in TicketCategory:
            count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.category == cat).scalar() or 0
            if count > 0:
                cat_counts[cat.value] = count

        # By system
        sys_counts = {}
        for sys in AffectedSystem:
            count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.affected_system == sys).scalar() or 0
            if count > 0:
                sys_counts[sys.value] = count

        # By severity
        sev_counts = {}
        for sev in TicketSeverity:
            count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.severity == sev).scalar() or 0
            if count > 0:
                sev_counts[sev.value] = count

        avg_resolution_hours = db.query(func.avg(SupportTicket.time_to_resolution_hours)).filter(
            SupportTicket.time_to_resolution_hours != None
        ).scalar() or 0.0

        auto_resolve_rate = (auto_resolved / total * 100) if total > 0 else 0
        escalation_rate = (escalated / total * 100) if total > 0 else 0
        engineering_time_pct = escalation_rate * 0.8  # Rough proxy

        return {
            "total_tickets": total,
            "open_tickets": open_tickets,
            "escalated": escalated,
            "auto_resolved": auto_resolved,
            "resolved": resolved,
            "high_risk_open": high_risk,
            "auto_resolve_rate": round(auto_resolve_rate, 1),
            "escalation_rate": round(escalation_rate, 1),
            "engineering_time_pct": round(engineering_time_pct, 1),
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "by_category": cat_counts,
            "by_system": sys_counts,
            "by_severity": sev_counts,
        }

    def run_pipeline(self, db: Session) -> Dict[str, Any]:
        start = time.time()
        steps = []

        # Step 1: Classify
        try:
            classify_result = self.classifier.classify_all(db)
            steps.append({"step": "classification", "status": "success", **classify_result})
        except Exception as e:
            steps.append({"step": "classification", "status": "error", "error": str(e)})

        # Step 2: Predict
        try:
            predict_result = self.predictor.predict_all(db)
            steps.append({"step": "prediction", "status": "success", **predict_result})
        except Exception as e:
            steps.append({"step": "prediction", "status": "error", "error": str(e)})

        # Step 3: Auto-resolve
        try:
            resolve_result = self.resolver.auto_resolve_batch(db)
            steps.append({"step": "auto_resolution", "status": "success", **resolve_result})
        except Exception as e:
            steps.append({"step": "auto_resolution", "status": "error", "error": str(e)})

        self.pipeline_runs += 1
        return {
            "steps": steps,
            "total_duration_seconds": round(time.time() - start, 3),
            "pipeline_run": self.pipeline_runs,
        }

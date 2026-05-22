"""
Escalation Predictor Agent — Predicts which tickets will escalate to engineering.

Uses a feature-based scoring model. In production, would use a trained Random Forest
or gradient boosting model on historical ticket data.

Key features:
- Ticket category (integration/performance tickets escalate more)
- Severity level
- Biller tier (enterprise billers get faster escalation)
- Keywords (error codes, specific systems)
- Time of day / day of week patterns
- Historical escalation rate per category
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.database import (
    SupportTicket, TicketCategory, TicketSeverity, AffectedSystem,
    TicketStatus
)

logger = logging.getLogger(__name__)

# Historical escalation rates by category (from IC support data patterns)
CATEGORY_ESCALATION_RATES = {
    TicketCategory.PAYMENT_PROCESSING: 0.35,
    TicketCategory.BILLER_CONFIGURATION: 0.15,
    TicketCategory.INTEGRATION: 0.55,
    TicketCategory.USER_ACCESS: 0.10,
    TicketCategory.PERFORMANCE: 0.50,
    TicketCategory.DATA_ISSUES: 0.40,
    TicketCategory.FEATURE_REQUEST: 0.05,
    TicketCategory.OTHER: 0.20,
}

SYSTEM_ESCALATION_WEIGHTS = {
    AffectedSystem.PAYMENT_SERVICE: 0.15,
    AffectedSystem.BILLER_CONFIG: 0.05,
    AffectedSystem.GUIDEWIRE: 0.25,
    AffectedSystem.SERVICEIQ: 0.10,
    AffectedSystem.IVR: 0.10,
    AffectedSystem.NBE_PORTAL: 0.05,
    AffectedSystem.REPORTING: 0.05,
    AffectedSystem.API_GATEWAY: 0.15,
    AffectedSystem.NOTIFICATION: 0.05,
    AffectedSystem.DATABASE: 0.20,
    AffectedSystem.AUTH: 0.10,
    AffectedSystem.OTHER: 0.05,
}

SEVERITY_WEIGHTS = {
    TicketSeverity.CRITICAL: 0.30,
    TicketSeverity.HIGH: 0.20,
    TicketSeverity.MEDIUM: 0.05,
    TicketSeverity.LOW: -0.05,
}

HIGH_ESCALATION_KEYWORDS = [
    "production", "outage", "data loss", "security", "all users",
    "revenue", "compliance", "audit", "guidewire sync", "api down",
    "database", "migration", "corruption", "certificate expired",
]

RESOLUTION_TIME_ESTIMATES = {
    TicketCategory.PAYMENT_PROCESSING: 4.0,
    TicketCategory.BILLER_CONFIGURATION: 2.0,
    TicketCategory.INTEGRATION: 8.0,
    TicketCategory.USER_ACCESS: 1.0,
    TicketCategory.PERFORMANCE: 6.0,
    TicketCategory.DATA_ISSUES: 5.0,
    TicketCategory.FEATURE_REQUEST: 40.0,
    TicketCategory.OTHER: 3.0,
}


class EscalationPredictorAgent:
    """Predicts ticket escalation probability."""

    def __init__(self):
        self.name = "EscalationPredictor"
        self.status = "healthy"
        self.last_run: Optional[datetime] = None
        self.records_processed = 0

    def predict_ticket(self, db: Session, ticket_id: int) -> Dict[str, Any]:
        """Predict escalation probability for a single ticket."""
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            return {"error": "Ticket not found"}

        if not ticket.category:
            return {"error": "Ticket not classified yet — run classifier first"}

        probability, factors = self._calculate_escalation_score(ticket)
        risk_level = self._probability_to_risk(probability)
        resolution_hours = self._estimate_resolution_time(ticket, probability)
        needs_engineering = probability >= 0.5

        ticket.escalation_probability = probability
        ticket.escalation_risk = risk_level
        ticket.escalation_factors = factors
        ticket.predicted_resolution_hours = resolution_hours
        ticket.will_need_engineering = needs_engineering

        db.commit()
        self.records_processed += 1
        self.last_run = datetime.utcnow()

        return {
            "ticket_id": ticket.ticket_id,
            "escalation_probability": probability,
            "risk_level": risk_level,
            "factors": factors,
            "predicted_resolution_hours": resolution_hours,
            "will_need_engineering": needs_engineering,
        }

    def predict_all(self, db: Session) -> Dict[str, Any]:
        """Batch predict all classified but unpredicted tickets."""
        tickets = db.query(SupportTicket).filter(
            SupportTicket.category != None,
            SupportTicket.escalation_probability == 0.0,
        ).all()

        results = {"predicted": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}
        for ticket in tickets:
            result = self.predict_ticket(db, ticket.id)
            if "error" not in result:
                results["predicted"] += 1
                risk = result["risk_level"]
                if risk == "high":
                    results["high_risk"] += 1
                elif risk == "medium":
                    results["medium_risk"] += 1
                else:
                    results["low_risk"] += 1

        return results

    def get_escalation_queue(self, db: Session, limit: int = 50) -> List[Dict[str, Any]]:
        """Get tickets sorted by escalation probability (highest first)."""
        tickets = db.query(SupportTicket).filter(
            SupportTicket.escalation_probability > 0,
            SupportTicket.status.in_([TicketStatus.NEW, TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS])
        ).order_by(desc(SupportTicket.escalation_probability)).limit(limit).all()

        return [
            {
                "id": t.id,
                "ticket_id": t.ticket_id,
                "title": t.title,
                "category": t.category.value if t.category else None,
                "severity": t.severity.value if t.severity else None,
                "affected_system": t.affected_system.value if t.affected_system else None,
                "biller_name": t.biller_name,
                "escalation_probability": t.escalation_probability,
                "risk_level": t.escalation_risk,
                "factors": t.escalation_factors,
                "predicted_resolution_hours": t.predicted_resolution_hours,
                "will_need_engineering": t.will_need_engineering,
                "status": t.status.value,
                "created_at": t.created_at.isoformat(),
            }
            for t in tickets
        ]

    def _calculate_escalation_score(self, ticket: SupportTicket) -> tuple[float, List[Dict[str, Any]]]:
        factors = []
        score = 0.0

        # Category base rate
        cat_rate = CATEGORY_ESCALATION_RATES.get(ticket.category, 0.2)
        score += cat_rate
        factors.append({"factor": "Category base rate", "value": f"{ticket.category.value}: {cat_rate:.0%}", "impact": cat_rate})

        # Severity
        sev_weight = SEVERITY_WEIGHTS.get(ticket.severity, 0.05)
        score += sev_weight
        if sev_weight > 0.1:
            factors.append({"factor": "Severity", "value": ticket.severity.value, "impact": sev_weight})

        # System complexity
        sys_weight = SYSTEM_ESCALATION_WEIGHTS.get(ticket.affected_system, 0.05)
        score += sys_weight
        if sys_weight > 0.1:
            factors.append({"factor": "System complexity", "value": ticket.affected_system.value, "impact": sys_weight})

        # Keyword signals
        text = f"{ticket.title} {ticket.description}".lower()
        keyword_hits = [kw for kw in HIGH_ESCALATION_KEYWORDS if kw in text]
        if keyword_hits:
            keyword_boost = min(len(keyword_hits) * 0.08, 0.25)
            score += keyword_boost
            factors.append({"factor": "High-risk keywords", "value": ", ".join(keyword_hits[:3]), "impact": keyword_boost})

        # Enterprise biller boost
        enterprise_billers = ["texas farm bureau", "db insurance", "fcci", "texas mutual", "safety insurance"]
        if ticket.biller_name and any(b in ticket.biller_name.lower() for b in enterprise_billers):
            score += 0.10
            factors.append({"factor": "Enterprise biller", "value": ticket.biller_name, "impact": 0.10})

        score = min(max(score, 0.01), 0.99)
        return round(score, 4), factors

    def _probability_to_risk(self, probability: float) -> str:
        if probability >= 0.6:
            return "high"
        elif probability >= 0.35:
            return "medium"
        return "low"

    def _estimate_resolution_time(self, ticket: SupportTicket, escalation_prob: float) -> float:
        base = RESOLUTION_TIME_ESTIMATES.get(ticket.category, 3.0)
        if ticket.severity == TicketSeverity.CRITICAL:
            base *= 0.5  # Faster response for critical
        elif ticket.severity == TicketSeverity.LOW:
            base *= 1.5

        if escalation_prob > 0.6:
            base *= 2.0  # Engineering involvement doubles time

        return round(base, 1)

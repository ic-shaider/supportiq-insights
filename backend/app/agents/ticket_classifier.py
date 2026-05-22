"""
Ticket Classifier Agent — Categorizes support tickets by type, severity, and affected system.

Uses TF-IDF + keyword matching to classify tickets. In production, this would use
an LLM (Azure OpenAI) for more nuanced classification, but the keyword-based approach
demonstrates the concept effectively for hackathon.

IC Context:
- ServiceIQ uses intent classification for customer-facing chat
- AIRA tracks ticket categories for sprint planning
- Payment processing, biller config, and integration are the top 3 ticket categories
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy.orm import Session

from app.models.database import (
    SupportTicket, TicketCategory, TicketSeverity, AffectedSystem, TicketStatus
)

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    TicketCategory.PAYMENT_PROCESSING: [
        "payment", "transaction", "failed", "declined", "refund", "charge", "ach",
        "credit card", "debit", "processor", "settlement", "reconciliation",
        "chase", "wells fargo", "paypal", "insufficient funds", "nsf", "rejected",
    ],
    TicketCategory.BILLER_CONFIGURATION: [
        "config", "configuration", "biller", "setup", "enable", "disable", "feature flag",
        "billing cycle", "payment method", "notification", "template", "onboarding",
    ],
    TicketCategory.INTEGRATION: [
        "guidewire", "api", "webhook", "sync", "integration", "endpoint", "timeout",
        "connection", "ssl", "certificate", "oauth", "token", "duck creek",
    ],
    TicketCategory.USER_ACCESS: [
        "login", "password", "access", "permission", "sso", "authentication", "locked",
        "account", "role", "unauthorized", "403", "401", "mfa", "2fa",
    ],
    TicketCategory.PERFORMANCE: [
        "slow", "timeout", "latency", "performance", "cpu", "memory", "load",
        "response time", "bottleneck", "hang", "freeze", "unresponsive",
    ],
    TicketCategory.DATA_ISSUES: [
        "missing data", "incorrect", "discrepancy", "mismatch", "duplicate",
        "reporting", "dashboard", "export", "import", "migration", "sync lag",
    ],
    TicketCategory.FEATURE_REQUEST: [
        "feature", "request", "enhancement", "would like", "need ability",
        "suggestion", "improve", "add support",
    ],
}

SYSTEM_KEYWORDS = {
    AffectedSystem.PAYMENT_SERVICE: ["payment", "transaction", "ach", "credit card", "processor"],
    AffectedSystem.BILLER_CONFIG: ["biller", "config", "configuration", "setup"],
    AffectedSystem.GUIDEWIRE: ["guidewire", "billing center", "policy center", "gw"],
    AffectedSystem.SERVICEIQ: ["serviceiq", "chatbot", "chat", "ai agent", "bot"],
    AffectedSystem.IVR: ["ivr", "phone", "call", "dtmf", "voice"],
    AffectedSystem.NBE_PORTAL: ["portal", "nbe", "dashboard", "ui", "frontend", "biller portal"],
    AffectedSystem.REPORTING: ["report", "analytics", "dashboard", "export", "csv"],
    AffectedSystem.API_GATEWAY: ["api", "gateway", "endpoint", "rest", "rate limit"],
    AffectedSystem.NOTIFICATION: ["email", "sms", "notification", "alert", "template"],
    AffectedSystem.DATABASE: ["database", "sql", "query", "cosmos", "snowflake"],
    AffectedSystem.AUTH: ["auth", "login", "sso", "oauth", "permission", "token"],
}

SEVERITY_RULES = {
    "critical": ["production down", "all users affected", "data loss", "security breach", "complete outage"],
    "high": ["many users", "payment failures", "revenue impact", "degraded", "intermittent outage"],
    "medium": ["some users", "workaround available", "partial", "one biller"],
    "low": ["question", "how to", "feature request", "minor", "cosmetic"],
}


class TicketClassifierAgent:
    """Classifies support tickets using keyword-based NLP."""

    def __init__(self):
        self.name = "TicketClassifier"
        self.status = "healthy"
        self.last_run: Optional[datetime] = None
        self.records_processed = 0

    def classify_ticket(self, db: Session, ticket_id: int) -> Dict[str, Any]:
        """Classify a single ticket."""
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            return {"error": "Ticket not found"}

        text = f"{ticket.title} {ticket.description}".lower()

        category, cat_confidence = self._classify_category(text)
        severity = self._classify_severity(text)
        system = self._classify_system(text)
        keywords = self._extract_keywords(text)

        ticket.category = category
        ticket.severity = severity
        ticket.affected_system = system
        ticket.classification_confidence = cat_confidence
        ticket.keywords = keywords
        if ticket.status == TicketStatus.NEW:
            ticket.status = TicketStatus.TRIAGED

        db.commit()
        self.records_processed += 1
        self.last_run = datetime.utcnow()

        return {
            "ticket_id": ticket.ticket_id,
            "category": category.value,
            "severity": severity.value,
            "affected_system": system.value,
            "confidence": cat_confidence,
            "keywords": keywords,
        }

    def classify_all(self, db: Session) -> Dict[str, Any]:
        """Batch classify all unclassified tickets."""
        tickets = db.query(SupportTicket).filter(
            SupportTicket.category == None
        ).all()

        results = {"classified": 0, "categories": {}}
        for ticket in tickets:
            result = self.classify_ticket(db, ticket.id)
            if "error" not in result:
                results["classified"] += 1
                cat = result["category"]
                results["categories"][cat] = results["categories"].get(cat, 0) + 1

        return results

    def _classify_category(self, text: str) -> Tuple[TicketCategory, float]:
        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score

        if not scores:
            return TicketCategory.OTHER, 0.3

        best = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = min(scores[best] / max(total, 1) + 0.3, 0.98)
        return best, round(confidence, 3)

    def _classify_severity(self, text: str) -> TicketSeverity:
        for severity_name, keywords in SEVERITY_RULES.items():
            if any(kw in text for kw in keywords):
                return TicketSeverity(severity_name)

        if any(w in text for w in ["urgent", "asap", "immediately", "critical"]):
            return TicketSeverity.HIGH
        if any(w in text for w in ["error", "fail", "broken", "not working"]):
            return TicketSeverity.MEDIUM
        return TicketSeverity.LOW

    def _classify_system(self, text: str) -> AffectedSystem:
        scores = {}
        for system, keywords in SYSTEM_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[system] = score

        if not scores:
            return AffectedSystem.OTHER
        return max(scores, key=scores.get)

    def _extract_keywords(self, text: str) -> List[str]:
        all_keywords = []
        for keywords in CATEGORY_KEYWORDS.values():
            all_keywords.extend(keywords)
        for keywords in SYSTEM_KEYWORDS.values():
            all_keywords.extend(keywords)

        found = list(set(kw for kw in all_keywords if kw in text))
        return sorted(found)[:10]

"""
Auto-Resolver Agent — Automatically resolves tickets matching known resolution patterns.

Matches tickets to a knowledge base of resolution patterns. For auto-resolvable patterns,
applies the fix and marks the ticket resolved. For others, suggests resolution steps.

IC Context:
- ServiceIQ's tool-based approach (20+ tools) is the model for auto-resolution
- Common IC support patterns: config toggles, cache clears, known bug workarounds
- Goal: reduce the 13% engineering escalation rate toward 10% target
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import (
    SupportTicket, ResolutionPattern, TicketStatus, TicketCategory
)

logger = logging.getLogger(__name__)


class AutoResolverAgent:
    """Matches tickets to resolution patterns and auto-resolves when possible."""

    def __init__(self):
        self.name = "AutoResolver"
        self.status = "healthy"
        self.last_run: Optional[datetime] = None
        self.records_processed = 0
        self.auto_resolved = 0

    def resolve_ticket(self, db: Session, ticket_id: int) -> Dict[str, Any]:
        """Attempt to auto-resolve a single ticket."""
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            return {"error": "Ticket not found"}

        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED, TicketStatus.AUTO_RESOLVED):
            return {"status": "already_resolved", "ticket_id": ticket.ticket_id}

        # Find matching resolution pattern
        pattern = self._find_matching_pattern(db, ticket)
        if not pattern:
            return {
                "ticket_id": ticket.ticket_id,
                "status": "no_match",
                "message": "No matching resolution pattern found",
            }

        self.records_processed += 1
        self.last_run = datetime.utcnow()

        if pattern.auto_resolvable:
            # Auto-resolve
            ticket.status = TicketStatus.AUTO_RESOLVED
            ticket.resolution_notes = f"Auto-resolved using pattern: {pattern.pattern_name}\n\nSteps:\n{pattern.resolution_steps}"
            ticket.resolution_type = "auto_resolved"
            ticket.resolution_pattern_id = pattern.id
            ticket.resolved_by = "SupportIQ AutoResolver"
            ticket.resolved_at = datetime.utcnow()

            age_hours = (datetime.utcnow() - ticket.created_at).total_seconds() / 3600
            ticket.time_to_resolution_hours = round(age_hours, 2)

            pattern.times_used += 1
            pattern.success_rate = min(pattern.success_rate + 0.01, 0.99)

            db.commit()
            self.auto_resolved += 1

            return {
                "ticket_id": ticket.ticket_id,
                "status": "auto_resolved",
                "pattern": pattern.pattern_name,
                "resolution": pattern.resolution_steps,
                "script_executed": bool(pattern.auto_resolve_script),
                "time_to_resolution_hours": ticket.time_to_resolution_hours,
            }
        else:
            # Suggest resolution
            ticket.resolution_notes = f"Suggested resolution (pattern: {pattern.pattern_name}):\n{pattern.resolution_steps}"
            ticket.resolution_pattern_id = pattern.id
            db.commit()

            return {
                "ticket_id": ticket.ticket_id,
                "status": "suggestion",
                "pattern": pattern.pattern_name,
                "suggested_resolution": pattern.resolution_steps,
                "auto_resolvable": False,
            }

    def auto_resolve_batch(self, db: Session) -> Dict[str, Any]:
        """Attempt to auto-resolve all eligible tickets."""
        eligible = db.query(SupportTicket).filter(
            SupportTicket.status.in_([TicketStatus.NEW, TicketStatus.TRIAGED]),
            SupportTicket.category != None,
        ).all()

        results = {
            "total_checked": len(eligible),
            "auto_resolved": 0,
            "suggestions": 0,
            "no_match": 0,
            "resolved_tickets": [],
        }

        for ticket in eligible:
            result = self.resolve_ticket(db, ticket.id)
            status = result.get("status", "error")
            if status == "auto_resolved":
                results["auto_resolved"] += 1
                results["resolved_tickets"].append(result["ticket_id"])
            elif status == "suggestion":
                results["suggestions"] += 1
            else:
                results["no_match"] += 1

        return results

    def _find_matching_pattern(self, db: Session, ticket: SupportTicket) -> Optional[ResolutionPattern]:
        """Find the best matching resolution pattern for a ticket."""
        text = f"{ticket.title} {ticket.description}".lower()

        # Get patterns for this category
        patterns = db.query(ResolutionPattern).filter(
            ResolutionPattern.category == ticket.category
        ).all()

        # Also check system-specific patterns
        if ticket.affected_system:
            system_patterns = db.query(ResolutionPattern).filter(
                ResolutionPattern.affected_system == ticket.affected_system
            ).all()
            patterns = list(set(patterns + system_patterns))

        best_match = None
        best_score = 0

        for pattern in patterns:
            trigger_keywords = pattern.trigger_keywords or []
            matches = sum(1 for kw in trigger_keywords if kw.lower() in text)
            if matches > 0:
                score = matches / len(trigger_keywords) if trigger_keywords else 0
                # Boost by success rate
                score *= (0.5 + pattern.success_rate * 0.5)
                if score > best_score:
                    best_score = score
                    best_match = pattern

        return best_match if best_score >= 0.2 else None

    def get_knowledge_base(self, db: Session) -> List[Dict[str, Any]]:
        """Return the full resolution pattern knowledge base."""
        patterns = db.query(ResolutionPattern).order_by(ResolutionPattern.times_used.desc()).all()
        return [
            {
                "id": p.id,
                "pattern_name": p.pattern_name,
                "category": p.category.value,
                "affected_system": p.affected_system.value if p.affected_system else None,
                "trigger_keywords": p.trigger_keywords,
                "resolution_steps": p.resolution_steps,
                "auto_resolvable": p.auto_resolvable,
                "success_rate": p.success_rate,
                "times_used": p.times_used,
            }
            for p in patterns
        ]

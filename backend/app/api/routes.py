"""API routes for SupportIQ Insights."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.database import (
    get_db, SupportTicket, ResolutionPattern, EscalationEvent,
    TicketStatus, TicketCategory, AffectedSystem
)

router = APIRouter(prefix="/api/v1")


def get_orchestrator():
    from app.main import orchestrator
    return orchestrator


# --- Ticket Endpoints ---

@router.get("/tickets")
def list_tickets(
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(SupportTicket)
    if status:
        query = query.filter(SupportTicket.status == TicketStatus(status))
    if category:
        query = query.filter(SupportTicket.category == TicketCategory(category))
    tickets = query.order_by(desc(SupportTicket.created_at)).limit(limit).all()
    return [
        {
            "id": t.id,
            "ticket_id": t.ticket_id,
            "title": t.title,
            "biller_name": t.biller_name,
            "status": t.status.value,
            "category": t.category.value if t.category else None,
            "severity": t.severity.value if t.severity else None,
            "affected_system": t.affected_system.value if t.affected_system else None,
            "escalation_probability": t.escalation_probability,
            "escalation_risk": t.escalation_risk,
            "will_need_engineering": t.will_need_engineering,
            "created_at": t.created_at.isoformat(),
        }
        for t in tickets
    ]


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "id": ticket.id,
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "description": ticket.description,
        "reporter_email": ticket.reporter_email,
        "reporter_name": ticket.reporter_name,
        "biller_name": ticket.biller_name,
        "status": ticket.status.value,
        "category": ticket.category.value if ticket.category else None,
        "severity": ticket.severity.value if ticket.severity else None,
        "affected_system": ticket.affected_system.value if ticket.affected_system else None,
        "classification_confidence": ticket.classification_confidence,
        "keywords": ticket.keywords,
        "escalation_probability": ticket.escalation_probability,
        "escalation_risk": ticket.escalation_risk,
        "escalation_factors": ticket.escalation_factors,
        "predicted_resolution_hours": ticket.predicted_resolution_hours,
        "will_need_engineering": ticket.will_need_engineering,
        "resolution_notes": ticket.resolution_notes,
        "resolution_type": ticket.resolution_type,
        "resolved_by": ticket.resolved_by,
        "time_to_resolution_hours": ticket.time_to_resolution_hours,
        "created_at": ticket.created_at.isoformat(),
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


@router.post("/tickets")
def create_ticket(
    title: str = Query(...),
    description: str = Query(...),
    biller_name: str = Query("Unknown"),
    reporter_name: str = Query("Anonymous"),
    db: Session = Depends(get_db),
):
    count = db.query(func.count(SupportTicket.id)).scalar() or 0
    ticket = SupportTicket(
        ticket_id=f"SUP-{20000 + count}",
        title=title,
        description=description,
        biller_name=biller_name,
        reporter_name=reporter_name,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"id": ticket.id, "ticket_id": ticket.ticket_id, "status": ticket.status.value}


# --- Prediction Endpoints ---

@router.get("/predictions/escalation")
def escalation_queue(limit: int = Query(50), db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.predictor.get_escalation_queue(db, limit)


@router.get("/predictions/dashboard")
def dashboard(db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.get_dashboard(db)


# --- Agent Endpoints ---

@router.post("/agents/classify-all")
def classify_all(db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.classifier.classify_all(db)


@router.post("/agents/predict-all")
def predict_all(db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.predictor.predict_all(db)


@router.post("/agents/auto-resolve")
def auto_resolve(db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.resolver.auto_resolve_batch(db)


@router.post("/agents/run-pipeline")
def run_pipeline(db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.run_pipeline(db)


@router.get("/agents/status")
def agent_status():
    orch = get_orchestrator()
    return orch.get_status()


# --- Knowledge Base ---

@router.get("/knowledge-base")
def knowledge_base(db: Session = Depends(get_db)):
    orch = get_orchestrator()
    return orch.resolver.get_knowledge_base(db)


# --- Analytics ---

@router.get("/analytics/by-system")
def analytics_by_system(db: Session = Depends(get_db)):
    results = {}
    for sys in AffectedSystem:
        count = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.affected_system == sys
        ).scalar() or 0
        if count > 0:
            escalated = db.query(func.count(SupportTicket.id)).filter(
                SupportTicket.affected_system == sys,
                SupportTicket.status == TicketStatus.ESCALATED,
            ).scalar() or 0
            results[sys.value] = {"total": count, "escalated": escalated, "escalation_rate": round(escalated / count * 100, 1)}
    return results


@router.get("/analytics/by-category")
def analytics_by_category(db: Session = Depends(get_db)):
    results = {}
    for cat in TicketCategory:
        count = db.query(func.count(SupportTicket.id)).filter(
            SupportTicket.category == cat
        ).scalar() or 0
        if count > 0:
            avg_resolution = db.query(func.avg(SupportTicket.time_to_resolution_hours)).filter(
                SupportTicket.category == cat,
                SupportTicket.time_to_resolution_hours != None,
            ).scalar() or 0
            results[cat.value] = {"total": count, "avg_resolution_hours": round(avg_resolution, 1)}
    return results

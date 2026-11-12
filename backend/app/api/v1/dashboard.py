from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user, tenant_filter
from app.models.client import Client
from app.models.document import Document
from app.models.voucher import Voucher
from app.models.audit_log import AuditLog

router = APIRouter()


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    tid = tenant_filter(user)

    def _c(model, *filters):
        q = select(func.count()).select_from(model)
        if tid and hasattr(model, "tenant_id"):
            q = q.where(model.tenant_id == tid)
        for f in filters:
            q = q.where(f)
        return q

    active_clients   = (await db.execute(_c(Client, Client.is_active == True))).scalar() or 0
    total_docs       = (await db.execute(_c(Document))).scalar() or 0
    total_vouchers   = (await db.execute(_c(Voucher))).scalar() or 0
    pending_vouchers = (await db.execute(_c(Voucher, Voucher.status == "pending_approval"))).scalar() or 0
    approved_vouchers= (await db.execute(_c(Voucher, Voucher.status == "approved"))).scalar() or 0
    posted_vouchers  = (await db.execute(_c(Voucher, Voucher.status.in_(["synced_to_tally", "posted_to_tally"])))).scalar() or 0
    rejected_vouchers= (await db.execute(_c(Voucher, Voucher.status == "rejected"))).scalar() or 0
    review_docs      = (await db.execute(_c(Document, Document.status.in_(["needs_review", "failed"])))).scalar() or 0
    tally_connected  = (await db.execute(_c(Client, Client.tally_company != None))).scalar() or 0

    # Recent activity from audit log
    audit_q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(8)
    if tid:
        audit_q = audit_q.where(AuditLog.tenant_id == tid)
    recent_logs = (await db.execute(audit_q)).scalars().all()

    action_labels = {
        "created": "Voucher created",
        "created_from_document": "Voucher created from document",
        "approved": "Voucher approved",
        "rejected": "Voucher rejected",
        "entries_updated": "Ledger entries updated",
        "posted_to_tally": "Posted to Tally",
        "tally_verified": "Tally posting verified",
        "tally_verify_failed": "Tally verification failed",
        "extraction_complete": "AI extraction complete",
    }
    status_map = {
        "approved": "success",
        "posted_to_tally": "success",
        "tally_verified": "success",
        "rejected": "danger",
        "tally_verify_failed": "danger",
        "pending_approval": "warning",
        "extraction_complete": "default",
        "created": "default",
        "created_from_document": "default",
    }

    activity = []
    for log in recent_logs:
        label = action_labels.get(log.action, log.action.replace("_", " ").title())
        details = log.details or {}
        extra = ""
        if log.entity_type == "voucher" and details.get("amount"):
            extra = f" — AED {details['amount']}"
        elif log.entity_type == "document" and details.get("document_type"):
            extra = f" — {details['document_type']}"
        activity.append({
            "client": log.client_id or log.entity_id,
            "action": f"{label}{extra}",
            "time": log.created_at.strftime("%d %b %H:%M") if log.created_at else "",
            "status": status_map.get(log.action, "default"),
        })

    # Fallback to recent vouchers if audit log is empty
    if not activity:
        v_q = select(Voucher).order_by(Voucher.updated_at.desc()).limit(6)
        if tid:
            v_q = v_q.where(Voucher.tenant_id == tid)
        for v in (await db.execute(v_q)).scalars().all():
            activity.append({
                "client": v.party_name or v.client_id,
                "action": f"{v.voucher_type} — AED {v.amount}",
                "time": v.updated_at.strftime("%d %b %H:%M") if v.updated_at else "",
                "status": "success" if v.status in ("approved", "synced_to_tally") else "warning",
            })

    return {
        "stats": {
            "activeClients": active_clients,
            "documents": total_docs,
            "vouchers": total_vouchers,
            "complianceAlerts": pending_vouchers + review_docs,
        },
        "recentActivity": activity,
        "extraStats": {
            "pendingVouchers": pending_vouchers,
            "approvedVouchers": approved_vouchers,
            "postedVouchers": posted_vouchers,
            "rejectedVouchers": rejected_vouchers,
            "tallyConnected": tally_connected,
            "reviewDocs": review_docs,
        },
    }

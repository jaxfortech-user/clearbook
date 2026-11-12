"""
Document upload, extraction queue, and voucher creation endpoints.
Files are stored on S3; extraction downloads to a temp file, runs Vision API, then cleans up.
"""
import os
import uuid
import tempfile
import boto3
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date

from app.core.database import get_db, AsyncSessionLocal
from app.core.config import settings
from app.core.deps import get_current_user, tenant_filter
from app.models.user import User
from app.models.document import Document
from app.models.voucher import Voucher
from app.models.ledger import Ledger
from app.services.ai_extraction_service import extract_document, suggest_voucher_entries

router = APIRouter()

REVIEW_THRESHOLD = 0.85
HANDWRITTEN_THRESHOLD = 0.75
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".webp", ".xlsx", ".xls", ".csv", ".docx", ".doc"}


# ── S3 helpers ────────────────────────────────────────────────────────────────

def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "AWS_REGION", "us-east-1"),
    )

def _upload_to_s3(file_bytes: bytes, s3_key: str, content_type: str) -> str:
    s3 = _s3_client()
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return s3_key

def _download_from_s3_to_temp(s3_key: str, suffix: str) -> str:
    """Download S3 object to a named temp file. Caller must delete."""
    s3 = _s3_client()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    s3.download_fileobj(settings.S3_BUCKET_NAME, s3_key, tmp)
    tmp.close()
    return tmp.name

def _s3_presigned_url(s3_key: str, expiry: int = 3600) -> str:
    s3 = _s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expiry,
    )


# ── Background extraction ─────────────────────────────────────────────────────

async def _run_extraction(doc_id: str):
    """Background task: download from S3, extract with Vision API, update DB."""
    tmp_path = None
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Document).filter(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if not doc:
                return

            doc.status = "processing"
            doc.updated_at = datetime.utcnow()
            await db.commit()

            suffix = f".{doc.file_type}" if doc.file_type else ".jpg"
            tmp_path = _download_from_s3_to_temp(doc.s3_key, suffix)

            result_data = extract_document(tmp_path)

            confidence = float(result_data.get("overall_confidence") or 0)
            is_handwritten = bool(result_data.get("is_handwritten", False))
            threshold = HANDWRITTEN_THRESHOLD if is_handwritten else REVIEW_THRESHOLD

            doc.extracted_data = result_data
            doc.confidence_score = confidence
            doc.is_handwritten = is_handwritten
            doc.document_type = result_data.get("document_type")
            doc.status = "extracted" if confidence >= threshold else "needs_review"
            doc.updated_at = datetime.utcnow()

            from app.services.audit_service import log as audit_log
            await audit_log(db, "document", doc.id, "extraction_complete",
                            client_id=doc.client_id,
                            details={"document_type": doc.document_type,
                                     "confidence": confidence,
                                     "status": doc.status,
                                     "is_handwritten": is_handwritten})
            await db.commit()

        except Exception as e:
            await db.rollback()
            try:
                result = await db.execute(select(Document).filter(Document.id == doc_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    doc.extracted_data = {"error": str(e)}
                    doc.updated_at = datetime.utcnow()
                    await db.commit()
            except Exception:
                pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    client_id: str = Query(None),
    file: UploadFile = File(...),
    uploaded_by: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    file_bytes = await file.read()
    file_type = ext.lstrip(".")

    doc_id = str(uuid.uuid4())
    s3_key = f"documents/{client_id or 'unassigned'}/{doc_id}{ext}"

    content_type_map = {
        "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp",
    }
    content_type = content_type_map.get(file_type, "application/octet-stream")
    _upload_to_s3(file_bytes, s3_key, content_type)

    tid = tenant_filter(user) or "system"
    doc = Document(
        id=doc_id,
        tenant_id=tid,
        client_id=client_id,
        file_name=file.filename,
        file_type=file_type,
        s3_key=s3_key,
        status="uploaded",
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    background_tasks.add_task(_run_extraction, doc.id)

    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status,
        "message": "File uploaded. Extraction started in background.",
    }


@router.get("/client/{client_id}")
async def list_documents_by_client(
    client_id: str,
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Frontend calls GET /documents/client/{clientId} — this route handles it."""
    q = select(Document).filter(Document.client_id == client_id)
    if status:
        q = q.filter(Document.status == status)
    q = q.order_by(Document.created_at.desc()).limit(100)
    result = await db.execute(q)
    docs = result.scalars().all()
    return [_doc_to_dict(d) for d in docs]


@router.get("/")
async def list_documents(
    client_id: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Document)
    tid = tenant_filter(user)
    if tid:
        q = q.filter(Document.tenant_id == tid)
    if client_id:
        q = q.filter(Document.client_id == client_id)
    if status:
        q = q.filter(Document.status == status)
    q = q.order_by(Document.created_at.desc()).limit(100)
    result = await db.execute(q)
    docs = result.scalars().all()
    return [_doc_to_dict(d) for d in docs]


@router.get("/review-queue")
async def review_queue(db: AsyncSession = Depends(get_db)):
    q = (
        select(Document)
        .filter(Document.status.in_(["needs_review", "failed"]))
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(q)
    docs = result.scalars().all()
    return [_doc_to_dict(d) for d in docs]


@router.get("/{doc_id}/file-url")
async def get_document_file_url(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Returns a short-lived S3 presigned URL for browser preview."""
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    url = _s3_presigned_url(doc.s3_key)
    return {"url": url, "expires_in": 3600}


@router.get("/{doc_id}")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return _doc_to_dict(doc)


@router.post("/{doc_id}/extract")
async def trigger_extraction(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.status = "uploaded"
    await db.commit()
    background_tasks.add_task(_run_extraction, doc_id)
    return {"message": "Extraction restarted"}


@router.put("/{doc_id}/extracted-data")
async def update_extracted_data(
    doc_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.extracted_data = payload.get("extracted_data", doc.extracted_data)
    if payload.get("confidence_score") is not None:
        doc.confidence_score = payload["confidence_score"]
    doc.status = "reviewed"
    doc.updated_at = datetime.utcnow()
    await db.commit()
    return {"message": "Corrections saved", "status": doc.status}


@router.post("/{doc_id}/create-voucher")
async def create_voucher_from_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.extracted_data:
        raise HTTPException(400, "No extracted data. Run extraction first.")

    # Duplicate detection: check if a voucher for this invoice number already exists
    from app.api.v1.vouchers import check_duplicate_invoice
    invoice_number = (
        doc.extracted_data.get("document_number")
        or doc.extracted_data.get("invoice_number")
    )
    duplicate_id = await check_duplicate_invoice(db, doc.client_id, invoice_number or "")
    if duplicate_id:
        raise HTTPException(
            409,
            f"Duplicate invoice detected. A voucher for invoice '{invoice_number}' "
            f"already exists (voucher ID: {duplicate_id}). "
            "If this is a different document, adjust the narration before creating."
        )

    suggestion = suggest_voucher_entries(doc.extracted_data)

    # Auto-create any missing ledgers in the tenant's master
    tid = tenant_filter(user) or "system"
    await _ensure_ledgers(db, tid, suggestion.get("entries", []))

    voucher = Voucher(
        id=str(uuid.uuid4()),
        tenant_id=tenant_filter(user) or "system",
        client_id=doc.client_id,
        document_id=doc.id,
        voucher_type=suggestion.get("voucher_type", "journal"),
        narration=suggestion.get("narration", ""),
        amount=float(suggestion.get("total_amount") or 0),
        currency=suggestion.get("currency", "AED"),
        ledger_entries=suggestion.get("entries", suggestion),
        voucher_date=date.today(),
        status="draft",
    )
    db.add(voucher)

    from app.services.audit_service import log as audit_log
    await audit_log(db, "voucher", voucher.id, "created_from_document",
                    client_id=doc.client_id,
                    details={"document_id": doc.id, "invoice_number": invoice_number,
                             "voucher_type": voucher.voucher_type, "amount": float(voucher.amount)},
                    tenant_id=tenant_filter(user))

    doc.status = "voucher_created"
    doc.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "id": voucher.id,
        "voucher_id": voucher.id,
        "voucher_type": voucher.voucher_type,
        "amount": float(voucher.amount),
        "status": voucher.status,
    }


# ── Ledger auto-create ────────────────────────────────────────────────────────

# Default Tally group for common ledger names used in UAE accounting
_LEDGER_GROUP_MAP: dict[str, str] = {
    # Purchases & expenses
    "Purchase Account":      "Purchase Accounts",
    "Purchases":             "Purchase Accounts",
    "Purchase Return":       "Purchase Accounts",
    "Direct Expenses":       "Direct Expenses",
    "Indirect Expenses":     "Indirect Expenses",
    "Freight Charges":       "Direct Expenses",
    "Petty Cash Expenses":   "Indirect Expenses",
    # VAT
    "Input VAT":             "Duties & Taxes",
    "Output VAT":            "Duties & Taxes",
    "VAT Payable":           "Duties & Taxes",
    "VAT Recoverable":       "Duties & Taxes",
    # Sales & income
    "Sales Account":         "Sales Accounts",
    "Sales":                 "Sales Accounts",
    "Scrap Sales":           "Sales Accounts",
    "Service Revenue":       "Sales Accounts",
    # Cash & bank
    "Cash":                  "Cash-in-Hand",
    "Petty Cash":            "Cash-in-Hand",
    "Bank":                  "Bank Accounts",
    "Bank Account":          "Bank Accounts",
    # Liabilities / assets
    "Suspense Account":      "Suspense A/c",
}

def _guess_group(name: str, is_debit: bool) -> str:
    """Guess Tally group from ledger name; fall back by DR/CR."""
    for key, grp in _LEDGER_GROUP_MAP.items():
        if key.lower() in name.lower():
            return grp
    # Heuristic: debit lines are usually assets/expenses; credit lines liabilities/income
    return "Sundry Debtors" if is_debit else "Sundry Creditors"


async def _ensure_ledgers(db: AsyncSession, tenant_id: str, entries: list[dict]) -> None:
    """Create ledger master records for any ledger names not yet in the tenant's master."""
    if not entries:
        return
    for entry in entries:
        name: str = entry.get("ledger_name", "").strip()
        if not name:
            continue
        existing = await db.execute(
            select(Ledger).where(Ledger.tenant_id == tenant_id, Ledger.tally_name == name)
        )
        if existing.scalar_one_or_none():
            continue  # already exists
        group = _guess_group(name, bool(entry.get("is_debit", True)))
        db.add(Ledger(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            tally_name=name,
            group=group,
            description=f"Auto-created from document extraction",
        ))
    # flush so the records exist before the outer commit
    await db.flush()


# ── Helper ────────────────────────────────────────────────────────────────────

def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "client_id": doc.client_id,
        "filename": doc.file_name,
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "s3_key": doc.s3_key,
        "status": doc.status,
        "extraction_status": doc.status,
        "document_type": doc.document_type,
        "confidence_score": doc.confidence_score,
        "is_handwritten": doc.is_handwritten,
        "extracted_data": doc.extracted_data,
        "notes": doc.notes,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }

@router.patch("/{doc_id}/assign-client")
async def assign_client(
    doc_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign or reassign a client to a document."""
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.client_id = payload.get("client_id")
    doc.updated_at = datetime.utcnow()
    await db.commit()
    return {"id": doc.id, "client_id": doc.client_id, "message": "Client assigned"}

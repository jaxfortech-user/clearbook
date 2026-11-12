import base64
import io
import json
from pathlib import Path
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

EXTRACTION_PROMPT = """You are a precise UAE accounting document extractor. Always return valid JSON only.

Extract structured data from this document. Return a JSON object with ALL of these fields (use null if not found):
{
    "document_type": "purchase_invoice|sales_invoice|receipt|bank_statement|purchase_order|credit_note|debit_note|petty_cash|delivery_note|other",
    "is_handwritten": false,
    "language": "english|arabic|mixed",
    "vendor_name": "string or null",
    "vendor_trn": "15-digit UAE TRN or null",
    "buyer_name": "string or null",
    "buyer_trn": "15-digit UAE TRN or null",
    "document_number": "invoice/receipt number or null",
    "invoice_number": "same as document_number for compatibility",
    "document_date": "YYYY-MM-DD or null",
    "invoice_date": "same as document_date for compatibility",
    "due_date": "YYYY-MM-DD or null",
    "subtotal": numeric or null,
    "vat_amount": numeric or null,
    "vat_rate": numeric percentage or null,
    "total_amount": numeric or null,
    "currency": "AED|USD|EUR etc",
    "line_items": [
        {
            "description": "string",
            "quantity": numeric or null,
            "unit_price": numeric or null,
            "vat_rate": numeric or null,
            "amount": numeric or null
        }
    ],
    "payment_method": "cash|bank_transfer|cheque|card or null",
    "notes": "any other relevant information or null",
    "confidence_scores": {
        "vendor_name": 0.95,
        "document_number": 0.98,
        "document_date": 0.97,
        "total_amount": 0.99,
        "vat_amount": 0.92
    },
    "overall_confidence": 0.95,
    "extraction_notes": "flag any issues, low quality scan, partial data, handwriting difficulty etc"
}

RULES:
- document_type MUST be one of the values listed above
- is_handwritten: true if any part of the document is handwritten
- overall_confidence: weighted average 0.0-1.0 (be honest - penalise blurry, handwritten, partial docs)
- For Arabic handwriting, overall_confidence should rarely exceed 0.75
- Null for missing fields, never empty string
"""


# -- Your original functions (unchanged) ------------------------------------

def extract_structured_data(raw_text: str, forms: dict) -> dict:
    """Extract from raw text (e.g. from AWS Textract or pdfplumber)."""
    combined_text = raw_text
    if forms:
        combined_text += "\n\nForm fields detected:\n"
        for k, v in forms.items():
            combined_text += f"{k}: {v}\n"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise UAE accounting document extractor. Always return valid JSON only."},
            {"role": "user", "content": EXTRACTION_PROMPT + "\n\nDocument text:\n" + combined_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def extract_from_image_with_vision(image_bytes: bytes, mime_type: str) -> dict:
    """Extract from image bytes using GPT-4o Vision."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise UAE accounting document extractor. Always return valid JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}", "detail": "high"}},
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


# -- New: file-path wrapper (called by background task in documents.py) --------

def extract_document(file_path: str) -> dict:
    """
    Main entry point for the background extraction task.
    Reads a file from disk and routes to vision or text extraction.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        image_bytes, mime_type = _pdf_to_image(file_path)
        return extract_from_image_with_vision(image_bytes, mime_type)

    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    with open(file_path, "rb") as f:
        image_bytes = f.read()
    return extract_from_image_with_vision(image_bytes, mime_type)


def _pdf_to_image(pdf_path: str) -> tuple[bytes, str]:
    """
    Convert first page of PDF to PNG for Vision API.

    Tries pymupdf (fitz) first — no system dependencies needed.
    Falls back to pdf2image (requires poppler).
    Raises if neither is available so the caller gets a clear error
    instead of silently sending raw PDF bytes that the Vision API rejects.
    """
    # --- Attempt 1: pymupdf (pip install pymupdf) ---
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        page = doc[0]
        # Render at 2x zoom (150 dpi equivalent) for good OCR quality
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        buf = io.BytesIO(pix.tobytes("png"))
        doc.close()
        return buf.getvalue(), "image/png"
    except ImportError:
        pass  # pymupdf not installed, try next
    except Exception as e:
        raise RuntimeError(f"pymupdf failed to convert PDF: {e}") from e

    # --- Attempt 2: pdf2image (pip install pdf2image + poppler) ---
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=200)
        buf = io.BytesIO()
        images[0].save(buf, format="PNG")
        return buf.getvalue(), "image/png"
    except ImportError:
        pass  # pdf2image not installed either
    except Exception as e:
        raise RuntimeError(f"pdf2image failed to convert PDF: {e}") from e

    # --- Neither library available ---
    raise RuntimeError(
        "Cannot convert PDF to image: neither 'pymupdf' nor 'pdf2image' is installed. "
        "Run: pip install pymupdf"
    )


# -- Voucher suggestion (called by POST /documents/{id}/create-voucher) -------

def suggest_voucher_entries(extracted_data: dict) -> dict:
    """Rule-based ledger mapping from extracted document data."""
    doc_type = extracted_data.get("document_type", "other")
    total = float(extracted_data.get("total_amount") or 0)
    subtotal = float(extracted_data.get("subtotal") or 0)
    vat_amount = float(extracted_data.get("vat_amount") or 0)
    vendor = extracted_data.get("vendor_name") or "Supplier"
    buyer = extracted_data.get("buyer_name") or "Customer"
    currency = extracted_data.get("currency") or "AED"
    narration = _build_narration(extracted_data)

    if doc_type in ["purchase_invoice", "receipt"]:
        return {
            "voucher_type": "Purchase",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "entries": [
                {"ledger_name": "Purchase Account", "is_debit": True, "amount": subtotal, "notes": "Purchase/expense (excl VAT)"},
                {"ledger_name": "Input VAT", "is_debit": True, "amount": vat_amount, "notes": "5% input VAT - recoverable"},
                {"ledger_name": vendor, "is_debit": False, "amount": total, "notes": "Supplier payable"},
            ],
        }
    elif doc_type == "sales_invoice":
        return {
            "voucher_type": "Sales",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "entries": [
                {"ledger_name": buyer, "is_debit": True, "amount": total, "notes": "Customer receivable"},
                {"ledger_name": "Sales Account", "is_debit": False, "amount": subtotal, "notes": "Revenue"},
                {"ledger_name": "Output VAT", "is_debit": False, "amount": vat_amount, "notes": "5% output VAT - payable to FTA"},
            ],
        }
    elif doc_type == "credit_note":
        return {
            "voucher_type": "Credit Note",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "entries": [
                {"ledger_name": vendor, "is_debit": True, "amount": total, "notes": "Reduce supplier payable"},
                {"ledger_name": "Purchase Return", "is_debit": False, "amount": subtotal, "notes": "Return"},
                {"ledger_name": "Input VAT", "is_debit": False, "amount": vat_amount, "notes": "Reverse input VAT"},
            ],
        }
    elif doc_type == "petty_cash":
        return {
            "voucher_type": "Payment",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "entries": [
                {"ledger_name": "Petty Cash Expenses", "is_debit": True, "amount": subtotal, "notes": "Petty cash expense"},
                {"ledger_name": "Input VAT", "is_debit": True, "amount": vat_amount, "notes": "Input VAT if applicable"},
                {"ledger_name": "Petty Cash", "is_debit": False, "amount": total, "notes": "Cash outflow"},
            ],
        }
    else:
        return {
            "voucher_type": "Journal",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "entries": [
                {"ledger_name": "Suspense Account", "is_debit": True, "amount": total, "notes": "Requires manual classification"},
                {"ledger_name": "Suspense Account", "is_debit": False, "amount": total, "notes": "Requires manual classification"},
            ],
        }


def _build_narration(extracted: dict) -> str:
    type_labels = {
        "purchase_invoice": "Purchase Invoice",
        "sales_invoice": "Sales Invoice",
        "receipt": "Receipt",
        "petty_cash": "Petty Cash Voucher",
        "credit_note": "Credit Note",
        "debit_note": "Debit Note",
        "bank_statement": "Bank Statement",
        "delivery_note": "Delivery Note",
    }
    label = type_labels.get(extracted.get("document_type", ""), "Document")
    parts = [label]
    # Support both field naming conventions
    doc_num = extracted.get("document_number") or extracted.get("invoice_number")
    doc_date = extracted.get("document_date") or extracted.get("invoice_date")
    if doc_num:
        parts.append(f"#{doc_num}")
    if extracted.get("vendor_name"):
        parts.append(f"from {extracted['vendor_name']}")
    elif extracted.get("buyer_name"):
        parts.append(f"to {extracted['buyer_name']}")
    if doc_date:
        parts.append(f"dated {doc_date}")
    return " ".join(parts)
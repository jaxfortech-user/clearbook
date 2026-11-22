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
    "invoice_subtype": "item_invoice|accounting_invoice",
    "is_handwritten": false,
    "language": "english|arabic|mixed",
    "vendor_name": "string or null",
    "vendor_trn": "15-digit UAE TRN or null",
    "vendor_address": "string or null",
    "buyer_name": "string or null",
    "buyer_trn": "15-digit UAE TRN or null",
    "buyer_address": "string or null",
    "document_number": "invoice/receipt number or null",
    "invoice_number": "same as document_number for compatibility",
    "document_date": "YYYY-MM-DD or null",
    "invoice_date": "same as document_date for compatibility",
    "due_date": "YYYY-MM-DD or null",
    "delivery_note_number": "string or null",
    "dispatch_details": "string or null",
    "subtotal": numeric or null,
    "vat_amount": numeric or null,
    "vat_rate": numeric percentage (e.g. 5 for 5%) or null,
    "total_amount": numeric or null,
    "currency": "AED|USD|EUR etc",
    "line_items": [
        {
            "description": "item or service name",
            "quantity": numeric or null,
            "unit": "pcs|kg|hrs|nos|box|set or null",
            "unit_price": numeric or null,
            "per": "unit label as printed on invoice e.g. Nos, Pcs, KG or null",
            "vat_rate": numeric percentage or null,
            "amount": numeric or null
        }
    ],
    "payment_method": "cash|bank_transfer|cheque|card or null",
    "bank_account": "bank name or account reference if mentioned or null",
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
- invoice_subtype: use "item_invoice" if the invoice has physical goods with quantity/rate/unit columns;
  use "accounting_invoice" if it's a service or single-amount billing (no stock items)
- is_handwritten: true if any part of the document is handwritten
- overall_confidence: weighted average 0.0-1.0 (be honest - penalise blurry, handwritten, partial docs)
- For Arabic handwriting, overall_confidence should rarely exceed 0.75
- line_items: extract EVERY line item shown on the invoice, including services; never skip any line
- For item invoices: always capture quantity, unit_price, per, and amount for each line
- vat_rate: extract the actual percentage shown (e.g. 5 for UAE VAT, not 0.05)
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
    """
    Build complete voucher suggestion from extracted document data.
    - Detects item vs accounting invoice automatically
    - Populates stock_items for item invoices
    - Always adds VAT as a named ledger line when present
    - Returns ledger entries balanced to zero
    """
    doc_type = extracted_data.get("document_type", "other")
    invoice_subtype = extracted_data.get("invoice_subtype") or "accounting_invoice"
    total = float(extracted_data.get("total_amount") or 0)
    subtotal = float(extracted_data.get("subtotal") or total)
    vat_amount = float(extracted_data.get("vat_amount") or 0)
    vat_rate = extracted_data.get("vat_rate")
    vendor = extracted_data.get("vendor_name") or "Supplier"
    buyer = extracted_data.get("buyer_name") or "Customer"
    currency = extracted_data.get("currency") or "AED"
    narration = _build_narration(extracted_data)
    line_items = extracted_data.get("line_items") or []

    # Recalculate subtotal from line items if more accurate
    if line_items:
        computed_subtotal = sum(float(li.get("amount") or 0) for li in line_items)
        if computed_subtotal > 0:
            subtotal = computed_subtotal

    # Build stock_items (for item invoices with physical goods)
    has_stock_items = (
        invoice_subtype == "item_invoice"
        and any(li.get("quantity") for li in line_items)
    )
    stock_items = []
    if has_stock_items:
        for li in line_items:
            qty = li.get("quantity")
            if qty is None:
                continue
            stock_items.append({
                "name": li.get("description") or "Item",
                "quantity": float(qty),
                "unit": li.get("unit") or li.get("per") or "Nos",
                "unit_price": float(li.get("unit_price") or 0),
                "per": li.get("per") or li.get("unit") or "Nos",
                "amount": float(li.get("amount") or 0),
                "vat_rate": float(li.get("vat_rate") or vat_rate or 0),
            })

    # VAT ledger name with rate if known
    vat_label_in = f"Input VAT {vat_rate}%" if vat_rate else "Input VAT"
    vat_label_out = f"Output VAT {vat_rate}%" if vat_rate else "Output VAT"

    if doc_type in ["purchase_invoice", "receipt"]:
        entries = []
        if has_stock_items:
            # Each stock item maps to its own purchase ledger line
            for item in stock_items:
                entries.append({
                    "ledger_name": "Purchase Account",
                    "is_debit": True,
                    "amount": round(item["amount"], 2),
                    "notes": f"{item['name']} – {item['quantity']} {item['per']} @ {item['unit_price']}",
                })
        else:
            entries.append({
                "ledger_name": "Purchase Account",
                "is_debit": True,
                "amount": round(subtotal, 2),
                "notes": "Purchase/expense (excl VAT)",
            })
        if vat_amount > 0:
            entries.append({
                "ledger_name": vat_label_in,
                "is_debit": True,
                "amount": round(vat_amount, 2),
                "notes": f"Input VAT recoverable",
            })
        entries.append({
            "ledger_name": vendor,
            "is_debit": False,
            "amount": round(total, 2),
            "notes": "Supplier payable",
        })
        return {
            "voucher_type": "Purchase",
            "invoice_subtype": invoice_subtype,
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "stock_items": stock_items,
            "entries": entries,
        }

    elif doc_type == "sales_invoice":
        entries = [{"ledger_name": buyer, "is_debit": True, "amount": round(total, 2), "notes": "Customer receivable"}]
        if has_stock_items:
            for item in stock_items:
                entries.append({
                    "ledger_name": "Sales Account",
                    "is_debit": False,
                    "amount": round(item["amount"], 2),
                    "notes": f"{item['name']} – {item['quantity']} {item['per']} @ {item['unit_price']}",
                })
        else:
            entries.append({"ledger_name": "Sales Account", "is_debit": False, "amount": round(subtotal, 2), "notes": "Revenue"})
        if vat_amount > 0:
            entries.append({
                "ledger_name": vat_label_out,
                "is_debit": False,
                "amount": round(vat_amount, 2),
                "notes": "Output VAT payable to FTA",
            })
        return {
            "voucher_type": "Sales",
            "invoice_subtype": invoice_subtype,
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "stock_items": stock_items,
            "entries": entries,
        }

    elif doc_type == "credit_note":
        return {
            "voucher_type": "Credit Note",
            "invoice_subtype": invoice_subtype,
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "stock_items": [],
            "entries": [
                {"ledger_name": vendor, "is_debit": True, "amount": round(total, 2), "notes": "Reduce supplier payable"},
                {"ledger_name": "Purchase Return", "is_debit": False, "amount": round(subtotal, 2), "notes": "Return"},
                {"ledger_name": vat_label_in, "is_debit": False, "amount": round(vat_amount, 2), "notes": "Reverse input VAT"},
            ],
        }

    elif doc_type == "petty_cash":
        return {
            "voucher_type": "Payment",
            "invoice_subtype": "accounting_invoice",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "stock_items": [],
            "entries": [
                {"ledger_name": "Petty Cash Expenses", "is_debit": True, "amount": round(subtotal, 2), "notes": "Petty cash expense"},
                {"ledger_name": vat_label_in, "is_debit": True, "amount": round(vat_amount, 2), "notes": "Input VAT if applicable"},
                {"ledger_name": "Petty Cash", "is_debit": False, "amount": round(total, 2), "notes": "Cash outflow"},
            ],
        }

    else:
        return {
            "voucher_type": "Journal",
            "invoice_subtype": "accounting_invoice",
            "narration": narration,
            "currency": currency,
            "total_amount": total,
            "stock_items": [],
            "entries": [
                {"ledger_name": "Suspense Account", "is_debit": True, "amount": round(total, 2), "notes": "Requires manual classification"},
                {"ledger_name": "Suspense Account", "is_debit": False, "amount": round(total, 2), "notes": "Requires manual classification"},
            ],
        }


def extract_bank_statement(file_path: str) -> dict:
    """
    Extract all transactions from a bank statement (PDF/CSV/Excel/image).
    Returns a dict with transactions list and statement metadata.
    """
    import csv
    ext = Path(file_path).suffix.lower()

    if ext in (".csv",):
        return _extract_bank_statement_csv(file_path)

    if ext in (".xlsx", ".xls"):
        return _extract_bank_statement_excel(file_path)

    # PDF or image — use Vision API
    if ext == ".pdf":
        image_bytes, mime_type = _pdf_to_image(file_path)
    else:
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/jpeg")
        with open(file_path, "rb") as f:
            image_bytes = f.read()

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = _BANK_STATEMENT_PROMPT

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise bank statement extractor. Always return valid JSON only."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}", "detail": "high"}},
            ]},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def _extract_bank_statement_csv(file_path: str) -> dict:
    """Parse a CSV bank statement — send raw text to GPT to extract structured transactions."""
    import csv as csv_mod
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv_mod.reader(f)
            for row in reader:
                rows.append(",".join(row))
        raw_text = "\n".join(rows[:200])
    except Exception as e:
        return {"transactions": [], "error": str(e)}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise bank statement extractor. Always return valid JSON only."},
            {"role": "user", "content": _BANK_STATEMENT_PROMPT + "\n\nBank statement CSV:\n" + raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def _extract_bank_statement_excel(file_path: str) -> dict:
    """Parse an Excel bank statement — convert to text then send to GPT."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(max_row=200, values_only=True):
            rows.append("\t".join(str(c) if c is not None else "" for c in row))
        raw_text = "\n".join(rows)
        wb.close()
    except Exception:
        try:
            import xlrd
            wb = xlrd.open_workbook(file_path)
            ws = wb.sheet_by_index(0)
            rows = ["\t".join(str(ws.cell_value(r, c)) for c in range(ws.ncols)) for r in range(min(200, ws.nrows))]
            raw_text = "\n".join(rows)
        except Exception as e:
            return {"transactions": [], "error": str(e)}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise bank statement extractor. Always return valid JSON only."},
            {"role": "user", "content": _BANK_STATEMENT_PROMPT + "\n\nBank statement data:\n" + raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


_BANK_STATEMENT_PROMPT = """Extract all transactions from this bank statement. Return a JSON object:
{
    "bank_name": "string or null",
    "account_number": "last 4 digits or null",
    "account_holder": "string or null",
    "currency": "AED or other",
    "period_start": "YYYY-MM-DD or null",
    "period_end": "YYYY-MM-DD or null",
    "opening_balance": numeric or null,
    "closing_balance": numeric or null,
    "transactions": [
        {
            "date": "YYYY-MM-DD",
            "description": "full transaction description as printed",
            "debit": numeric or 0,
            "credit": numeric or 0,
            "balance": numeric or null,
            "reference": "cheque number or reference if shown or null"
        }
    ]
}

RULES:
- Extract EVERY transaction row — do not skip any
- debit = money going OUT (negative cash flow), credit = money coming IN (positive)
- If the statement shows a single signed amount column: negative = debit, positive = credit
- dates must be YYYY-MM-DD format
- amounts must be numeric (no currency symbols, no commas)
- description: copy the full text exactly as shown
- balance: running balance after each transaction if shown
"""


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
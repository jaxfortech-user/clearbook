from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.tally_routing import route_tally_xml
from app.core.deps import get_current_user
from app.models.client import Client
from app.models.tenant import Tenant

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TallyConfig(BaseModel):
    host: str = "localhost"
    port: int = 9000


class TallySettingsUpdate(BaseModel):
    tally_host: Optional[str] = None
    tally_port: Optional[int] = None
    tally_company: Optional[str] = None
    tally_edu_mode: Optional[bool] = None


# ── DB-backed settings endpoints (Gap 3 fix) ─────────────────────────────────

@router.get("/settings/{client_id}")
async def get_tally_settings(client_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Fetch the tenant's connector_api_key
    t_result = await db.execute(select(Tenant).where(Tenant.id == client.tenant_id))
    tenant = t_result.scalar_one_or_none()
    return {
        "client_id": client.id,
        "tally_host": client.tally_host or "localhost",
        "tally_port": client.tally_port or 9000,
        "tally_company": client.tally_company or "",
        "tally_edu_mode": client.tally_edu_mode or False,
        "tally_connector_status": client.tally_connector_status or "not_installed",
        "connector_api_key": tenant.connector_api_key if tenant else "",
    }


@router.patch("/settings/{client_id}")
async def update_tally_settings(
    client_id: str,
    payload: TallySettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.tally_host is not None:
        client.tally_host = payload.tally_host
    if payload.tally_port is not None:
        client.tally_port = payload.tally_port
    if payload.tally_company is not None:
        client.tally_company = payload.tally_company
    if payload.tally_edu_mode is not None:
        client.tally_edu_mode = payload.tally_edu_mode

    await db.commit()
    await db.refresh(client)
    return {"success": True, "client_id": client.id}


@router.get("/test/{client_id}")
async def test_tally_connection(client_id: str, db: AsyncSession = Depends(get_db)):
    """Test Tally connection via tunnel (production) or direct HTTP (dev)."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    xml = """<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

    try:
        response = await route_tally_xml(client, xml)
        return {"connected": True, "message": "Connected to Tally successfully.", "bytes": len(response)}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Tally unreachable: {str(e)}")


# ── Legacy direct test (dev only) ────────────────────────────────────────────

@router.post("/test-connection")
def test_tally_connection_direct(config: TallyConfig):
    xml = """<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""
    try:
        response = _post_tally_xml(config.host, config.port, xml)
        return {"connected": True, "message": "Connected to Tally successfully.", "bytes": len(response)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Tally unreachable: {str(e)}")


@router.post("/companies")
def list_tally_companies(config: TallyConfig):
    xml = """<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME>
<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""
    try:
        response = _post_tally_xml(config.host, config.port, xml)
        root = ET.fromstring(response)
        companies = [c.text for c in root.iter("BASICCOMPANYNAME") if c.text]
        return {"companies": companies}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Tally unreachable: {str(e)}")


# ── Voucher import ────────────────────────────────────────────────────────────

class VoucherEntry(BaseModel):
    ledger_name: str
    is_debit: bool
    amount: float


class VoucherRequest(BaseModel):
    client_id: str
    company: str
    voucher_type: str
    date: date
    narration: str
    entries: list[VoucherEntry]
    auto_create_ledgers: bool = False


@router.post("/voucher")
async def post_voucher(payload: VoucherRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == payload.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    entries = [e.dict() for e in payload.entries]

    if payload.auto_create_ledgers:
        try:
            created = _ensure_ledgers_exist_async_wrapper(
                payload.company, client, entries, payload.voucher_type
            )
        except RuntimeError as e:
            raise HTTPException(status_code=422, detail=str(e))

    xml = _build_voucher_xml(
        payload.company, payload.voucher_type,
        payload.date, payload.narration, entries
    )

    try:
        response = await route_tally_xml(client, xml)
        voucher_number = _extract_voucher_number(response)
        return {
            "success": True,
            "voucher_number": voucher_number,
            "tally_response_bytes": len(response),
        }
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── XML helpers (unchanged from your original) ───────────────────────────────

def _post_tally_xml(host: str, port: int, xml_body: str) -> str:
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"http://{host}:{port}",
            content=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
        )
        response.raise_for_status()
        return response.text


def _build_voucher_xml(company, voucher_type, date, narration, entries,
                       stock_items=None, invoice_subtype=None) -> str:
    """
    Build Tally Import XML for a voucher.
    - stock_items present + invoice_subtype == 'item_invoice' → Item Invoice view with inventory lines
    - Otherwise → standard Accounting Voucher view
    """
    tally_date = date.strftime("%Y%m%d")
    vch_type_map = {
        "payment": "Payment", "receipt": "Receipt", "journal": "Journal",
        "contra": "Contra", "sales": "Sales", "purchase": "Purchase",
        "credit note": "Credit Note", "debit note": "Debit Note",
    }
    tally_vch_type = vch_type_map.get((voucher_type or "journal").lower(), "Journal")
    bill_types = {"payment", "receipt"}
    use_bill = tally_vch_type.lower() in bill_types
    is_item_invoice = (
        invoice_subtype == "item_invoice"
        and stock_items
        and len(stock_items) > 0
    )
    ledger_xml = ""
    for entry in entries:
        ledger_name = entry.get("ledger_name", "")
        is_debit = entry.get("is_debit", True)
        amount = float(entry.get("amount", 0))
        bill_ref = entry.get("bill_ref", "")
        cost_centre = entry.get("cost_centre") or ""
        tally_amount = amount if not is_debit else -amount
        is_deemed_positive = "Yes" if is_debit else "No"
        bill_xml = ""
        if use_bill and bill_ref:
            bill_xml = f"""
            <BILLALLOCATIONS.LIST>
              <NAME>{_xml_escape(bill_ref)}</NAME>
              <BILLTYPE>Against Ref</BILLTYPE>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>
            </BILLALLOCATIONS.LIST>"""
        cost_centre_xml = ""
        if cost_centre:
            cost_centre_xml = f"""
            <COSTCENTREALLOCATION.LIST>
              <NAME>{_xml_escape(cost_centre)}</NAME>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>
            </COSTCENTREALLOCATION.LIST>"""
        ledger_xml += f"""
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{_xml_escape(ledger_name)}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>{is_deemed_positive}</ISDEEMEDPOSITIVE>
            <AMOUNT>{tally_amount:.2f}</AMOUNT>{bill_xml}{cost_centre_xml}
          </ALLLEDGERENTRIES.LIST>"""

    if not is_item_invoice:
        obj_view = "Accounting Voucher View"
        # Consolidate duplicate ledger entries and find party ledger
        from collections import defaultdict as _dd
        _consolidated: dict[tuple, float] = _dd(float)
        _entry_meta: dict[tuple, dict] = {}
        for _e in entries:
            _k = (_e.get("ledger_name", ""), bool(_e.get("is_debit", True)))
            _amt = float(_e.get("amount", 0))
            _consolidated[_k] += -_amt if _k[1] else _amt
            if _k not in _entry_meta:
                _entry_meta[_k] = _e
        ledger_xml = ""
        party_name = ""
        for (_ln, _is_dr), _ta in _consolidated.items():
            _idp = "Yes" if _is_dr else "No"
            _e = _entry_meta[(_ln, _is_dr)]
            _br = _e.get("bill_ref", "")
            _cc = _e.get("cost_centre") or ""
            _bxml = f"""
            <BILLALLOCATIONS.LIST>
              <NAME>{_xml_escape(_br)}</NAME>
              <BILLTYPE>Against Ref</BILLTYPE>
              <AMOUNT>{_ta:.2f}</AMOUNT>
            </BILLALLOCATIONS.LIST>""" if use_bill and _br else ""
            _cxml = f"""
            <COSTCENTREALLOCATION.LIST>
              <NAME>{_xml_escape(_cc)}</NAME>
              <AMOUNT>{_ta:.2f}</AMOUNT>
            </COSTCENTREALLOCATION.LIST>""" if _cc else ""
            ledger_xml += f"""
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{_xml_escape(_ln)}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>{_idp}</ISDEEMEDPOSITIVE>
            <AMOUNT>{_ta:.2f}</AMOUNT>{_bxml}{_cxml}
          </ALLLEDGERENTRIES.LIST>"""
            if _is_dr and not party_name:
                party_name = _ln
        persistedview_xml = f"\n          <PERSISTEDVIEW>{obj_view}</PERSISTEDVIEW>" if obj_view == "Invoice Voucher View" else ""
        party_xml = f"\n          <PARTYLEDGERNAME>{_xml_escape(party_name)}</PARTYLEDGERNAME>" if party_name and obj_view == "Invoice Voucher View" else ""
        return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>Vouchers</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{_xml_escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHER VCHTYPE="{tally_vch_type}" ACTION="Create" OBJVIEW="{obj_view}">
          <DATE>{tally_date}</DATE>
          <EFFECTIVEDATE>{tally_date}</EFFECTIVEDATE>
          <NARRATION>{_xml_escape(narration)}</NARRATION>
          <VOUCHERTYPENAME>{tally_vch_type}</VOUCHERTYPENAME>{persistedview_xml}{party_xml}
          <VOUCHERNUMBER></VOUCHERNUMBER>{ledger_xml}
        </VOUCHER>
      </TALLYMESSAGE>
    </REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>"""

    # Consolidate duplicate ledger entries (same ledger name, same ISDEEMEDPOSITIVE)
    from collections import defaultdict
    consolidated: dict[tuple, float] = defaultdict(float)
    entry_meta: dict[tuple, dict] = {}
    for entry in entries:
        ledger_name = entry.get("ledger_name", "")
        is_debit = entry.get("is_debit", True)
        amount = float(entry.get("amount", 0))
        tally_amount = amount if not is_debit else -amount
        key = (ledger_name, is_debit)
        consolidated[key] += tally_amount
        if key not in entry_meta:
            entry_meta[key] = entry
    ledger_xml = ""
    party_ledger_name = ""
    for (ledger_name, is_debit), tally_amount in consolidated.items():
        is_deemed_positive = "Yes" if is_debit else "No"
        entry = entry_meta[(ledger_name, is_debit)]
        bill_ref = entry.get("bill_ref", "")
        cost_centre = entry.get("cost_centre") or ""
        bill_xml = ""
        if use_bill and bill_ref:
            bill_xml = f"""
            <BILLALLOCATIONS.LIST>
              <NAME>{_xml_escape(bill_ref)}</NAME>
              <BILLTYPE>Against Ref</BILLTYPE>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>
            </BILLALLOCATIONS.LIST>"""
        cost_centre_xml = ""
        if cost_centre:
            cost_centre_xml = f"""
            <COSTCENTREALLOCATION.LIST>
              <NAME>{_xml_escape(cost_centre)}</NAME>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>
            </COSTCENTREALLOCATION.LIST>"""
        ledger_xml += f"""
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{_xml_escape(ledger_name)}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>{is_deemed_positive}</ISDEEMEDPOSITIVE>
            <AMOUNT>{tally_amount:.2f}</AMOUNT>{bill_xml}{cost_centre_xml}
          </ALLLEDGERENTRIES.LIST>"""
        if is_debit and not party_ledger_name:
            party_ledger_name = ledger_name

    # Item Invoice XML — includes inventory allocation lines
    inventory_xml = ""
    for item in stock_items:
        name = _xml_escape(item.get("name") or "Item")
        qty = float(item.get("quantity") or 0)
        per = _xml_escape(item.get("per") or item.get("unit") or "Nos")
        rate = float(item.get("unit_price") or 0)
        amount = float(item.get("amount") or (qty * rate))
        item_cc = item.get("cost_centre") or ""
        item_cc_xml = ""
        if item_cc:
            item_cc_xml = f"""
              <COSTCENTREALLOCATION.LIST>
                <NAME>{_xml_escape(item_cc)}</NAME>
                <AMOUNT>-{amount:.2f}</AMOUNT>
              </COSTCENTREALLOCATION.LIST>"""
        inventory_xml += f"""
          <ALLINVENTORYENTRIES.LIST>
            <STOCKITEMNAME>{name}</STOCKITEMNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <RATE>{rate:.2f}/{per}</RATE>
            <AMOUNT>-{amount:.2f}</AMOUNT>
            <ACTUALQTY>{qty:.2f} {per}</ACTUALQTY>
            <BILLEDQTY>{qty:.2f} {per}</BILLEDQTY>
            <BATCHALLOCATIONS.LIST>
              <GODOWNNAME>Main Location</GODOWNNAME>
              <BATCHNAME>Primary Batch</BATCHNAME>
              <AMOUNT>-{amount:.2f}</AMOUNT>
              <ACTUALQTY>{qty:.2f} {per}</ACTUALQTY>
              <BILLEDQTY>{qty:.2f} {per}</BILLEDQTY>
            </BATCHALLOCATIONS.LIST>{item_cc_xml}
          </ALLINVENTORYENTRIES.LIST>"""

    party_xml = f"\n          <PARTYLEDGERNAME>{_xml_escape(party_ledger_name)}</PARTYLEDGERNAME>" if party_ledger_name else ""
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>Vouchers</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{_xml_escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHER VCHTYPE="{tally_vch_type}" ACTION="Create" OBJVIEW="Invoice Voucher View">
          <DATE>{tally_date}</DATE>
          <EFFECTIVEDATE>{tally_date}</EFFECTIVEDATE>
          <NARRATION>{_xml_escape(narration)}</NARRATION>
          <VOUCHERTYPENAME>{tally_vch_type}</VOUCHERTYPENAME>
          <ISINVOICE>Yes</ISINVOICE>
          <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>{party_xml}
          <VOUCHERNUMBER></VOUCHERNUMBER>{ledger_xml}{inventory_xml}
        </VOUCHER>
      </TALLYMESSAGE>
    </REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>"""


def _extract_voucher_number(response_text: str) -> str:
    try:
        root = ET.fromstring(response_text)
        for tag in ("MASTERID", "VOUCHERNUMBER", "VCHNO"):
            el = root.find(f".//{tag}")
            if el is not None and el.text:
                return el.text.strip()
    except Exception:
        pass
    return ""


def _xml_escape(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
    )


def _guess_ledger_group(ledger_name: str, is_debit: bool, voucher_type: str) -> str:
    name_lower = ledger_name.lower()
    vtype = (voucher_type or "").lower()
    # Name-based patterns (highest priority)
    if any(k in name_lower for k in ("cash", "petty cash")):
        return "Cash-in-Hand"
    if any(k in name_lower for k in ("bank", "hdfc", "icici", "axis", "sbi", "emirates", "nbd", "fab", "adcb", "enbd")):
        return "Bank Accounts"
    if any(k in name_lower for k in ("vat", "gst", "tax", "duty", "tds", "withholding", "excise")):
        return "Duties & Taxes"
    if any(k in name_lower for k in ("salary", "wages", "payroll")):
        return "Indirect Expenses"
    if any(k in name_lower for k in ("sales", "revenue", "income", "turnover", "service income", "consulting")):
        return "Sales Accounts"
    if any(k in name_lower for k in ("purchase", "cost of goods", "cogs", "raw material")):
        return "Purchase Accounts"
    if any(k in name_lower for k in ("expense", "overhead", "rent", "utility", "telephone", "transport",
                                      "postage", "printing", "repair", "maintenance", "insurance",
                                      "commission", "advertisement", "freight", "discount allowed")):
        return "Indirect Expenses"
    if any(k in name_lower for k in ("discount received", "interest received", "other income")):
        return "Indirect Incomes"
    # Voucher-type-based fallback for party ledgers
    if vtype in ("sales", "credit note"):
        return "Sundry Debtors" if is_debit else "Sales Accounts"
    if vtype in ("purchase", "debit note"):
        return "Purchase Accounts" if is_debit else "Sundry Creditors"
    if vtype == "payment":
        return "Sundry Creditors" if is_debit else "Bank Accounts"
    if vtype == "receipt":
        return "Bank Accounts" if is_debit else "Sundry Debtors"
    # Generic fallback
    return "Sundry Debtors" if is_debit else "Sundry Creditors"


def _create_ledger_xml(company: str, ledger_name: str, under_group: str) -> str:
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>All Masters</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{_xml_escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <LEDGER NAME="{_xml_escape(ledger_name)}" ACTION="Create" RESERVED="No">
          <NAME>{_xml_escape(ledger_name)}</NAME>
          <PARENT>{_xml_escape(under_group)}</PARENT>
        </LEDGER>
      </TALLYMESSAGE>
    </REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>"""


def _create_stock_item_xml(company: str, item_name: str, uom: str = "Nos") -> str:
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>All Masters</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{_xml_escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{_xml_escape(item_name)}" ACTION="Create">
          <NAME>{_xml_escape(item_name)}</NAME>
          <PARENT>Primary</PARENT>
          <BASEUNITS>{_xml_escape(uom)}</BASEUNITS>
        </STOCKITEM>
      </TALLYMESSAGE>
    </REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>"""


async def _ensure_stock_items_via_tunnel(company, client_obj, stock_items) -> tuple[list, list]:
    """Auto-create missing stock items in Tally before posting an item invoice.
    Returns (created, failed) — if any items failed, caller should fall back to accounting voucher."""
    from app.core.tally_routing import route_tally_xml
    created, failed = [], []
    for item in stock_items:
        item_name = (item.get("name") or "").strip()
        if not item_name:
            continue
        uom = item.get("per") or item.get("unit") or "Nos"
        xml = _create_stock_item_xml(company, item_name, uom)
        try:
            response = await route_tally_xml(client_obj, xml)
            if "LINEERROR" in response or "IMPORTERROR" in response:
                # Could mean item already exists (Tally returns ALTERED) or group missing
                # Check if ALTERED > 0 (item exists, that's fine)
                try:
                    root = ET.fromstring(response)
                    altered_el = root.find(".//ALTERED")
                    if altered_el is not None and altered_el.text and int(altered_el.text) > 0:
                        created.append(item_name)  # already existed
                        continue
                except Exception:
                    pass
                failed.append(item_name)
                continue
            root = ET.fromstring(response)
            created_el = root.find(".//CREATED")
            if created_el is not None and created_el.text and int(created_el.text) > 0:
                created.append(item_name)
            else:
                failed.append(item_name)
        except Exception:
            failed.append(item_name)
    return created, failed


def _ensure_ledgers_exist_async_wrapper(company, client, entries, voucher_type):
    created = []
    for entry in entries:
        ledger_name = entry.get("ledger_name", "").strip()
        if not ledger_name:
            continue
        is_debit = entry.get("is_debit", True)
        under_group = _guess_ledger_group(ledger_name, is_debit, voucher_type)
        xml = _create_ledger_xml(company, ledger_name, under_group)
        try:
            response = _post_tally_xml(client.tally_host or "localhost", client.tally_port or 9000, xml)
            if "LINEERROR" in response or "IMPORTERROR" in response:
                raise RuntimeError(f"Could not create ledger '{ledger_name}': {response}")
            root = ET.fromstring(response)
            created_el = root.find(".//CREATED")
            if created_el is not None and created_el.text and int(created_el.text) > 0:
                created.append(ledger_name)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Error creating ledger '{ledger_name}': {str(e)}")
    return created

async def _ensure_ledgers_via_tunnel(company, client_obj, entries, voucher_type):
    """Async version of _ensure_ledgers_exist_async_wrapper that routes through WebSocket tunnel."""
    from app.core.tally_routing import route_tally_xml
    created = []
    for entry in entries:
        ledger_name = entry.get("ledger_name", "").strip()
        if not ledger_name:
            continue
        is_debit = entry.get("is_debit", True)
        under_group = _guess_ledger_group(ledger_name, is_debit, voucher_type)
        xml = _create_ledger_xml(company, ledger_name, under_group)
        try:
            response = await route_tally_xml(client_obj, xml)
            if "LINEERROR" in response or "IMPORTERROR" in response:
                continue  # ledger likely already exists; non-fatal
            root = ET.fromstring(response)
            created_el = root.find(".//CREATED")
            if created_el is not None and created_el.text and int(created_el.text) > 0:
                created.append(ledger_name)
        except Exception:
            pass  # best-effort; voucher post will surface any real issue
    return created

# Backward-compatible wrapper: accepts (company, host, port, entries, voucher_type)
class _TallyConfig:
    def __init__(self, host, port):
        self.tally_host = host
        self.tally_port = port

def _ensure_ledgers_exist(company, host, port, entries, voucher_type):
    client = _TallyConfig(host, port)
    return _ensure_ledgers_exist_async_wrapper(company, client, entries, voucher_type)


# ── Ledger push ───────────────────────────────────────────────────────────────

@router.post("/push-ledgers/{client_id}")
async def push_ledgers_to_tally(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Bulk-push all active tenant ledgers to Tally as masters."""
    from app.models.ledger import Ledger

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    company = client.tally_company or ""
    if not company:
        raise HTTPException(422, "No Tally company configured for this client. Set it in Tally Settings first.")

    ledger_result = await db.execute(
        select(Ledger).where(
            Ledger.tenant_id == current_user.tenant_id,
            Ledger.is_active == True,
        ).order_by(Ledger.name)
    )
    ledgers = ledger_result.scalars().all()

    if not ledgers:
        return {"pushed": 0, "created": 0, "already_exists": 0, "errors": [],
                "message": "No active ledgers found — add ledgers first."}

    created, already_exists, errors = [], [], []

    for ledger in ledgers:
        xml = _create_ledger_xml(company, ledger.tally_name, ledger.group or "Sundry Creditors")
        try:
            response = await route_tally_xml(client, xml)
            # LINEERROR / IMPORTERROR usually means ledger already exists — non-fatal
            if "LINEERROR" in response or "IMPORTERROR" in response:
                already_exists.append(ledger.tally_name)
                continue
            root = ET.fromstring(response)
            created_el = root.find(".//CREATED")
            if created_el is not None and created_el.text and int(created_el.text) > 0:
                created.append(ledger.tally_name)
            else:
                already_exists.append(ledger.tally_name)
        except Exception as e:
            errors.append({"ledger": ledger.tally_name, "error": str(e)})

    return {
        "pushed": len(ledgers),
        "created": len(created),
        "already_exists": len(already_exists),
        "errors": errors,
        "created_names": created,
        "message": (
            f"Pushed {len(ledgers)} ledgers — "
            f"{len(created)} created, {len(already_exists)} already existed"
            + (f", {len(errors)} errors" if errors else "")
        ),
    }

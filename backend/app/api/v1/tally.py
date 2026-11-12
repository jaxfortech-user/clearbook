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
from app.models.client import Client

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
    return {
        "client_id": client.id,
        "tally_host": client.tally_host or "localhost",
        "tally_port": client.tally_port or 9000,
        "tally_company": client.tally_company or "",
        "tally_edu_mode": client.tally_edu_mode or False,
        "tally_connector_status": client.tally_connector_status or "not_installed",
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


def _build_voucher_xml(company, voucher_type, date, narration, entries) -> str:
    tally_date = date.strftime("%Y%m%d")
    vch_type_map = {
        "payment": "Payment", "receipt": "Receipt", "journal": "Journal",
        "contra": "Contra", "sales": "Sales", "purchase": "Purchase",
        "credit note": "Credit Note", "debit note": "Debit Note",
    }
    tally_vch_type = vch_type_map.get((voucher_type or "journal").lower(), "Journal")
    ledger_xml = ""
    for entry in entries:
        ledger_name = entry.get("ledger_name", "")
        is_debit = entry.get("is_debit", True)
        amount = float(entry.get("amount", 0))
        tally_amount = amount if not is_debit else -amount
        is_deemed_positive = "Yes" if is_debit else "No"
        ledger_xml += f"""
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{_xml_escape(ledger_name)}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>{is_deemed_positive}</ISDEEMEDPOSITIVE>
            <AMOUNT>{tally_amount:.2f}</AMOUNT>
          </ALLLEDGERENTRIES.LIST>"""
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>Vouchers</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{_xml_escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHER VCHTYPE="{tally_vch_type}" ACTION="Create" OBJVIEW="Accounting Voucher View">
          <DATE>{tally_date}</DATE>
          <NARRATION>{_xml_escape(narration)}</NARRATION>
          <VOUCHERTYPENAME>{tally_vch_type}</VOUCHERTYPENAME>
          <VOUCHERNUMBER></VOUCHERNUMBER>{ledger_xml}
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
    if any(k in name_lower for k in ("cash", "petty cash")):
        return "Cash-in-Hand"
    if any(k in name_lower for k in ("bank", "hdfc", "icici", "axis", "sbi", "emirates", "nbd", "fab", "adcb", "enbd")):
        return "Bank Accounts"
    if any(k in name_lower for k in ("vat", "gst", "tax", "duty", "tds", "withholding")):
        return "Duties & Taxes"
    if any(k in name_lower for k in ("salary", "wages", "payroll", "staff")):
        return "Indirect Expenses"
    if vtype == "receipt":
        return "Sundry Debtors" if is_debit else "Sundry Creditors"
    return "Sundry Creditors" if is_debit else "Sundry Debtors"


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
        <LEDGER NAME="{_xml_escape(ledger_name)}" ACTION="Create">
          <NAME>{_xml_escape(ledger_name)}</NAME>
          <PARENT>{_xml_escape(under_group)}</PARENT>
        </LEDGER>
      </TALLYMESSAGE>
    </REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>"""


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
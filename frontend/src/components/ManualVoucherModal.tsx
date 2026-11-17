"use client"
import { useState } from "react"
import { createManualVoucher } from "@/lib/api"

interface LineItem {
  ledger: string
  type: "debit" | "credit"
  amount: number
  is_party: boolean
}

const DEFAULT_TEMPLATES: Record<string, { voucher_type: string; narration: string; lines: LineItem[] }> = {
  "Salary Payment": {
    voucher_type: "Payment",
    narration: "Salary payment for the month",
    lines: [
      { ledger: "Salaries & Wages", type: "debit", amount: 0, is_party: false },
      { ledger: "Bank Account", type: "credit", amount: 0, is_party: false },
    ],
  },
  "Depreciation Journal": {
    voucher_type: "Journal",
    narration: "Monthly depreciation entry",
    lines: [
      { ledger: "Depreciation", type: "debit", amount: 0, is_party: false },
      { ledger: "Accumulated Depreciation", type: "credit", amount: 0, is_party: false },
    ],
  },
  "Rent Accrual": {
    voucher_type: "Journal",
    narration: "Rent accrual entry",
    lines: [
      { ledger: "Rent Expense", type: "debit", amount: 0, is_party: false },
      { ledger: "Rent Payable", type: "credit", amount: 0, is_party: false },
    ],
  },
  "Cash Deposit": {
    voucher_type: "Contra",
    narration: "Cash deposited into bank",
    lines: [
      { ledger: "Bank Account", type: "debit", amount: 0, is_party: false },
      { ledger: "Cash", type: "credit", amount: 0, is_party: false },
    ],
  },
  "Petty Cash Replenishment": {
    voucher_type: "Payment",
    narration: "Petty cash replenishment",
    lines: [
      { ledger: "Petty Cash", type: "debit", amount: 0, is_party: false },
      { ledger: "Bank Account", type: "credit", amount: 0, is_party: false },
    ],
  },
}

interface Props {
  clientId: string
  onClose: () => void
  onSaved: () => void
}

export default function ManualVoucherModal({ clientId, onClose, onSaved }: Props) {
  const [voucherType, setVoucherType] = useState("Payment")
  const [voucherNumber, setVoucherNumber] = useState("")
  const [voucherDate, setVoucherDate] = useState(new Date().toISOString().split("T")[0])
  const [narration, setNarration] = useState("")
  const [lines, setLines] = useState<LineItem[]>([
    { ledger: "", type: "debit", amount: 0, is_party: false },
    { ledger: "", type: "credit", amount: 0, is_party: false },
  ])
  const [billRef, setBillRef] = useState("")
  const [billParty, setBillParty] = useState("")
  const [saveAsTemplate, setSaveAsTemplate] = useState(false)
  const [templateName, setTemplateName] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const totalDr = lines.filter(l => l.type === "debit").reduce((s, l) => s + (Number(l.amount) || 0), 0)
  const totalCr = lines.filter(l => l.type === "credit").reduce((s, l) => s + (Number(l.amount) || 0), 0)
  const balanced = Math.abs(totalDr - totalCr) < 0.01

  function applyTemplate(name: string) {
    const t = DEFAULT_TEMPLATES[name]
    if (!t) return
    setVoucherType(t.voucher_type)
    setNarration(t.narration)
    setLines(t.lines.map(l => ({ ...l })))
    setTemplateName(name)
  }

  function updateLine(idx: number, field: keyof LineItem, value: string | number | boolean) {
    setLines(prev => prev.map((l, i) => i === idx ? { ...l, [field]: value } : l))
  }

  function addLine() {
    setLines(prev => [...prev, { ledger: "", type: "debit", amount: 0, is_party: false }])
  }

  function removeLine(idx: number) {
    if (lines.length <= 2) return
    setLines(prev => prev.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    if (!balanced) { setError("Voucher does not balance"); return }
    if (!voucherNumber) { setError("Voucher number is required"); return }
    setSaving(true)
    setError("")
    try {
      await createManualVoucher(clientId, {
        voucher_type: voucherType,
        voucher_number: voucherNumber,
        voucher_date: voucherDate,
        narration,
        line_items: lines.map(l => ({ ledger: l.ledger, type: l.type, amount: Number(l.amount), is_party: l.is_party })),
        bill_ref: billRef,
        bill_party: billParty,
        template_name: saveAsTemplate ? templateName : "",
      })
      onSaved()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save voucher")
    } finally {
      setSaving(false)
    }
  }

  const showBillByBill = ["Payment", "Receipt"].includes(voucherType)

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">New Manual Voucher</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <div className="p-6 space-y-4">
          {/* Quick templates */}
          <div>
            <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">Quick Templates</p>
            <div className="flex flex-wrap gap-2">
              {Object.keys(DEFAULT_TEMPLATES).map(name => (
                <button key={name} onClick={() => applyTemplate(name)}
                  className="px-3 py-1 text-xs rounded-full border border-gray-300 hover:bg-blue-50 hover:border-blue-400 transition-colors">
                  {name}
                </button>
              ))}
            </div>
          </div>

          {/* Header fields */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Type</label>
              <select value={voucherType} onChange={e => setVoucherType(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm">
                {["Payment", "Receipt", "Journal", "Contra"].map(t => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Voucher No.</label>
              <input value={voucherNumber} onChange={e => setVoucherNumber(e.target.value)}
                placeholder="PV-001" className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Date</label>
              <input type="date" value={voucherDate} onChange={e => setVoucherDate(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Narration</label>
            <input value={narration} onChange={e => setNarration(e.target.value)}
              placeholder="Description of transaction" className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>

          {/* Line items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Ledger Entries</p>
              <div className={`text-xs font-medium px-2 py-0.5 rounded ${balanced ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                Dr {totalDr.toFixed(2)} / Cr {totalCr.toFixed(2)}
              </div>
            </div>
            <div className="space-y-2">
              {lines.map((line, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <input value={line.ledger} onChange={e => updateLine(idx, "ledger", e.target.value)}
                    placeholder="Ledger name" className="flex-1 border rounded-lg px-3 py-2 text-sm" />
                  <select value={line.type} onChange={e => updateLine(idx, "type", e.target.value)}
                    className="w-24 border rounded-lg px-2 py-2 text-sm">
                    <option value="debit">Dr</option>
                    <option value="credit">Cr</option>
                  </select>
                  <input type="number" value={line.amount || ""} onChange={e => updateLine(idx, "amount", e.target.value)}
                    placeholder="0.00" className="w-28 border rounded-lg px-3 py-2 text-sm text-right" />
                  {showBillByBill && (
                    <label className="flex items-center gap-1 text-xs text-gray-500 whitespace-nowrap">
                      <input type="checkbox" checked={line.is_party}
                        onChange={e => updateLine(idx, "is_party", e.target.checked)} />
                      Party
                    </label>
                  )}
                  <button onClick={() => removeLine(idx)}
                    className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
                </div>
              ))}
            </div>
            <button onClick={addLine} className="mt-2 text-xs text-blue-600 hover:underline">+ Add line</button>
          </div>

          {/* Bill-by-bill */}
          {showBillByBill && (
            <div className="bg-blue-50 rounded-lg p-3 space-y-2">
              <p className="text-xs font-medium text-blue-700">Bill-by-Bill Settlement (optional)</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Invoice Ref</label>
                  <input value={billRef} onChange={e => setBillRef(e.target.value)}
                    placeholder="INV-001" className="w-full border rounded-lg px-3 py-2 text-sm bg-white" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Party Name</label>
                  <input value={billParty} onChange={e => setBillParty(e.target.value)}
                    placeholder="Supplier / Customer" className="w-full border rounded-lg px-3 py-2 text-sm bg-white" />
                </div>
              </div>
            </div>
          )}

          {/* Recurring template */}
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={saveAsTemplate} onChange={e => setSaveAsTemplate(e.target.checked)} />
              Save as recurring template
            </label>
            {saveAsTemplate && (
              <input value={templateName} onChange={e => setTemplateName(e.target.value)}
                placeholder="Template name" className="flex-1 border rounded-lg px-3 py-2 text-sm" />
            )}
          </div>

          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
        </div>

        <div className="p-6 border-t flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancel</button>
          <button onClick={handleSave} disabled={saving || !balanced}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Saving..." : "Save Voucher"}
          </button>
        </div>
      </div>
    </div>
  )
}

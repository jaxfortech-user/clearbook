"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, Pencil, Check, X } from "lucide-react";
import { getLedgers, createLedger, updateLedger, type Ledger } from "@/lib/api";

const GROUPS = [
  "Cash-in-Hand", "Bank Accounts", "Sundry Debtors", "Sundry Creditors",
  "Sales Accounts", "Purchase Accounts", "Direct Expenses", "Indirect Expenses",
  "Direct Incomes", "Indirect Incomes", "Fixed Assets", "Current Assets",
  "Current Liabilities", "Capital Account", "Duties & Taxes", "Loans (Liability)",
];

export default function LedgerMasterPage() {
  const [ledgers, setLedgers] = useState<Ledger[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", tally_name: "", group: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try { setLedgers(await getLedgers()); } catch { }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function handleSave() {
    if (!form.name.trim() || !form.tally_name.trim()) { setError("Name and Tally Name are required"); return; }
    setSaving(true); setError(null);
    try {
      if (editId) {
        await updateLedger(editId, form);
      } else {
        await createLedger(form);
      }
      setShowNew(false); setEditId(null);
      setForm({ name: "", tally_name: "", group: "", description: "" });
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  function startEdit(l: Ledger) {
    setEditId(l.id);
    setForm({ name: l.name, tally_name: l.tally_name, group: l.group || "", description: l.description || "" });
    setShowNew(false);
  }

  async function handleDeactivate(id: string) {
    try { await updateLedger(id, { is_active: false }); await load(); } catch { }
  }

  const inp: React.CSSProperties = { height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", width: "100%", outline: "none", fontFamily: "var(--font-family-sans)", boxSizing: "border-box" };

  return (
    <div style={{ maxWidth: "900px", padding: "32px 24px", fontFamily: "var(--font-family-sans)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "18px", fontWeight: 700, color: "#0a0a0a", margin: 0 }}>Ledger Master</h1>
          <p style={{ fontSize: "13px", color: "#6b7280", margin: "4px 0 0" }}>
            Define your ledger accounts. The Tally Name must exactly match the ledger name in Tally.
          </p>
        </div>
        <button onClick={() => { setShowNew(true); setEditId(null); setForm({ name: "", tally_name: "", group: "", description: "" }); }}
          style={{ display: "flex", alignItems: "center", gap: "7px", height: "34px", padding: "0 14px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "13px", fontWeight: 600, cursor: "pointer" }}>
          <Plus size={13} /> Add Ledger
        </button>
      </div>

      {error && <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", padding: "10px 14px", fontSize: "13px", color: "#991b1b", marginBottom: "14px" }}>{error}</div>}

      {/* Add / Edit form */}
      {(showNew || editId) && (
        <div style={{ background: "#f8f9ff", border: "1px solid #c7d0fb", borderRadius: "10px", padding: "18px", marginBottom: "20px" }}>
          <div style={{ fontSize: "13px", fontWeight: 600, color: "#3730a3", marginBottom: "14px" }}>{editId ? "Edit Ledger" : "New Ledger"}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
            <div>
              <label style={{ fontSize: "11px", fontWeight: 600, color: "#6b7280", display: "block", marginBottom: "4px" }}>Platform Name *</label>
              <input style={inp} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Sales Revenue" />
            </div>
            <div>
              <label style={{ fontSize: "11px", fontWeight: 600, color: "#6b7280", display: "block", marginBottom: "4px" }}>Tally Ledger Name * <span style={{ color: "#dc2626" }}>(exact match)</span></label>
              <input style={inp} value={form.tally_name} onChange={e => setForm(f => ({ ...f, tally_name: e.target.value }))} placeholder="e.g. Sales Accounts" />
            </div>
            <div>
              <label style={{ fontSize: "11px", fontWeight: 600, color: "#6b7280", display: "block", marginBottom: "4px" }}>Tally Group</label>
              <select style={inp} value={form.group} onChange={e => setForm(f => ({ ...f, group: e.target.value }))}>
                <option value="">Select group…</option>
                {GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: "11px", fontWeight: 600, color: "#6b7280", display: "block", marginBottom: "4px" }}>Description</label>
              <input style={inp} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Optional note" />
            </div>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={handleSave} disabled={saving} style={{ display: "flex", alignItems: "center", gap: "6px", height: "32px", padding: "0 14px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "13px", fontWeight: 600, cursor: "pointer" }}>
              <Check size={13} /> {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => { setShowNew(false); setEditId(null); setError(null); }} style={{ display: "flex", alignItems: "center", gap: "6px", height: "32px", padding: "0 12px", background: "#f5f5f5", border: "none", borderRadius: "7px", fontSize: "13px", cursor: "pointer" }}>
              <X size={13} /> Cancel
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div style={{ background: "#fff", border: "1px solid #ebebeb", borderRadius: "10px", overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr 1fr 80px", padding: "10px 16px", borderBottom: "1px solid #f0f0f0", fontSize: "11px", fontWeight: 600, color: "#a0a0a0", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          <span>Platform Name</span><span>Tally Name</span><span>Group</span><span>Description</span><span></span>
        </div>
        {loading && <div style={{ padding: "24px", textAlign: "center", color: "#a0a0a0", fontSize: "13px" }}>Loading…</div>}
        {!loading && ledgers.length === 0 && (
          <div style={{ padding: "40px", textAlign: "center", color: "#a0a0a0", fontSize: "13px" }}>
            No ledgers yet. Add your first ledger to use in voucher entries.
          </div>
        )}
        {ledgers.map((l, i) => (
          <div key={l.id} style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr 1fr 80px", padding: "12px 16px", borderBottom: i < ledgers.length - 1 ? "1px solid #f5f5f5" : "none", alignItems: "center" }}>
            <div style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>{l.name}</div>
            <div style={{ fontSize: "13px", color: "#374151", fontFamily: "monospace" }}>{l.tally_name}</div>
            <div style={{ fontSize: "12px", color: "#6b7280" }}>{l.group || "—"}</div>
            <div style={{ fontSize: "12px", color: "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l.description || "—"}</div>
            <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
              <button onClick={() => startEdit(l)} title="Edit" style={{ background: "none", border: "none", cursor: "pointer", padding: "4px", color: "#6b7280" }}>
                <Pencil size={13} />
              </button>
              <button onClick={() => handleDeactivate(l.id)} title="Remove" style={{ background: "none", border: "none", cursor: "pointer", padding: "4px", color: "#dc2626" }}>
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

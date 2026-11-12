"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { AlertCircle, CheckCircle, Loader2, X } from "lucide-react";
import { getVouchers, getClients, createVoucher, approveVoucher, type Voucher, type Client } from "@/lib/api";

const statusStyle: Record<string, { bg: string; color: string }> = {
  approved:         { bg: "#d1fae5", color: "#059669" },
  pending:          { bg: "#fef3c7", color: "#b45309" },
  pending_approval: { bg: "#fef3c7", color: "#b45309" },
  rejected:         { bg: "#fee2e2", color: "#dc2626" },
  draft:            { bg: "#f5f5f5", color: "#737373" },
  cancelled:        { bg: "#fee2e2", color: "#dc2626" },
};

const fallbackStyle = { bg: "#f5f5f5", color: "#737373" };

const cols = ["ID", "Client", "Description", "Amount", "Type", "Status", ""];

const VOUCHER_TYPES = ["Expense", "Income", "Journal", "Payment", "Receipt", "Contra"];

const inputStyle = {
  height: "34px", padding: "0 10px", borderRadius: "7px",
  border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a",
  background: "#ffffff", outline: "none", width: "100%",
  fontFamily: "var(--font-family-sans)", boxSizing: "border-box" as const,
};

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#525252", letterSpacing: "0.01em" }}>
        {label}{required && <span style={{ color: "#dc2626", marginLeft: "2px" }}>*</span>}
      </label>
      {children}
    </div>
  );
}

export default function VouchersPage() {
  const router = useRouter();
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [form, setForm] = useState({
    clientId: "", description: "", amount: "",
    type: "Expense", date: "", reference: "", narration: "",
  });

  const fetchData = () => {
    setLoading(true);
    setLoadError("");
    Promise.all([
      getVouchers(),
      getClients().catch(() => [] as Client[]),
    ])
      .then(([vouchersData, clientsData]) => {
        setVouchers(vouchersData);
        setClients(Array.isArray(clientsData) ? clientsData : (clientsData as any)?.items ?? []);
      })
      .catch(e => setLoadError(e.message || "Failed to load vouchers"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  const pendingCount = vouchers.filter(v => v.status === "pending" || v.status === "pending_approval").length;

  function set(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  function openModal() {
    const today = new Date().toISOString().split("T")[0];
    setForm({ clientId: "", description: "", amount: "", type: "Expense", date: today, reference: "", narration: "" });
    setSaveError("");
    setShowModal(true);
  }

  function closeModal() {
    if (saving) return;
    setShowModal(false);
  }

  async function handleSave() {
    if (!form.clientId) { setSaveError("Please select a client."); return; }
    if (!form.description.trim()) { setSaveError("Description is required."); return; }
    if (!form.amount || isNaN(Number(form.amount)) || Number(form.amount) <= 0) { setSaveError("Enter a valid amount."); return; }
    if (!form.date) { setSaveError("Date is required."); return; }
    setSaveError("");
    setSaving(true);
    try {
      const created = await createVoucher({
        client: form.clientId,
        description: form.description.trim(),
        amount: Number(form.amount),
        voucher_type: form.type,
        voucher_date: form.date,
        narration: form.narration.trim() || undefined,
      });
      setVouchers(prev => [created, ...prev]);
      setShowModal(false);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Failed to create voucher.");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove(id: string) {
    try {
      const updated = await approveVoucher(id);
      setVouchers(prev => prev.map(v => v.id === id ? updated : v));
    } catch {
      setVouchers(prev => prev.map(v => v.id === id ? { ...v, status: "approved" as const } : v));
    }
  }

  // Resolve a voucher's client UUID → display name
  function resolveClientName(v: Voucher): string {
    const vAny = v as any;
    // If backend already returns a name field, use it
    if (vAny.client_name) return vAny.client_name;
    // Otherwise look up in the clients list by UUID
    const clientId = vAny.client_id || v.client;
    if (clientId) {
      const match = clients.find(c => c.id === clientId);
      if (match) return match.name;
      // Last resort: show a truncated UUID so it's clear something is there
      return clientId.length > 8 ? `${clientId.substring(0, 8)}…` : clientId;
    }
    return "—";
  }

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Vouchers"
        subtitle={loading ? "Loading…" : `${vouchers.length} voucher${vouchers.length !== 1 ? "s" : ""}`}
        actions={
          <button
            onClick={openModal}
            style={{ height: "32px", padding: "0 14px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "12.5px", fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
            onMouseEnter={e => (e.currentTarget.style.background = "#4254d4")}
            onMouseLeave={e => (e.currentTarget.style.background = "#5266eb")}
          >+ New Voucher</button>
        }
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>

        {/* Loading */}
        {loading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: "10px" }}>
            <Loader2 size={18} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Loading vouchers…</span>
          </div>
        )}

        {/* Error */}
        {!loading && loadError && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{loadError}</span>
            <button onClick={fetchData} style={{ marginLeft: "auto", fontSize: "12px", color: "#5266eb", background: "none", border: "none", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}>Retry</button>
          </div>
        )}

        {!loading && !loadError && (
          <>
            {/* Pending alert */}
            {pendingCount > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef3c7", border: "1px solid #b45309", borderRadius: "8px" }}>
                <AlertCircle size={14} color="#b45309" />
                <p style={{ fontSize: "13px", color: "#b45309", margin: 0 }}>
                  <strong>{pendingCount} voucher{pendingCount !== 1 ? "s" : ""}</strong> awaiting your approval
                </p>
              </div>
            )}

            {/* Table */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #ebebeb" }}>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>All Vouchers</span>
                <span style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "11px", color: "#a3a3a3" }}>
                  <CheckCircle size={12} color="#059669" />
                  {vouchers.filter(v => v.status === "approved").length} approved
                </span>
              </div>

              {vouchers.length === 0 ? (
                <div style={{ padding: "60px 20px", textAlign: "center" }}>
                  <p style={{ fontSize: "13px", fontWeight: 500, color: "#a3a3a3" }}>No vouchers yet. Create your first voucher to get started.</p>
                </div>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                      {cols.map(h => <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {vouchers.map((v, i) => {
                      const style = statusStyle[v.status] ?? fallbackStyle;
                      const vAny = v as any;
                      const displayClient = resolveClientName(v);
                      return (
                        <tr key={v.id} style={{ borderBottom: i < vouchers.length - 1 ? "1px solid #ebebeb" : "none", transition: "background 0.1s" }}
                          onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                        >
                          <td style={{ padding: "12px 20px", fontSize: "11px", fontFamily: "monospace", color: "#a3a3a3", whiteSpace: "nowrap" }}>{v.id}</td>
                          <td style={{ padding: "12px 20px", fontSize: "13px", fontWeight: 500, color: "#0a0a0a", whiteSpace: "nowrap" }}>
                            {displayClient}
                          </td>
                          <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {v.description || "—"}
                          </td>
                          <td style={{ padding: "12px 20px", fontSize: "13px", fontWeight: 600, color: "#0a0a0a", whiteSpace: "nowrap" }}>
                            {Number(v.amount).toLocaleString("en-AE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                            <span style={{ display: "inline-flex", fontSize: "11px", fontWeight: 500, padding: "2px 8px", borderRadius: "9999px", background: vAny.type === "Income" ? "#eef0fd" : "#f5f5f5", color: vAny.type === "Income" ? "#5266eb" : "#525252" }}>
                              {vAny.type || "—"}
                            </span>
                          </td>
                          <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontSize: "11px", fontWeight: 500, padding: "2px 8px", borderRadius: "9999px", background: style.bg, color: style.color }}>
                              <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: style.color, flexShrink: 0 }} />
                              {v.status.replace(/_/g, " ")}
                            </span>
                          </td>
                          <td style={{ padding: "12px 24px 12px 20px", whiteSpace: "nowrap", textAlign: "right" }}>
                            {(v.status === "pending" || v.status === "pending_approval") ? (
                              <button onClick={() => handleApprove(v.id)} style={{ height: "28px", padding: "0 12px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "6px", fontSize: "12px", fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
                                onMouseEnter={e => (e.currentTarget.style.background = "#4254d4")}
                                onMouseLeave={e => (e.currentTarget.style.background = "#5266eb")}
                              >Approve</button>
                            ) : (
                              <button
                                onClick={() => router.push(`/vouchers/${v.id}`)}
                                style={{ height: "28px", padding: "0 12px", background: "none", border: "1px solid #ebebeb", borderRadius: "6px", fontSize: "12px", color: "#525252", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
                                onMouseEnter={e => { e.currentTarget.style.background = "#f5f5f5"; e.currentTarget.style.borderColor = "#d4d4d4"; }}
                                onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.borderColor = "#ebebeb"; }}
                              >View</button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>

      {/* ── NEW VOUCHER MODAL ── */}
      {showModal && (
        <div
          onClick={closeModal}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", backdropFilter: "blur(4px)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: "#ffffff", borderRadius: "14px", boxShadow: "0 20px 60px rgba(0,0,0,0.15)", width: "100%", maxWidth: "520px", maxHeight: "90vh", overflow: "auto", display: "flex", flexDirection: "column" }}
          >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 20px", borderBottom: "1px solid #ebebeb", flexShrink: 0 }}>
              <div>
                <h2 style={{ fontSize: "15px", fontWeight: 650, color: "#0a0a0a", letterSpacing: "-0.2px" }}>New Voucher</h2>
                <p style={{ fontSize: "12px", color: "#a3a3a3", marginTop: "2px" }}>Enter the voucher details below</p>
              </div>
              <button onClick={closeModal} style={{ width: "28px", height: "28px", display: "flex", alignItems: "center", justifyContent: "center", background: "#f5f5f5", border: "none", borderRadius: "7px", cursor: "pointer" }}
                onMouseEnter={e => (e.currentTarget.style.background = "#ebebeb")}
                onMouseLeave={e => (e.currentTarget.style.background = "#f5f5f5")}
              >
                <X size={14} color="#525252" />
              </button>
            </div>

            {/* Form */}
            <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px", flex: 1 }}>

              <Field label="Client" required>
                <select value={form.clientId} onChange={e => set("clientId", e.target.value)}
                  style={{ ...inputStyle, cursor: "pointer", color: form.clientId ? "#0a0a0a" : "#a3a3a3" }}
                  onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                >
                  <option value="">Select client…</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </Field>

              <Field label="Description" required>
                <input value={form.description} onChange={e => set("description", e.target.value)} placeholder="Office rent — Dec 2024"
                  style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
              </Field>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <Field label="Amount (AED)" required>
                  <input type="number" min="0" step="0.01" value={form.amount} onChange={e => set("amount", e.target.value)} placeholder="0.00"
                    style={{ ...inputStyle, fontFamily: "monospace" }} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
                <Field label="Type" required>
                  <select value={form.type} onChange={e => set("type", e.target.value)}
                    style={{ ...inputStyle, cursor: "pointer" }}
                    onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                  >
                    {VOUCHER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </Field>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <Field label="Date" required>
                  <input type="date" value={form.date} onChange={e => set("date", e.target.value)}
                    style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
                <Field label="Reference No.">
                  <input value={form.reference} onChange={e => set("reference", e.target.value)} placeholder="INV-2024-001"
                    style={{ ...inputStyle, fontFamily: "monospace" }} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
              </div>

              <Field label="Narration">
                <input value={form.narration} onChange={e => set("narration", e.target.value)} placeholder="Additional notes…"
                  style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
              </Field>

              {saveError && (
                <p style={{ fontSize: "12.5px", color: "#dc2626", background: "#fef2f2", border: "1px solid #fca5a5", padding: "8px 12px", borderRadius: "7px" }}>
                  {saveError}
                </p>
              )}
            </div>

            {/* Footer */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px", padding: "14px 20px", borderTop: "1px solid #ebebeb", flexShrink: 0 }}>
              <button onClick={closeModal} disabled={saving}
                style={{ height: "32px", padding: "0 14px", background: "none", border: "1px solid #e0e0e0", borderRadius: "7px", fontSize: "12.5px", color: "#525252", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
                onMouseEnter={e => (e.currentTarget.style.background = "#f5f5f5")}
                onMouseLeave={e => (e.currentTarget.style.background = "none")}
              >Cancel</button>
              <button onClick={handleSave} disabled={saving}
                style={{ height: "32px", padding: "0 16px", background: saving ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "12.5px", fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
                onMouseEnter={e => { if (!saving) e.currentTarget.style.background = "#4254d4"; }}
                onMouseLeave={e => { if (!saving) e.currentTarget.style.background = "#5266eb"; }}
              >
                {saving && <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />}
                {saving ? "Saving…" : "Create Voucher"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
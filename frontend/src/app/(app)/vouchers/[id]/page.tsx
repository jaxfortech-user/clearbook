"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { AlertCircle, ArrowLeft, CheckCircle, Loader2, Send, Plus, Trash2, Save } from "lucide-react";
import { approveVoucher, getLedgers, type Ledger } from "@/lib/api";
const API = "https://clearbook-app.duckdns.org";

function authH(): Record<string, string> {
  const t = typeof window !== "undefined" ? localStorage.getItem("clearbook_token") : null;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

const statusStyle: Record<string, { bg: string; color: string }> = {
  approved:         { bg: "#d1fae5", color: "#059669" },
  pending:          { bg: "#fef3c7", color: "#b45309" },
  pending_approval: { bg: "#fef3c7", color: "#b45309" },
  rejected:         { bg: "#fee2e2", color: "#dc2626" },
  draft:            { bg: "#f5f5f5", color: "#737373" },
  cancelled:        { bg: "#fee2e2", color: "#dc2626" },
};
const fallbackStyle = { bg: "#f5f5f5", color: "#737373" };

function FieldRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
      <span style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
      <span style={{ fontSize: "13.5px", color: "#0a0a0a" }}>{value ?? "—"}</span>
    </div>
  );
}

interface LedgerEntry {
  ledger_name: string;
  is_debit: boolean;
  amount: number;
  notes?: string;
}

function emptyEntry(): LedgerEntry {
  return { ledger_name: "", is_debit: true, amount: 0 };
}

function VoucherDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;

  const [voucher, setVoucher] = useState<any>(null);
  const [clients, setClients] = useState<any[]>([]);
  const [ledgers, setLedgers] = useState<Ledger[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [approving, setApproving] = useState(false);
  const [approveSuccess, setApproveSuccess] = useState(false);
  const [approveError, setApproveError] = useState("");

  // Tally posting state
  const [posting, setPosting] = useState(false);
  const [postSuccess, setPostSuccess] = useState(false);
  const [postError, setPostError] = useState("");

  // Ledger entries editor state
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [savingEntries, setSavingEntries] = useState(false);
  const [saveEntriesSuccess, setSaveEntriesSuccess] = useState(false);
  const [saveEntriesError, setSaveEntriesError] = useState("");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/v1/vouchers/${id}`, { headers: authH() }).then(r => {
        if (!r.ok) throw new Error(`Error ${r.status}`);
        return r.json();
      }),
      fetch(`${API}/api/v1/clients/`, { headers: authH() }).then(r => r.json()).catch(() => []),
      getLedgers().catch(() => []),
    ])
      .then(([voucherData, clientsData, ledgersData]) => {
        setVoucher(voucherData);
        setClients(Array.isArray(clientsData) ? clientsData : clientsData?.items ?? []);
        setLedgers(Array.isArray(ledgersData) ? ledgersData : []);

        // Populate entries editor from approved_entries or ledger_entries
        const raw: any[] = voucherData?.approved_entries || voucherData?.ai_suggested_data?.entries || [];
        if (raw.length > 0) {
          setEntries(raw.map((e: any) => ({
            ledger_name: e.ledger_name || "",
            is_debit: e.is_debit !== false,
            amount: parseFloat(e.amount) || 0,
            notes: e.notes || "",
          })));
        } else {
          // Start with two blank rows for convenience
          setEntries([emptyEntry(), { ...emptyEntry(), is_debit: false }]);
        }

        setLoading(false);
      })
      .catch(e => { setError(e.message || "Failed to load voucher"); setLoading(false); });
  }, [id]);

  async function handleApprove() {
    if (!voucher) return;
    setApproving(true);
    setApproveError("");
    try {
      const updated = await approveVoucher(voucher.id);
      setVoucher((prev: any) => ({ ...prev, ...(updated?.id ? updated : {}), status: "approved" }));
      setApproveSuccess(true);
    } catch (e: any) {
      setApproveError(e?.message || "Failed to approve voucher");
    } finally {
      setApproving(false);
    }
  }

  async function handleSubmit() {
    if (!voucher) return;
    setApproving(true);
    setApproveError("");
    try {
      const res = await fetch(`${API}/api/v1/vouchers/${voucher.id}/submit`, { method: "POST", headers: authH() });
      if (res.ok) {
        const updated = await res.json();
        setVoucher((prev: any) => ({ ...prev, ...(updated?.id ? updated : {}), status: "pending_approval" }));
      } else {
        setVoucher((prev: any) => ({ ...prev, status: "pending_approval" }));
      }
    } catch {
      setVoucher((prev: any) => ({ ...prev, status: "pending_approval" }));
    } finally {
      setApproving(false);
    }
  }

  async function handleSaveEntries() {
    if (!voucher) return;
    setSaveEntriesError("");
    setSaveEntriesSuccess(false);

    // Validate — at least one row, all rows filled
    const valid = entries.filter(e => e.ledger_name.trim() && e.amount > 0);
    if (valid.length === 0) {
      setSaveEntriesError("Add at least one entry with a ledger name and amount.");
      return;
    }

    // Warn if debits ≠ credits (soft warning, don't block)
    const totalDebit = valid.filter(e => e.is_debit).reduce((s, e) => s + e.amount, 0);
    const totalCredit = valid.filter(e => !e.is_debit).reduce((s, e) => s + e.amount, 0);
    if (Math.abs(totalDebit - totalCredit) > 0.01) {
      setSaveEntriesError(`Debits (${totalDebit.toFixed(2)}) ≠ Credits (${totalCredit.toFixed(2)}). Save anyway? Fix the amounts and try again, or Tally will reject the voucher.`);
      return;
    }

    setSavingEntries(true);
    try {
      const res = await fetch(`${API}/api/v1/vouchers/${voucher.id}/update-entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authH() },
        body: JSON.stringify({ entries: valid }),
      });
      if (res.ok) {
        const updated = await res.json();
        setVoucher(updated);
        setSaveEntriesSuccess(true);
        setTimeout(() => setSaveEntriesSuccess(false), 3000);
      } else {
        const err = await res.json().catch(() => ({}));
        setSaveEntriesError(typeof err?.detail === "string" ? err.detail : "Failed to save entries.");
      }
    } catch (e: any) {
      setSaveEntriesError(e?.message || "Network error saving entries.");
    } finally {
      setSavingEntries(false);
    }
  }

  async function handlePostToTally() {
    if (!voucher) return;

    let tallyConfig = { host: "localhost", port: 9000, company: "" };
    try {
      const stored = localStorage.getItem("clearbook_tally_config");
      if (stored) tallyConfig = { ...tallyConfig, ...JSON.parse(stored) };
    } catch {}

    if (!tallyConfig.company) {
      setPostError("Tally company not configured. Go to Settings → Tally to set it up.");
      return;
    }

    setPosting(true);
    setPostError("");
    setPostSuccess(false);
    try {
      const qp = new URLSearchParams({
        tally_company: tallyConfig.company,
        tally_host: tallyConfig.host,
        tally_port: String(tallyConfig.port),
        tally_edu_mode: "true",
      });
      const res = await fetch(
        `${API}/api/v1/vouchers/${voucher.id}/post-to-tally?${qp}`,
        { method: "POST" }
      );
      if (res.ok) {
        const data = await res.json();
        if (data?.success === false) {
          setPostError(data?.error || "Tally rejected the voucher. Check ledger names exist in Tally.");
        } else {
          setPostSuccess(true);
          if (data?.id) setVoucher((prev: any) => ({ ...prev, ...data }));
        }
      } else {
        const err = await res.json().catch(() => ({}));
        const errMsg = Array.isArray(err?.detail)
          ? err.detail.map((e: any) => e.msg || JSON.stringify(e)).join("; ")
          : typeof err?.detail === "string"
          ? err.detail
          : `Failed to post to Tally (${res.status})`;
        setPostError(errMsg);
      }
    } catch (e: any) {
      setPostError(e?.message || "Could not reach Tally. Check your Tally connection.");
    } finally {
      setPosting(false);
    }
  }

  // Entry row helpers
  function updateEntry(idx: number, field: keyof LedgerEntry, value: any) {
    setEntries(prev => prev.map((e, i) => i === idx ? { ...e, [field]: value } : e));
    setSaveEntriesError("");
    setSaveEntriesSuccess(false);
  }
  function addRow() {
    setEntries(prev => [...prev, emptyEntry()]);
  }
  function removeRow(idx: number) {
    setEntries(prev => prev.filter((_, i) => i !== idx));
  }

  const totalDebit = entries.filter(e => e.is_debit).reduce((s, e) => s + (parseFloat(String(e.amount)) || 0), 0);
  const totalCredit = entries.filter(e => !e.is_debit).reduce((s, e) => s + (parseFloat(String(e.amount)) || 0), 0);
  const balanced = Math.abs(totalDebit - totalCredit) < 0.01;

  const isApproved = voucher?.status === "approved";
  const isPending = voucher?.status === "pending" || voucher?.status === "pending_approval";
  const isDraft = voucher?.status === "draft";
  const isPosted = voucher?.status === "synced_to_tally" || voucher?.status === "posted_to_tally";
  const canEditEntries = !isPosted;
  const statusSt = voucher ? (statusStyle[voucher.status] ?? fallbackStyle) : fallbackStyle;

  const clientId = voucher?.client_id || voucher?.client;
  const clientObj = clients.find((c: any) => c.id === clientId);
  const clientName = voucher?.client_name || clientObj?.name || clientId || "—";

  const formattedAmount = voucher?.amount
    ? Number(voucher.amount).toLocaleString("en-AE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Voucher Detail"
        subtitle={voucher?.id ? `#${voucher.id.slice(0, 8)}…` : "Loading…"}
        actions={
          <button
            onClick={() => router.push("/vouchers")}
            style={{ height: "32px", padding: "0 14px", background: "none", border: "1px solid #e0e0e0", borderRadius: "8px", fontSize: "12.5px", color: "#525252", cursor: "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
            onMouseEnter={e => (e.currentTarget.style.background = "#f5f5f5")}
            onMouseLeave={e => (e.currentTarget.style.background = "none")}
          >
            <ArrowLeft size={13} />
            Back to Vouchers
          </button>
        }
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px", maxWidth: "900px" }}>

        {loading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: "10px" }}>
            <Loader2 size={18} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Loading voucher…</span>
          </div>
        )}

        {!loading && error && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{error}</span>
          </div>
        )}

        {approveSuccess && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#d1fae5", border: "1px solid #6ee7b7", borderRadius: "8px" }}>
            <CheckCircle size={14} color="#059669" />
            <span style={{ fontSize: "13px", color: "#059669", fontWeight: 500 }}>Voucher approved successfully.</span>
          </div>
        )}

        {postSuccess && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#d1fae5", border: "1px solid #6ee7b7", borderRadius: "8px" }}>
            <CheckCircle size={14} color="#059669" />
            <span style={{ fontSize: "13px", color: "#059669", fontWeight: 500 }}>Voucher posted to Tally successfully.</span>
          </div>
        )}

        {postError && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{postError}</span>
            <button onClick={() => setPostError("")} style={{ marginLeft: "auto", fontSize: "12px", color: "#525252", background: "none", border: "none", cursor: "pointer" }}>Dismiss</button>
          </div>
        )}

        {approveError && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{approveError}</span>
          </div>
        )}

        {!loading && !error && voucher && (
          <>
            {/* Header card — status + action buttons */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: "20px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "12px", color: "#a3a3a3", fontWeight: 500 }}>Status</span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "13px", fontWeight: 600, padding: "4px 10px", borderRadius: "9999px", background: statusSt.bg, color: statusSt.color }}>
                  <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: statusSt.color, flexShrink: 0 }} />
                  {voucher.status.replace(/_/g, " ")}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                {isDraft && !approveSuccess && (
                  <button onClick={handleSubmit} disabled={approving}
                    style={{ height: "36px", padding: "0 20px", background: approving ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "13px", fontWeight: 600, cursor: approving ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
                    onMouseEnter={e => { if (!approving) e.currentTarget.style.background = "#4254d4"; }}
                    onMouseLeave={e => { if (!approving) e.currentTarget.style.background = "#5266eb"; }}
                  >
                    {approving && <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />}
                    {approving ? "Submitting…" : "Submit for Approval"}
                  </button>
                )}

                {isPending && !approveSuccess && (
                  <button onClick={handleApprove} disabled={approving}
                    style={{ height: "36px", padding: "0 20px", background: approving ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "13px", fontWeight: 600, cursor: approving ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
                    onMouseEnter={e => { if (!approving) e.currentTarget.style.background = "#4254d4"; }}
                    onMouseLeave={e => { if (!approving) e.currentTarget.style.background = "#5266eb"; }}
                  >
                    {approving && <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />}
                    {approving ? "Approving…" : "Approve Voucher"}
                  </button>
                )}

                {(isApproved || approveSuccess) && !postSuccess && (
                  <button onClick={handlePostToTally} disabled={posting}
                    style={{ height: "36px", padding: "0 20px", background: posting ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "13px", fontWeight: 600, cursor: posting ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "7px" }}
                    onMouseEnter={e => { if (!posting) e.currentTarget.style.background = "#4254d4"; }}
                    onMouseLeave={e => { if (!posting) e.currentTarget.style.background = "#5266eb"; }}
                  >
                    {posting ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Send size={13} />}
                    {posting ? "Posting…" : "Post to Tally"}
                  </button>
                )}

                {(isApproved || approveSuccess) && (
                  <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#059669", fontWeight: 500 }}>
                    <CheckCircle size={15} color="#059669" /> Approved
                  </span>
                )}

                {postSuccess && (
                  <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#059669", fontWeight: 500 }}>
                    <CheckCircle size={15} color="#059669" /> Posted to Tally
                  </span>
                )}
              </div>
            </div>

            {/* Voucher Info */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
              <div style={{ padding: "14px 20px", borderBottom: "1px solid #ebebeb" }}>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Voucher Information</span>
              </div>
              <div style={{ padding: "20px 24px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "20px" }}>
                <FieldRow label="Voucher ID" value={voucher.id} />
                <FieldRow label="Client" value={clientName} />
                <FieldRow label="Type" value={voucher.voucher_type || voucher.type} />
                <FieldRow label="Amount (AED)" value={formattedAmount} />
                <FieldRow label="Date" value={voucher.voucher_date || voucher.date} />
                <FieldRow label="Reference No." value={voucher.reference_number || voucher.reference} />
              </div>
              {voucher.narration && (
                <div style={{ padding: "0 24px 20px" }}>
                  <FieldRow label="Narration" value={voucher.narration} />
                </div>
              )}
            </div>

            {/* Ledger Entries */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
              <div style={{ padding: "14px 20px", borderBottom: "1px solid #ebebeb", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Ledger Entries</span>
                  {entries.length > 0 && (
                    <span style={{
                      fontSize: "11px", fontWeight: 600, padding: "2px 8px", borderRadius: "9999px",
                      background: balanced ? "#d1fae5" : "#fef3c7",
                      color: balanced ? "#059669" : "#b45309",
                    }}>
                      {balanced ? "Balanced ✓" : `DR ${totalDebit.toFixed(2)} / CR ${totalCredit.toFixed(2)}`}
                    </span>
                  )}
                </div>
                {canEditEntries && (
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button onClick={addRow}
                      style={{ height: "30px", padding: "0 12px", background: "#f5f5f5", border: "1px solid #e0e0e0", borderRadius: "7px", fontSize: "12px", fontWeight: 600, color: "#525252", cursor: "pointer", display: "flex", alignItems: "center", gap: "5px", fontFamily: "var(--font-family-sans)" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#ebebeb")}
                      onMouseLeave={e => (e.currentTarget.style.background = "#f5f5f5")}
                    >
                      <Plus size={12} /> Add Row
                    </button>
                    <button onClick={handleSaveEntries} disabled={savingEntries}
                      style={{ height: "30px", padding: "0 14px", background: savingEntries ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "12px", fontWeight: 600, cursor: savingEntries ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: "5px", fontFamily: "var(--font-family-sans)" }}
                      onMouseEnter={e => { if (!savingEntries) e.currentTarget.style.background = "#4254d4"; }}
                      onMouseLeave={e => { if (!savingEntries) e.currentTarget.style.background = "#5266eb"; }}
                    >
                      {savingEntries ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={12} />}
                      {savingEntries ? "Saving…" : "Save Entries"}
                    </button>
                  </div>
                )}
              </div>

              {/* Save feedback */}
              {saveEntriesSuccess && (
                <div style={{ margin: "10px 20px 0", display: "flex", alignItems: "center", gap: "8px", padding: "10px 14px", background: "#d1fae5", border: "1px solid #6ee7b7", borderRadius: "7px" }}>
                  <CheckCircle size={13} color="#059669" />
                  <span style={{ fontSize: "12.5px", color: "#059669", fontWeight: 500 }}>Entries saved successfully.</span>
                </div>
              )}
              {saveEntriesError && (
                <div style={{ margin: "10px 20px 0", display: "flex", alignItems: "center", gap: "8px", padding: "10px 14px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "7px" }}>
                  <AlertCircle size={13} color="#dc2626" />
                  <span style={{ fontSize: "12.5px", color: "#dc2626" }}>{saveEntriesError}</span>
                  <button onClick={() => setSaveEntriesError("")} style={{ marginLeft: "auto", fontSize: "12px", color: "#525252", background: "none", border: "none", cursor: "pointer" }}>✕</button>
                </div>
              )}

              <div style={{ padding: "16px 20px" }}>
                {/* Table header */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 130px 32px", gap: "8px", marginBottom: "6px", padding: "0 4px" }}>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Ledger Name</span>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Dr / Cr</span>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Amount (AED)</span>
                  <span />
                </div>

                {/* Entry rows */}
                {entries.length === 0 && (
                  <div style={{ padding: "24px 0", textAlign: "center", color: "#a3a3a3", fontSize: "13px" }}>
                    No entries yet. Click <strong>Add Row</strong> to begin.
                  </div>
                )}

                {entries.map((entry, idx) => (
                  <div key={idx} style={{ display: "grid", gridTemplateColumns: "1fr 90px 130px 32px", gap: "8px", marginBottom: "7px", alignItems: "center" }}>
                    {/* Ledger name — picks from master, falls back to free text */}
                    <div style={{ position: "relative" }}>
                      <input
                        list={`ledger-list-${idx}`}
                        type="text"
                        value={entry.ledger_name}
                        onChange={e => {
                          const val = e.target.value;
                          // if user picks from list, store tally_name as ledger_name
                          const matched = ledgers.find(l => l.name === val || l.tally_name === val);
                          updateEntry(idx, "ledger_name", matched ? matched.tally_name : val);
                        }}
                        placeholder={ledgers.length ? "Select or type ledger…" : "e.g. Cash, Sales A/c"}
                        disabled={!canEditEntries}
                        style={{ width: "100%", height: "34px", padding: "0 10px", border: "1px solid #e0e0e0", borderRadius: "7px", fontSize: "13px", fontFamily: "var(--font-family-sans)", background: canEditEntries ? "#fff" : "#f9f9f9", color: "#0a0a0a", outline: "none", boxSizing: "border-box" }}
                        onFocus={e => { e.currentTarget.style.borderColor = "#5266eb"; }}
                        onBlur={e => { e.currentTarget.style.borderColor = "#e0e0e0"; }}
                      />
                      <datalist id={`ledger-list-${idx}`}>
                        {ledgers.map(l => (
                          <option key={l.id} value={l.name} label={l.tally_name !== l.name ? `→ ${l.tally_name}` : undefined} />
                        ))}
                      </datalist>
                    </div>

                    {/* DR / CR toggle */}
                    <div style={{ display: "flex", border: "1px solid #e0e0e0", borderRadius: "7px", overflow: "hidden", height: "34px" }}>
                      <button
                        onClick={() => canEditEntries && updateEntry(idx, "is_debit", true)}
                        style={{ flex: 1, border: "none", fontSize: "12px", fontWeight: 600, cursor: canEditEntries ? "pointer" : "default", fontFamily: "var(--font-family-sans)", background: entry.is_debit ? "#dbeafe" : "#fff", color: entry.is_debit ? "#1d4ed8" : "#a3a3a3", transition: "background 0.15s" }}
                      >DR</button>
                      <button
                        onClick={() => canEditEntries && updateEntry(idx, "is_debit", false)}
                        style={{ flex: 1, border: "none", borderLeft: "1px solid #e0e0e0", fontSize: "12px", fontWeight: 600, cursor: canEditEntries ? "pointer" : "default", fontFamily: "var(--font-family-sans)", background: !entry.is_debit ? "#dcfce7" : "#fff", color: !entry.is_debit ? "#16a34a" : "#a3a3a3", transition: "background 0.15s" }}
                      >CR</button>
                    </div>

                    {/* Amount */}
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={entry.amount || ""}
                      onChange={e => updateEntry(idx, "amount", parseFloat(e.target.value) || 0)}
                      placeholder="0.00"
                      disabled={!canEditEntries}
                      style={{ height: "34px", padding: "0 10px", border: "1px solid #e0e0e0", borderRadius: "7px", fontSize: "13px", fontFamily: "var(--font-family-sans)", background: canEditEntries ? "#fff" : "#f9f9f9", color: "#0a0a0a", outline: "none", textAlign: "right" }}
                      onFocus={e => { e.currentTarget.style.borderColor = "#5266eb"; }}
                      onBlur={e => { e.currentTarget.style.borderColor = "#e0e0e0"; }}
                    />

                    {/* Delete */}
                    {canEditEntries ? (
                      <button onClick={() => removeRow(idx)}
                        style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "none", border: "1px solid #e0e0e0", borderRadius: "7px", cursor: "pointer", color: "#a3a3a3" }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = "#fca5a5"; e.currentTarget.style.color = "#dc2626"; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = "#e0e0e0"; e.currentTarget.style.color = "#a3a3a3"; }}
                      >
                        <Trash2 size={13} />
                      </button>
                    ) : <div />}
                  </div>
                ))}

                {/* Totals row */}
                {entries.length > 0 && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 130px 32px", gap: "8px", marginTop: "10px", paddingTop: "10px", borderTop: "2px solid #ebebeb" }}>
                    <span style={{ fontSize: "12px", fontWeight: 700, color: "#525252", textAlign: "right", paddingRight: "8px" }}>Total</span>
                    <span />
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "0 4px", fontSize: "12px", fontWeight: 700 }}>
                      <span style={{ color: "#1d4ed8" }}>DR {totalDebit.toFixed(2)}</span>
                      <span style={{ color: "#16a34a" }}>CR {totalCredit.toFixed(2)}</span>
                    </div>
                    <span />
                  </div>
                )}

                {isPosted && (
                  <p style={{ fontSize: "12px", color: "#a3a3a3", marginTop: "12px" }}>
                    Entries are locked — this voucher has been posted to Tally.
                  </p>
                )}
              </div>
            </div>

            {/* Source document link */}
            {(voucher.document_id || voucher.source_document_id) && (
              <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Source Document</span>
                  <p style={{ fontSize: "12px", color: "#a3a3a3", marginTop: "2px" }}>This voucher was created from an extracted document</p>
                </div>
                <button
                  onClick={() => router.push(`/documents/${voucher.document_id || voucher.source_document_id}`)}
                  style={{ height: "32px", padding: "0 14px", background: "#eef0fd", color: "#5266eb", border: "none", borderRadius: "7px", fontSize: "12.5px", fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "#dde0fb")}
                  onMouseLeave={e => (e.currentTarget.style.background = "#eef0fd")}
                >View Document</button>
              </div>
            )}
          </>
        )}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function VoucherDetailPageWrapper() {
  return (
    <Suspense fallback={<div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}><Loader2 size={20} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} /><style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style></div>}>
      <VoucherDetailPage />
    </Suspense>
  );
}
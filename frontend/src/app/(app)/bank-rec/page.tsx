"use client";

import { useEffect, useRef, useState } from "react";
import { Topbar } from "@/components/layout/topbar";
import { getClients, uploadBankStatement, matchTransaction, type Client, type Reconciliation, type BankTransaction } from "@/lib/api";
import { Upload, CheckCircle, AlertCircle, ChevronDown, Link2, Unlink } from "lucide-react";

function fmt(n: number) {
  return n.toLocaleString("en-AE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function StatusPill({ matched }: { matched: boolean }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: "4px",
      padding: "2px 8px", borderRadius: "9999px", fontSize: "11px", fontWeight: 600,
      background: matched ? "#d1fae5" : "#fef3c7",
      color: matched ? "#059669" : "#b45309",
    }}>
      <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: "currentColor" }} />
      {matched ? "Matched" : "Unmatched"}
    </span>
  );
}

export default function BankRecPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [rec, setRec] = useState<Reconciliation | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [matchingId, setMatchingId] = useState<string | null>(null);
  const [matchInput, setMatchInput] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getClients().then(c => { setClients(c); if (c.length) setClientId(c[0].id); }).catch(() => {});
  }, []);

  const handleUpload = async (file: File) => {
    if (!clientId) { setUploadError("Select a client first"); return; }
    setUploading(true);
    setUploadError(null);
    try {
      const result = await uploadBankStatement(clientId, file);
      setRec(result);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleMatch = async (txn: BankTransaction) => {
    if (!rec) return;
    const ref = matchInput[txn.id] || txn.suggested || "";
    if (!ref.trim()) return;
    try {
      const updated = await matchTransaction(rec.id, txn.id, ref.trim());
      setRec(updated);
      setMatchingId(null);
    } catch {}
  };

  const matched = rec?.transactions.filter(t => t.matched) ?? [];
  const unmatched = rec?.transactions.filter(t => !t.matched) ?? [];

  const inputStyle = { height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", outline: "none", fontFamily: "var(--font-family-sans)", cursor: "pointer" as const };

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar title="Bank Reconciliation" subtitle="Upload statement · match transactions" />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>

        {/* Upload card */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Client</label>
              <select value={clientId} onChange={e => setClientId(e.target.value)} style={{ ...inputStyle, minWidth: "200px" }}>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div style={{ marginTop: "auto" }}>
              <input ref={fileRef} type="file" accept=".pdf,.csv,.xlsx,.xls" style={{ display: "none" }}
                onChange={e => { if (e.target.files?.[0]) handleUpload(e.target.files[0]); e.target.value = ""; }}
              />
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploading || !clientId}
                style={{ display: "flex", alignItems: "center", gap: "6px", height: "34px", padding: "0 16px", background: uploading || !clientId ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "13px", fontWeight: 600, cursor: uploading || !clientId ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)" }}
                onMouseEnter={e => { if (!uploading && clientId) e.currentTarget.style.background = "#4254d4"; }}
                onMouseLeave={e => { if (!uploading && clientId) e.currentTarget.style.background = "#5266eb"; }}
              >
                {uploading
                  ? <><span style={{ width: "13px", height: "13px", border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite", display: "inline-block" }} /> Uploading…</>
                  : <><Upload size={13} /> Upload Bank Statement</>
                }
              </button>
            </div>
          </div>
          <p style={{ fontSize: "12px", color: "#a3a3a3", margin: 0 }}>Accepts PDF, CSV, XLSX — AI extracts and auto-matches transactions to Tally ledger entries</p>

          {uploadError && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "10px 14px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "7px", fontSize: "12.5px", color: "#dc2626" }}>
              <AlertCircle size={13} /> {uploadError}
            </div>
          )}
        </div>

        {rec && (
          <>
            {/* Summary cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "12px" }}>
              {[
                { label: "Total Transactions", value: rec.summary.total, unit: "txns", color: "#0a0a0a", bg: "#ffffff" },
                { label: "Matched", value: rec.summary.matched, unit: "txns", color: "#059669", bg: "#f0fdf4" },
                { label: "Unmatched", value: rec.summary.unmatched, unit: "txns", color: "#b45309", bg: "#fef3c7" },
                { label: "Closing Balance", value: fmt(rec.summary.closing_balance), unit: "AED", color: "#5266eb", bg: "#eef0fd" },
              ].map(({ label, value, unit, color, bg }) => (
                <div key={label} style={{ padding: "14px 18px", background: bg, border: "1px solid #ebebeb", borderRadius: "12px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>{label}</div>
                  <div style={{ fontSize: "20px", fontWeight: 700, color, fontFamily: "monospace" }}>{value} <span style={{ fontSize: "12px", fontWeight: 500, color: "#a3a3a3" }}>{unit}</span></div>
                </div>
              ))}
            </div>

            {/* Unmatched first */}
            {unmatched.length > 0 && (
              <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
                <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb", background: "#fef3c7", display: "flex", alignItems: "center", gap: "8px" }}>
                  <AlertCircle size={13} color="#b45309" />
                  <span style={{ fontSize: "12.5px", fontWeight: 600, color: "#b45309" }}>{unmatched.length} Unmatched Transactions — need Tally reference</span>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                      {["Date", "Description", "Debit", "Credit", "Status", "Tally Reference", ""].map(h => (
                        <th key={h} style={{ padding: "9px 16px", textAlign: h === "Debit" || h === "Credit" ? "right" : "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {unmatched.map((txn, i) => (
                      <tr key={txn.id} style={{ borderBottom: i < unmatched.length - 1 ? "1px solid #f5f5f5" : "none" }}>
                        <td style={{ padding: "10px 16px", fontSize: "12px", color: "#525252", whiteSpace: "nowrap" }}>{txn.date}</td>
                        <td style={{ padding: "10px 16px", fontSize: "13px", color: "#0a0a0a", maxWidth: "240px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{txn.description}</td>
                        <td style={{ padding: "10px 16px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", color: txn.debit > 0 ? "#dc2626" : "#c0c0c0" }}>{txn.debit > 0 ? fmt(txn.debit) : "—"}</td>
                        <td style={{ padding: "10px 16px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", color: txn.credit > 0 ? "#059669" : "#c0c0c0" }}>{txn.credit > 0 ? fmt(txn.credit) : "—"}</td>
                        <td style={{ padding: "10px 16px" }}><StatusPill matched={false} /></td>
                        <td style={{ padding: "10px 16px" }}>
                          {matchingId === txn.id ? (
                            <input
                              autoFocus
                              value={matchInput[txn.id] ?? txn.suggested ?? ""}
                              onChange={e => setMatchInput(p => ({ ...p, [txn.id]: e.target.value }))}
                              onKeyDown={e => { if (e.key === "Enter") handleMatch(txn); if (e.key === "Escape") setMatchingId(null); }}
                              placeholder="e.g. Utilities Expense – DEWA"
                              style={{ height: "30px", padding: "0 10px", border: "1px solid #5266eb", borderRadius: "6px", fontSize: "12.5px", width: "220px", outline: "none" }}
                            />
                          ) : (
                            <span style={{ fontSize: "12px", color: txn.suggested ? "#b45309" : "#c0c0c0" }}>
                              {txn.suggested ? `Suggested: ${txn.suggested}` : "No suggestion"}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "10px 16px", whiteSpace: "nowrap" }}>
                          {matchingId === txn.id ? (
                            <div style={{ display: "flex", gap: "6px" }}>
                              <button onClick={() => handleMatch(txn)} style={{ height: "28px", padding: "0 10px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "6px", fontSize: "12px", fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-family-sans)" }}>Save</button>
                              <button onClick={() => setMatchingId(null)} style={{ height: "28px", padding: "0 10px", background: "#f5f5f5", border: "1px solid #e0e0e0", borderRadius: "6px", fontSize: "12px", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}>Cancel</button>
                            </div>
                          ) : (
                            <button onClick={() => setMatchingId(txn.id)}
                              style={{ display: "flex", alignItems: "center", gap: "5px", height: "28px", padding: "0 10px", background: "#f5f5f5", border: "1px solid #e0e0e0", borderRadius: "6px", fontSize: "12px", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
                              onMouseEnter={e => (e.currentTarget.style.background = "#ebebeb")}
                              onMouseLeave={e => (e.currentTarget.style.background = "#f5f5f5")}
                            >
                              <Link2 size={11} /> Match
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Matched transactions */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
              <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb", display: "flex", alignItems: "center", gap: "8px" }}>
                <CheckCircle size={13} color="#059669" />
                <span style={{ fontSize: "12.5px", fontWeight: 600, color: "#059669" }}>{matched.length} Matched Transactions</span>
                <span style={{ marginLeft: "auto", fontSize: "12px", color: "#a3a3a3" }}>{rec.filename}</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                    {["Date", "Description", "Debit", "Credit", "Balance", "Status", "Tally Reference"].map(h => (
                      <th key={h} style={{ padding: "9px 16px", textAlign: h === "Debit" || h === "Credit" || h === "Balance" ? "right" : "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matched.map((txn, i) => (
                    <tr key={txn.id} style={{ borderBottom: i < matched.length - 1 ? "1px solid #f5f5f5" : "none" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                      <td style={{ padding: "10px 16px", fontSize: "12px", color: "#525252", whiteSpace: "nowrap" }}>{txn.date}</td>
                      <td style={{ padding: "10px 16px", fontSize: "13px", color: "#0a0a0a", maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{txn.description}</td>
                      <td style={{ padding: "10px 16px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", color: txn.debit > 0 ? "#dc2626" : "#c0c0c0" }}>{txn.debit > 0 ? fmt(txn.debit) : "—"}</td>
                      <td style={{ padding: "10px 16px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", color: txn.credit > 0 ? "#059669" : "#c0c0c0" }}>{txn.credit > 0 ? fmt(txn.credit) : "—"}</td>
                      <td style={{ padding: "10px 16px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", color: "#525252" }}>{fmt(txn.balance)}</td>
                      <td style={{ padding: "10px 16px" }}><StatusPill matched={true} /></td>
                      <td style={{ padding: "10px 16px", fontSize: "12.5px", color: "#525252" }}>{txn.tally_ref ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!rec && !uploading && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px", padding: "60px 20px" }}>
            <Upload size={28} color="#d4d4d4" />
            <p style={{ fontSize: "13px", fontWeight: 500, color: "#525252", margin: 0 }}>Upload a bank statement to begin reconciliation</p>
            <p style={{ fontSize: "12px", color: "#a3a3a3", margin: 0 }}>AI will extract transactions and auto-match to Tally ledger entries</p>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Topbar } from "@/components/layout/topbar";
import {
  getClients, getTrialBalance, getPLReport,
  type Client, type TrialBalanceReport, type PLReport,
} from "@/lib/api";
import { AlertCircle, TrendingUp, ChevronDown, RefreshCw } from "lucide-react";

type ReportType = "trial_balance" | "profit_loss";

function fmt(n: number) {
  return n.toLocaleString("en-AE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function AmountCell({ value, dim }: { value: number; dim?: boolean }) {
  return (
    <td style={{ padding: "9px 16px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", color: value === 0 ? "#c0c0c0" : dim ? "#525252" : "#0a0a0a" }}>
      {value === 0 ? "—" : fmt(value)}
    </td>
  );
}

function TrialBalanceView({ report }: { report: TrialBalanceReport }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(
    Object.fromEntries(report.groups.map(g => [g.name, true]))
  );
  return (
    <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
      {report.demo_mode && (
        <div style={{ padding: "10px 20px", background: "#fef3c7", borderBottom: "1px solid #fde68a", fontSize: "12px", color: "#b45309" }}>
          Demo data — connect TallyPrime via Client → Tally tab to see live figures
        </div>
      )}
      {report.tally_error && (
        <div style={{ padding: "10px 20px", background: "#fef2f2", borderBottom: "1px solid #fca5a5", fontSize: "12px", color: "#dc2626" }}>
          Tally error: {report.tally_error} — showing demo data
        </div>
      )}
      <div style={{ padding: "14px 20px", borderBottom: "1px solid #ebebeb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Trial Balance</span>
          <span style={{ marginLeft: "10px", fontSize: "12px", color: "#a3a3a3" }}>{report.period}</span>
        </div>
        <span style={{ fontSize: "12px", color: "#a3a3a3" }}>Amounts in AED</span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #ebebeb", background: "#fafafa" }}>
            <th style={{ padding: "9px 20px", textAlign: "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Ledger</th>
            <th style={{ padding: "9px 16px", textAlign: "right", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Opening Dr</th>
            <th style={{ padding: "9px 16px", textAlign: "right", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Opening Cr</th>
            <th style={{ padding: "9px 16px", textAlign: "right", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Txn Dr</th>
            <th style={{ padding: "9px 16px", textAlign: "right", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Txn Cr</th>
            <th style={{ padding: "9px 16px", textAlign: "right", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Closing Dr</th>
            <th style={{ padding: "9px 16px", textAlign: "right", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Closing Cr</th>
          </tr>
        </thead>
        <tbody>
          {report.groups.map(group => (
            <>
              <tr key={group.name} onClick={() => setExpanded(p => ({ ...p, [group.name]: !p[group.name] }))}
                style={{ background: "#f9fafb", cursor: "pointer", borderBottom: "1px solid #ebebeb" }}>
                <td colSpan={7} style={{ padding: "8px 20px", fontSize: "12px", fontWeight: 600, color: "#525252", display: "flex", alignItems: "center", gap: "6px" }}>
                  <ChevronDown size={12} style={{ transition: "transform 0.15s", transform: expanded[group.name] ? "rotate(0deg)" : "rotate(-90deg)" }} />
                  {group.name}
                </td>
              </tr>
              {expanded[group.name] && group.entries.map((entry, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                  <td style={{ padding: "9px 20px 9px 36px", fontSize: "13px", color: "#0a0a0a" }}>{entry.ledger}</td>
                  <AmountCell value={entry.opening_dr ?? 0} dim />
                  <AmountCell value={entry.opening_cr ?? 0} dim />
                  <AmountCell value={entry.transactions_dr ?? 0} />
                  <AmountCell value={entry.transactions_cr ?? 0} />
                  <AmountCell value={entry.closing_dr ?? 0} />
                  <AmountCell value={entry.closing_cr ?? 0} />
                </tr>
              ))}
            </>
          ))}
          {/* Totals row */}
          <tr style={{ borderTop: "2px solid #ebebeb", background: "#fafafa" }}>
            <td style={{ padding: "11px 20px", fontSize: "12px", fontWeight: 700, color: "#0a0a0a" }}>Total</td>
            <td colSpan={4} />
            <td style={{ padding: "11px 16px", textAlign: "right", fontSize: "13px", fontWeight: 700, fontFamily: "monospace", color: "#1d4ed8" }}>{fmt(report.totals.debit)}</td>
            <td style={{ padding: "11px 16px", textAlign: "right", fontSize: "13px", fontWeight: 700, fontFamily: "monospace", color: "#16a34a" }}>{fmt(report.totals.credit)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function PLView({ report }: { report: PLReport }) {
  const profit = report.net_profit >= 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {report.demo_mode && (
        <div style={{ padding: "10px 16px", background: "#fef3c7", border: "1px solid #fde68a", borderRadius: "8px", fontSize: "12px", color: "#b45309" }}>
          Demo data — connect TallyPrime via Client → Tally tab to see live figures
        </div>
      )}

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "12px" }}>
        {[
          { label: "Total Income", value: report.total_income, color: "#059669", bg: "#f0fdf4" },
          { label: "Total Expenses", value: report.total_expenses, color: "#dc2626", bg: "#fef2f2" },
          { label: profit ? "Net Profit" : "Net Loss", value: Math.abs(report.net_profit), color: profit ? "#059669" : "#dc2626", bg: profit ? "#f0fdf4" : "#fef2f2" },
        ].map(({ label, value, color, bg }) => (
          <div key={label} style={{ padding: "16px 20px", background: bg, border: "1px solid #ebebeb", borderRadius: "12px" }}>
            <div style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "6px" }}>{label}</div>
            <div style={{ fontSize: "22px", fontWeight: 700, color, fontFamily: "monospace" }}>AED {fmt(value)}</div>
          </div>
        ))}
      </div>

      {/* Income + Expense tables side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        {/* Income */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
          <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb", background: "#f0fdf4" }}>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "#059669", textTransform: "uppercase", letterSpacing: "0.05em" }}>Income</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {report.income.map((item, i) => (
                <tr key={i} style={{ borderBottom: i < report.income.length - 1 ? "1px solid #f5f5f5" : "none" }}>
                  <td style={{ padding: "9px 20px", fontSize: "13px", color: "#0a0a0a" }}>{item.name}</td>
                  <td style={{ padding: "9px 20px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", fontWeight: 500, color: "#059669" }}>{fmt(item.amount)}</td>
                </tr>
              ))}
              <tr style={{ borderTop: "2px solid #ebebeb", background: "#f0fdf4" }}>
                <td style={{ padding: "10px 20px", fontSize: "12px", fontWeight: 700 }}>Total Income</td>
                <td style={{ padding: "10px 20px", textAlign: "right", fontSize: "13px", fontWeight: 700, fontFamily: "monospace", color: "#059669" }}>{fmt(report.total_income)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Expenses */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
          <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb", background: "#fef2f2" }}>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "#dc2626", textTransform: "uppercase", letterSpacing: "0.05em" }}>Expenses</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {report.expenses.map((item, i) => (
                <tr key={i} style={{ borderBottom: i < report.expenses.length - 1 ? "1px solid #f5f5f5" : "none" }}>
                  <td style={{ padding: "9px 20px", fontSize: "13px", color: "#0a0a0a" }}>{item.name}</td>
                  <td style={{ padding: "9px 20px", textAlign: "right", fontSize: "13px", fontFamily: "monospace", fontWeight: 500, color: "#dc2626" }}>{fmt(item.amount)}</td>
                </tr>
              ))}
              <tr style={{ borderTop: "2px solid #ebebeb", background: "#fef2f2" }}>
                <td style={{ padding: "10px 20px", fontSize: "12px", fontWeight: 700 }}>Total Expenses</td>
                <td style={{ padding: "10px 20px", textAlign: "right", fontSize: "13px", fontWeight: 700, fontFamily: "monospace", color: "#dc2626" }}>{fmt(report.total_expenses)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Net profit row */}
      <div style={{ padding: "16px 24px", background: profit ? "#f0fdf4" : "#fef2f2", border: `1px solid ${profit ? "#bbf7d0" : "#fecaca"}`, borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "14px", fontWeight: 600, color: profit ? "#059669" : "#dc2626" }}>{profit ? "Net Profit" : "Net Loss"} — {report.period}</span>
        <span style={{ fontSize: "20px", fontWeight: 700, fontFamily: "monospace", color: profit ? "#059669" : "#dc2626" }}>AED {fmt(Math.abs(report.net_profit))}</span>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [reportType, setReportType] = useState<ReportType>("profit_loss");
  const [report, setReport] = useState<TrialBalanceReport | PLReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClients().then(c => { setClients(c); if (c.length) setClientId(c[0].id); }).catch(() => {});
  }, []);

  const fetchReport = async () => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    try {
      if (reportType === "profit_loss") {
        setReport(await getPLReport(clientId));
      } else {
        setReport(await getTrialBalance(clientId));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (clientId) fetchReport(); }, [clientId, reportType]);

  const inputStyle = { height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", outline: "none", fontFamily: "var(--font-family-sans)", cursor: "pointer" as const };

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Financial Reports"
        subtitle="Tally-sourced reports"
        actions={
          <button onClick={fetchReport} style={{ display: "flex", alignItems: "center", gap: "6px", height: "32px", padding: "0 14px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "12.5px", fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
            onMouseEnter={e => (e.currentTarget.style.background = "#4254d4")}
            onMouseLeave={e => (e.currentTarget.style.background = "#5266eb")}
          >
            <RefreshCw size={12} /> Refresh
          </button>
        }
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* Controls */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "16px 20px", display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Client</label>
            <select value={clientId} onChange={e => setClientId(e.target.value)} style={{ ...inputStyle, minWidth: "200px" }}>
              {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Report Type</label>
            <select value={reportType} onChange={e => setReportType(e.target.value as ReportType)} style={inputStyle}>
              <option value="profit_loss">Profit & Loss</option>
              <option value="trial_balance">Trial Balance</option>
            </select>
          </div>
        </div>

        {loading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "60px 0", gap: "10px" }}>
            <div style={{ width: "18px", height: "18px", border: "2px solid #ebebeb", borderTopColor: "#5266eb", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
            <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Fetching from Tally…</span>
          </div>
        )}

        {!loading && error && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{error}</span>
          </div>
        )}

        {!loading && !error && !report && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px", padding: "60px 20px" }}>
            <TrendingUp size={28} color="#d4d4d4" />
            <p style={{ fontSize: "13px", color: "#a3a3a3", margin: 0 }}>Select a client and report type to view</p>
          </div>
        )}

        {!loading && report && (
          report.report_type === "profit_loss"
            ? <PLView report={report as PLReport} />
            : <TrialBalanceView report={report as TrialBalanceReport} />
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

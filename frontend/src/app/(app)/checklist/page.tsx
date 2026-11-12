"use client";

import { useEffect, useState } from "react";
import { Topbar } from "@/components/layout/topbar";
import { getClients, getChecklist, updateChecklistItem, type Client, type Checklist, type ChecklistItem } from "@/lib/api";
import { CheckCircle, Circle, MinusCircle, AlertCircle, ChevronDown, ChevronRight } from "lucide-react";

const PRIORITY_COLOR: Record<string, { color: string; bg: string }> = {
  high:   { color: "#dc2626", bg: "#fef2f2" },
  medium: { color: "#b45309", bg: "#fef3c7" },
  low:    { color: "#525252", bg: "#f5f5f5" },
};

function PriorityBadge({ p }: { p: string }) {
  const { color, bg } = PRIORITY_COLOR[p] ?? { color: "#525252", bg: "#f5f5f5" };
  return <span style={{ display: "inline-flex", padding: "1px 7px", borderRadius: "9999px", fontSize: "10px", fontWeight: 600, background: bg, color, textTransform: "uppercase", letterSpacing: "0.05em" }}>{p}</span>;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "complete") return <CheckCircle size={16} color="#059669" />;
  if (status === "na") return <MinusCircle size={16} color="#a3a3a3" />;
  return <Circle size={16} color="#d4d4d4" />;
}

function ProgressBar({ complete, total }: { complete: number; total: number }) {
  const pct = total > 0 ? (complete / total) * 100 : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <div style={{ flex: 1, height: "6px", borderRadius: "9999px", background: "#f0f0f0", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: "9999px", background: pct === 100 ? "#059669" : "#5266eb", transition: "width 0.4s" }} />
      </div>
      <span style={{ fontSize: "12px", fontWeight: 600, color: pct === 100 ? "#059669" : "#525252", whiteSpace: "nowrap" }}>{complete}/{total}</span>
    </div>
  );
}

export default function ChecklistPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [period, setPeriod] = useState("");
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const now = new Date();
    setPeriod(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
    setMonthOptions(Array.from({ length: 12 }, (_, i) => {
      const d = new Date(now);
      d.setMonth(d.getMonth() - i);
      const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      return { val, label: d.toLocaleDateString("en-AE", { month: "long", year: "numeric" }) };
    }));
    getClients().then(c => { setClients(c); if (c.length) setClientId(c[0].id); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    getChecklist(clientId, period)
      .then(setChecklist)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load checklist"))
      .finally(() => setLoading(false));
  }, [clientId, period]);

  const handleToggle = async (item: ChecklistItem) => {
    if (!checklist) return;
    const next: "pending" | "complete" | "na" =
      item.status === "pending" ? "complete" : item.status === "complete" ? "na" : "pending";
    setUpdating(item.id);
    try {
      const updated = await updateChecklistItem(clientId, item.id, next, period);
      setChecklist(updated);
    } catch {}
    finally { setUpdating(null); }
  };

  // Group items by category
  const grouped = checklist
    ? checklist.items.reduce((acc, item) => {
        (acc[item.category] = acc[item.category] || []).push(item);
        return acc;
      }, {} as Record<string, ChecklistItem[]>)
    : {};

  const categories = Object.keys(grouped);

  const inputStyle = { height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", outline: "none", fontFamily: "var(--font-family-sans)", cursor: "pointer" as const };

  const [monthOptions, setMonthOptions] = useState<{ val: string; label: string }[]>([]);

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Month-end Checklist"
        subtitle={checklist ? `${checklist.summary.complete}/${checklist.summary.total} complete` : "Month-end closing tasks"}
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
            <label style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Period</label>
            <select value={period} onChange={e => setPeriod(e.target.value)} style={inputStyle}>
              {monthOptions.map(o => <option key={o.val} value={o.val}>{o.label}</option>)}
            </select>
          </div>
          {checklist && (
            <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", gap: "4px", minWidth: "200px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em" }}>Progress</span>
                <span style={{ fontSize: "11px", color: "#a3a3a3" }}>
                  {checklist.summary.na > 0 && `${checklist.summary.na} N/A`}
                </span>
              </div>
              <ProgressBar complete={checklist.summary.complete} total={checklist.summary.total - checklist.summary.na} />
            </div>
          )}
        </div>

        {loading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "60px 0", gap: "10px" }}>
            <div style={{ width: "18px", height: "18px", border: "2px solid #ebebeb", borderTopColor: "#5266eb", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
            <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Loading checklist…</span>
          </div>
        )}

        {!loading && error && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{error}</span>
          </div>
        )}

        {!loading && checklist && (
          <>
            {/* Summary row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "12px" }}>
              {[
                { label: "Complete", value: checklist.summary.complete, color: "#059669", bg: "#f0fdf4" },
                { label: "Pending", value: checklist.summary.pending, color: "#b45309", bg: "#fef3c7" },
                { label: "Not Applicable", value: checklist.summary.na, color: "#525252", bg: "#f5f5f5" },
              ].map(({ label, value, color, bg }) => (
                <div key={label} style={{ padding: "14px 18px", background: bg, border: "1px solid #ebebeb", borderRadius: "12px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>{label}</div>
                  <div style={{ fontSize: "24px", fontWeight: 700, color }}>{value}</div>
                </div>
              ))}
            </div>

            {/* Legend */}
            <div style={{ display: "flex", alignItems: "center", gap: "16px", padding: "10px 16px", background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "10px", fontSize: "12px", color: "#525252" }}>
              <span style={{ fontWeight: 600, color: "#a3a3a3", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em" }}>Click to toggle:</span>
              <span style={{ display: "flex", alignItems: "center", gap: "5px" }}><Circle size={13} color="#d4d4d4" /> Pending</span>
              <span style={{ display: "flex", alignItems: "center", gap: "5px" }}><CheckCircle size={13} color="#059669" /> Complete</span>
              <span style={{ display: "flex", alignItems: "center", gap: "5px" }}><MinusCircle size={13} color="#a3a3a3" /> N/A</span>
            </div>

            {/* Checklist by category */}
            {categories.map(cat => {
              const items = grouped[cat];
              const isOpen = collapsed[cat] !== false;
              const catComplete = items.filter(i => i.status === "complete").length;
              const catPending = items.filter(i => i.status === "pending").length;
              return (
                <div key={cat} style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
                  <button
                    onClick={() => setCollapsed(p => ({ ...p, [cat]: !isOpen }))}
                    style={{ width: "100%", display: "flex", alignItems: "center", gap: "10px", padding: "13px 20px", background: "none", border: "none", cursor: "pointer", textAlign: "left", borderBottom: isOpen ? "1px solid #ebebeb" : "none" }}
                  >
                    {isOpen ? <ChevronDown size={14} color="#a3a3a3" /> : <ChevronRight size={14} color="#a3a3a3" />}
                    <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a", flex: 1 }}>{cat}</span>
                    <span style={{ fontSize: "11.5px", color: catPending > 0 ? "#b45309" : "#059669" }}>
                      {catComplete}/{items.length} done
                    </span>
                  </button>

                  {isOpen && (
                    <div>
                      {items.map((item, i) => {
                        const isUpdating = updating === item.id;
                        return (
                          <div
                            key={item.id}
                            onClick={() => !isUpdating && handleToggle(item)}
                            style={{
                              display: "flex", alignItems: "flex-start", gap: "12px", padding: "13px 20px",
                              borderBottom: i < items.length - 1 ? "1px solid #f5f5f5" : "none",
                              cursor: isUpdating ? "wait" : "pointer",
                              background: item.status === "complete" ? "#fafffe" : item.status === "na" ? "#fafafa" : "#ffffff",
                              opacity: item.status === "na" ? 0.65 : 1,
                              transition: "background 0.1s",
                            }}
                            onMouseEnter={e => { if (item.status === "pending") e.currentTarget.style.background = "#fafafa"; }}
                            onMouseLeave={e => { if (item.status === "pending") e.currentTarget.style.background = "#ffffff"; }}
                          >
                            <div style={{ marginTop: "1px", flexShrink: 0 }}>
                              {isUpdating
                                ? <div style={{ width: "16px", height: "16px", border: "2px solid #ebebeb", borderTopColor: "#5266eb", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                                : <StatusIcon status={item.status} />
                              }
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "2px" }}>
                                <span style={{ fontSize: "13px", fontWeight: item.status === "pending" ? 500 : 450, color: item.status === "complete" ? "#059669" : "#0a0a0a", textDecoration: item.status === "complete" ? "line-through" : "none" }}>
                                  {item.task}
                                </span>
                                <PriorityBadge p={item.priority} />
                              </div>
                              <span style={{ fontSize: "12px", color: "#a3a3a3" }}>{item.description}</span>
                              {item.completed_by && item.status === "complete" && (
                                <span style={{ display: "block", fontSize: "11px", color: "#059669", marginTop: "2px" }}>
                                  ✓ Done by {item.completed_by} · {item.completed_at ? new Date(item.completed_at).toLocaleDateString("en-AE") : ""}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

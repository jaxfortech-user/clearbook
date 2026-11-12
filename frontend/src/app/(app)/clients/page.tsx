"use client";
export const instant = false;

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { Search, X, Loader2, AlertCircle, Users } from "lucide-react";
import { getClients, createClient, type Client } from "@/lib/api";

const statusStyle: Record<string, { bg: string; color: string }> = {
  active:   { bg: "#d1fae5", color: "#059669" },
  pending:  { bg: "#fef3c7", color: "#b45309" },
  inactive: { bg: "#f5f5f5", color: "#a3a3a3" },
};

const cols = ["Client Name", "TRN", "Type", "Status", "Documents", "Last Activity", ""];

const ENTITY_TYPES = ["LLC", "FZE", "FZCO", "Co.", "LLP", "Sole Proprietorship", "Branch", "Representative Office"];

const INDUSTRIES = [
  "Trading", "Real Estate", "Logistics & Freight", "Construction",
  "Hospitality", "Retail", "Manufacturing", "IT & Technology",
  "Healthcare", "Education", "Professional Services", "Other",
];

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

const inputStyle = {
  height: "34px", padding: "0 10px", borderRadius: "7px",
  border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a",
  background: "#ffffff", outline: "none", width: "100%",
  fontFamily: "var(--font-family-sans)", boxSizing: "border-box" as const,
};

export default function ClientsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  useEffect(() => { if (searchParams.get("new") === "true") setShowModal(true); }, [searchParams]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [form, setForm] = useState({
    name: "", trn: "", type: "LLC", email: "",
    phone: "", contactPerson: "", industry: "", address: "",
  });

  useEffect(() => {
    setLoading(true);
    getClients()
      .then(setClients)
      .catch(e => setLoadError(e.message || "Failed to load clients"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = clients.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) || (c.trn ?? "").includes(search)
  );

  function openModal() {
    setForm({ name: "", trn: "", type: "LLC", email: "", phone: "", contactPerson: "", industry: "", address: "" });
    setSaveError("");
    setShowModal(true);
  }

  function closeModal() {
    if (saving) return;
    setShowModal(false);
  }

  function set(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    if (!form.name.trim()) { setSaveError("Company name is required."); return; }
    if (!form.trn.trim()) { setSaveError("TRN is required."); return; }
    setSaveError("");
    setSaving(true);
    try {
      const created = await createClient({
        name: form.name.trim(),
        trn: form.trn.trim(),
        type: form.type,
        contact_email: form.email.trim() || undefined,
        contact_phone: form.phone.trim() || undefined,
        contact_name: form.contactPerson.trim() || undefined,
        industry: form.industry || undefined,
      });
      setClients(prev => [created, ...prev]);
      setShowModal(false);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Failed to create client.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Clients"
        subtitle={loading ? "Loading…" : `${clients.length} total clients`}
        actions={
          <button
            onClick={openModal}
            style={{ height: "32px", padding: "0 14px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "12.5px", fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
            onMouseEnter={e => (e.currentTarget.style.background = "#4254d4")}
            onMouseLeave={e => (e.currentTarget.style.background = "#5266eb")}
          >+ Add Client</button>
        }
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>

        {/* Loading */}
        {loading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: "10px" }}>
            <Loader2 size={18} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Loading clients…</span>
          </div>
        )}

        {/* Error */}
        {!loading && loadError && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ fontSize: "13px", color: "#dc2626" }}>{loadError}</span>
            <button
              onClick={() => { setLoadError(""); setLoading(true); getClients().then(setClients).catch(e => setLoadError(e.message)).finally(() => setLoading(false)); }}
              style={{ marginLeft: "auto", fontSize: "12px", color: "#5266eb", background: "none", border: "none", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
            >Retry</button>
          </div>
        )}

        {/* Content */}
        {!loading && !loadError && (
          <>
            {/* Search */}
            <div style={{ maxWidth: "320px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "0 12px", height: "34px", background: searchFocused ? "#ffffff" : "#f5f5f5", border: `1px solid ${searchFocused ? "#5266eb" : "#e8e8e8"}`, borderRadius: "8px", transition: "all 0.15s", boxShadow: searchFocused ? "0 0 0 3px rgba(82,102,235,0.08)" : "none" }}>
                <Search size={13} color={searchFocused ? "#5266eb" : "#b0b0b0"} style={{ flexShrink: 0 }} />
                <input type="text" placeholder="Search by name or TRN…" value={search} onChange={e => setSearch(e.target.value)}
                  onFocus={() => setSearchFocused(true)} onBlur={() => setSearchFocused(false)}
                  style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontSize: "13px", color: "#0a0a0a", fontFamily: "var(--font-family-sans)" }}
                />
              </div>
            </div>

            {/* Table */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                    {cols.map(h => <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((client, i) => (
                    <tr key={client.id} style={{ borderBottom: i < filtered.length - 1 ? "1px solid #ebebeb" : "none" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ padding: "12px 20px", fontSize: "13px", fontWeight: 500, color: "#0a0a0a", whiteSpace: "nowrap" }}>{client.name}</td>
                      <td style={{ padding: "12px 20px", fontSize: "11px", fontFamily: "monospace", color: "#a3a3a3", whiteSpace: "nowrap" }}>{client.trn}</td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", whiteSpace: "nowrap" }}>{client.type}</td>
                      <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontSize: "11px", fontWeight: 500, padding: "2px 8px", borderRadius: "9999px", ...statusStyle[client.status] }}>
                          <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: statusStyle[client.status]?.color, flexShrink: 0 }} />
                          {client.status}
                        </span>
                      </td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", whiteSpace: "nowrap" }}>{client.docs ?? 0}</td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", color: "#a3a3a3", whiteSpace: "nowrap" }}>{client.lastActivity ?? "—"}</td>
                      <td style={{ padding: "12px 24px 12px 20px", whiteSpace: "nowrap", textAlign: "right" }}>
                        <button
                          onClick={() => router.push(`/clients/${client.id}`)}
                          style={{ height: "28px", padding: "0 12px", background: "none", border: "1px solid #ebebeb", borderRadius: "6px", fontSize: "12px", color: "#525252", cursor: "pointer", fontFamily: "var(--font-family-sans)" }}
                          onMouseEnter={e => { e.currentTarget.style.background = "#f5f5f5"; e.currentTarget.style.borderColor = "#d4d4d4"; }}
                          onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.borderColor = "#ebebeb"; }}
                        >View</button>
                      </td>
                    </tr>
                  ))}

                  {/* Empty state */}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ padding: "60px 20px", textAlign: "center" }}>
                        <Users size={32} color="#d4d4d4" style={{ margin: "0 auto 10px" }} />
                        <p style={{ fontSize: "13px", fontWeight: 500, color: "#a3a3a3" }}>
                          {search ? "No clients match your search." : "No clients yet. Add your first client to get started."}
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* ── ADD CLIENT MODAL ── */}
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
                <h2 style={{ fontSize: "15px", fontWeight: 650, color: "#0a0a0a", letterSpacing: "-0.2px" }}>Add New Client</h2>
                <p style={{ fontSize: "12px", color: "#a3a3a3", marginTop: "2px" }}>Enter the company details below</p>
              </div>
              <button
                onClick={closeModal}
                style={{ width: "28px", height: "28px", display: "flex", alignItems: "center", justifyContent: "center", background: "#f5f5f5", border: "none", borderRadius: "7px", cursor: "pointer" }}
                onMouseEnter={e => (e.currentTarget.style.background = "#ebebeb")}
                onMouseLeave={e => (e.currentTarget.style.background = "#f5f5f5")}
              >
                <X size={14} color="#525252" />
              </button>
            </div>

            {/* Form */}
            <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px", flex: 1 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <Field label="Company Name" required>
                  <input value={form.name} onChange={e => set("name", e.target.value)} placeholder="Al Faris Trading LLC"
                    style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
                <Field label="TRN" required>
                  <input value={form.trn} onChange={e => set("trn", e.target.value)} placeholder="100234567890003"
                    style={{ ...inputStyle, fontFamily: "monospace" }} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <Field label="Entity Type" required>
                  <select value={form.type} onChange={e => set("type", e.target.value)}
                    style={{ ...inputStyle, cursor: "pointer" }} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")}>
                    {ENTITY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </Field>
                <Field label="Industry">
                  <select value={form.industry} onChange={e => set("industry", e.target.value)}
                    style={{ ...inputStyle, cursor: "pointer" }} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")}>
                    <option value="">Select industry…</option>
                    {INDUSTRIES.map(ind => <option key={ind} value={ind}>{ind}</option>)}
                  </select>
                </Field>
              </div>

              <Field label="Contact Person">
                <input value={form.contactPerson} onChange={e => set("contactPerson", e.target.value)} placeholder="Mohammed Al Rashid"
                  style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
              </Field>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <Field label="Email">
                  <input type="email" value={form.email} onChange={e => set("email", e.target.value)} placeholder="accounts@company.ae"
                    style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
                <Field label="Phone">
                  <input value={form.phone} onChange={e => set("phone", e.target.value)} placeholder="+971 4 XXX XXXX"
                    style={inputStyle} onFocus={e => (e.target.style.borderColor = "#5266eb")} onBlur={e => (e.target.style.borderColor = "#e0e0e0")} />
                </Field>
              </div>

              <Field label="Address">
                <input value={form.address} onChange={e => set("address", e.target.value)} placeholder="Office 402, Business Bay, Dubai"
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
                {saving ? "Saving…" : "Add Client"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

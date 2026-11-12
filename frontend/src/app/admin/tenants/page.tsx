"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Building2, Users, Briefcase, CheckCircle, XCircle, LogOut, BookOpen } from "lucide-react";
import { getTenants, createTenant, updateTenant, TenantSummary, CreateTenantPayload } from "@/lib/api";
import { getAuthUser, clearToken } from "@/lib/auth";

const PLANS = ["trial", "professional", "enterprise"];
const PLAN_COLOR: Record<string, string> = {
  trial: "#f59e0b",
  professional: "#5266eb",
  enterprise: "#7c3aed",
};

export default function TenantsPage() {
  const router = useRouter();
  const user = typeof window !== "undefined" ? getAuthUser() : null;
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [form, setForm] = useState<CreateTenantPayload>({
    name: "", contact_email: "", contact_phone: "", plan: "trial",
    admin_email: "", admin_password: "", admin_full_name: "",
  });

  useEffect(() => {
    if (user?.role !== "super_admin") { router.push("/dashboard"); return; }
    load();
  }, []);

  async function load() {
    setLoading(true);
    try { setTenants(await getTenants()); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to load"); }
    finally { setLoading(false); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError(null); setSuccess(null);
    try {
      const res = await createTenant(form);
      setSuccess(res.message);
      setShowNew(false);
      setForm({ name: "", contact_email: "", contact_phone: "", plan: "trial", admin_email: "", admin_password: "", admin_full_name: "" });
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to create"); }
    finally { setSaving(false); }
  }

  async function toggleActive(t: TenantSummary) {
    try {
      await updateTenant(t.id, { is_active: !t.is_active });
      await load();
    } catch {}
  }

  function handleLogout() { clearToken(); router.push("/login"); }

  const inp: React.CSSProperties = { height: "36px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", width: "100%", outline: "none", fontFamily: "var(--font-family-sans)" };

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa", fontFamily: "var(--font-family-sans)" }}>
      {/* Top bar */}
      <div style={{ background: "#fff", borderBottom: "1px solid #ebebeb", padding: "0 32px", height: "56px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{ width: "28px", height: "28px", background: "#5266eb", borderRadius: "7px", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <BookOpen size={14} color="#fff" strokeWidth={2.5} />
          </div>
          <span style={{ fontSize: "14px", fontWeight: 700, color: "#0a0a0a" }}>Clearbook</span>
          <span style={{ fontSize: "12px", color: "#a0a0a0", marginLeft: "4px" }}>/ Super Admin</span>
        </div>
        <button onClick={handleLogout} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#6b7280", background: "none", border: "none", cursor: "pointer" }}>
          <LogOut size={14} /> Sign out
        </button>
      </div>

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "32px 24px" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px" }}>
          <div>
            <h1 style={{ fontSize: "20px", fontWeight: 700, color: "#0a0a0a", margin: 0 }}>CA Tenants</h1>
            <p style={{ fontSize: "13px", color: "#6b7280", margin: "4px 0 0" }}>Manage CA firms on the Clearbook platform</p>
          </div>
          <button onClick={() => setShowNew(true)} style={{ display: "flex", alignItems: "center", gap: "7px", height: "36px", padding: "0 16px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "13px", fontWeight: 600, cursor: "pointer" }}>
            <Plus size={14} /> Add CA Firm
          </button>
        </div>

        {success && <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "8px", padding: "10px 14px", fontSize: "13px", color: "#166534", marginBottom: "16px" }}>{success}</div>}
        {error && <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", padding: "10px 14px", fontSize: "13px", color: "#991b1b", marginBottom: "16px" }}>{error}</div>}

        {/* Summary cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "24px" }}>
          {[
            { label: "Total Tenants", value: tenants.length, icon: Building2 },
            { label: "Active Firms", value: tenants.filter(t => t.is_active).length, icon: CheckCircle },
            { label: "Total Clients", value: tenants.reduce((s, t) => s + t.client_count, 0), icon: Briefcase },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} style={{ background: "#fff", border: "1px solid #ebebeb", borderRadius: "10px", padding: "18px 20px", display: "flex", alignItems: "center", gap: "14px" }}>
              <div style={{ width: "36px", height: "36px", background: "#eef0fd", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Icon size={16} color="#5266eb" />
              </div>
              <div>
                <div style={{ fontSize: "22px", fontWeight: 700, color: "#0a0a0a", lineHeight: 1 }}>{loading ? "—" : value}</div>
                <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "3px" }}>{label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Tenant table */}
        <div style={{ background: "#fff", border: "1px solid #ebebeb", borderRadius: "10px", overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 90px 80px 80px 100px", padding: "10px 20px", borderBottom: "1px solid #f0f0f0", fontSize: "11px", fontWeight: 600, color: "#a0a0a0", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            <span>CA Firm</span><span>Contact</span><span>Plan</span><span>Users</span><span>Clients</span><span>Status</span>
          </div>
          {loading && <div style={{ padding: "32px", textAlign: "center", color: "#a0a0a0", fontSize: "13px" }}>Loading…</div>}
          {!loading && tenants.length === 0 && (
            <div style={{ padding: "48px", textAlign: "center", color: "#a0a0a0", fontSize: "13px" }}>
              No CA firms yet. Add your first tenant.
            </div>
          )}
          {tenants.map((t, i) => (
            <div key={t.id} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 90px 80px 80px 100px", padding: "14px 20px", borderBottom: i < tenants.length - 1 ? "1px solid #f5f5f5" : "none", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>{t.name}</div>
                <div style={{ fontSize: "11px", color: "#a0a0a0", marginTop: "2px" }}>{t.slug}</div>
              </div>
              <div style={{ fontSize: "12px", color: "#6b7280", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.contact_email || "—"}</div>
              <div>
                <span style={{ fontSize: "11px", fontWeight: 600, color: PLAN_COLOR[t.plan] ?? "#6b7280", background: `${PLAN_COLOR[t.plan] ?? "#6b7280"}15`, padding: "3px 8px", borderRadius: "5px", textTransform: "capitalize" }}>{t.plan}</span>
              </div>
              <div style={{ fontSize: "13px", color: "#374151", display: "flex", alignItems: "center", gap: "5px" }}><Users size={12} color="#a0a0a0" />{t.user_count}</div>
              <div style={{ fontSize: "13px", color: "#374151", display: "flex", alignItems: "center", gap: "5px" }}><Briefcase size={12} color="#a0a0a0" />{t.client_count}</div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button onClick={() => toggleActive(t)} title={t.is_active ? "Deactivate" : "Activate"} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                  {t.is_active
                    ? <CheckCircle size={16} color="#16a34a" />
                    : <XCircle size={16} color="#dc2626" />}
                </button>
                <span style={{ fontSize: "11px", color: t.is_active ? "#16a34a" : "#dc2626" }}>{t.is_active ? "Active" : "Inactive"}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* New tenant modal */}
      {showNew && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={() => setShowNew(false)}>
          <div style={{ background: "#fff", borderRadius: "12px", padding: "28px", width: "480px", maxHeight: "90vh", overflowY: "auto" }} onClick={e => e.stopPropagation()}>
            <h2 style={{ fontSize: "16px", fontWeight: 700, color: "#0a0a0a", margin: "0 0 20px" }}>Add CA Firm</h2>
            <form onSubmit={handleCreate}>
              <div style={{ display: "grid", gap: "14px" }}>
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#374151", display: "block", marginBottom: "5px" }}>Firm Name *</label>
                  <input style={inp} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required placeholder="Al Farooq & Associates CA" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div>
                    <label style={{ fontSize: "12px", fontWeight: 600, color: "#374151", display: "block", marginBottom: "5px" }}>Contact Email</label>
                    <input style={inp} type="email" value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} placeholder="info@cafirm.ae" />
                  </div>
                  <div>
                    <label style={{ fontSize: "12px", fontWeight: 600, color: "#374151", display: "block", marginBottom: "5px" }}>Plan</label>
                    <select style={inp} value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))}>
                      {PLANS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
                    </select>
                  </div>
                </div>
                <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: "14px" }}>
                  <p style={{ fontSize: "12px", fontWeight: 600, color: "#374151", margin: "0 0 10px" }}>CA Admin Account</p>
                  <div style={{ display: "grid", gap: "10px" }}>
                    <div>
                      <label style={{ fontSize: "12px", color: "#6b7280", display: "block", marginBottom: "4px" }}>Full Name</label>
                      <input style={inp} value={form.admin_full_name} onChange={e => setForm(f => ({ ...f, admin_full_name: e.target.value }))} placeholder="CA Ahmed Al Mansouri" />
                    </div>
                    <div>
                      <label style={{ fontSize: "12px", color: "#6b7280", display: "block", marginBottom: "4px" }}>Email *</label>
                      <input style={inp} type="email" value={form.admin_email} onChange={e => setForm(f => ({ ...f, admin_email: e.target.value }))} required placeholder="ahmed@cafirm.ae" />
                    </div>
                    <div>
                      <label style={{ fontSize: "12px", color: "#6b7280", display: "block", marginBottom: "4px" }}>Password *</label>
                      <input style={inp} type="password" value={form.admin_password} onChange={e => setForm(f => ({ ...f, admin_password: e.target.value }))} required placeholder="Min 8 characters" />
                    </div>
                  </div>
                </div>
              </div>
              {error && <div style={{ marginTop: "12px", fontSize: "12px", color: "#dc2626" }}>{error}</div>}
              <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
                <button type="button" onClick={() => setShowNew(false)} style={{ flex: 1, height: "36px", background: "#f5f5f5", border: "none", borderRadius: "8px", fontSize: "13px", cursor: "pointer" }}>Cancel</button>
                <button type="submit" disabled={saving} style={{ flex: 2, height: "36px", background: "#5266eb", color: "#fff", border: "none", borderRadius: "8px", fontSize: "13px", fontWeight: 600, cursor: "pointer", opacity: saving ? 0.7 : 1 }}>
                  {saving ? "Creating…" : "Create Tenant"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

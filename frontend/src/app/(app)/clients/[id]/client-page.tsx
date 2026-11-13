"use client";

import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, Building2, FileText, Receipt,
  Phone, Mail, MapPin, Calendar, AlertCircle, Loader2,
  Plug, CheckCircle, Wifi, WifiOff
} from "lucide-react";
import {
  getClientById, getClientDocuments, getClientVouchers,
  approveVoucher, updateTallyMapping, testTallyConnection,
  type Client, type Document, type Voucher
} from "@/lib/api";

type Tab = "overview" | "documents" | "vouchers" | "tally";

const statusVariant: Record<string, "success" | "warning" | "default"> = {
  active: "success", pending: "warning", inactive: "default",
};

const docStatusVariant: Record<string, "success" | "warning" | "default"> = {
  verified: "success", review: "warning", pending: "default",
};

const voucherStatusVariant: Record<string, "success" | "warning" | "danger" | "default"> = {
  approved: "success", pending: "warning", rejected: "danger",
};

function InfoRow({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "11px", color: "#a3a3a3", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
      <span style={{ fontSize: "13px", color: value ? "#0a0a0a" : "#d4d4d4", fontFamily: mono ? "monospace" : undefined }}>
        {value || "—"}
      </span>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px" }}>
      <AlertCircle size={14} color="#dc2626" />
      <span style={{ fontSize: "13px", color: "#dc2626" }}>{message}</span>
    </div>
  );
}

function ClientDetailInner() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [tab, setTab] = useState<Tab>("overview");
  const [client, setClient] = useState<Client | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [clientError, setClientError] = useState("");
  const [docsError, setDocsError] = useState("");
  const [vouchersError, setVouchersError] = useState("");
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(false);
  const [vouchersLoading, setVouchersLoading] = useState(false);

  // Tally mapping state
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [tallyCompany, setTallyCompany] = useState("");
  const [tallyEduMode, setTallyEduMode] = useState(false);
  const [tallySaving, setTallySaving] = useState(false);
  const [tallySaved, setTallySaved] = useState(false);
  const [tallyTesting, setTallyTesting] = useState(false);
  const [tallyTestResult, setTallyTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [tallyError, setTallyError] = useState("");

  useEffect(() => {
    setLoading(true);
    getClientById(id)
      .then(c => {
        setClient(c);
        if (c.tally_host) setTallyHost(c.tally_host);
        if (c.tally_port) setTallyPort(String(c.tally_port));
        if (c.tally_company) setTallyCompany(c.tally_company);
        if (c.tally_edu_mode) setTallyEduMode(c.tally_edu_mode);
      })
      .catch(e => setClientError(e.message || "Failed to load client"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSaveTally() {
    if (!tallyCompany.trim()) { setTallyError("Company name is required."); return; }
    setTallyError(""); setTallySaving(true);
    try {
      const updated = await updateTallyMapping(id, {
        tally_host: tallyHost.trim() || "localhost",
        tally_port: parseInt(tallyPort) || 9000,
        tally_company: tallyCompany.trim(),
        tally_edu_mode: tallyEduMode,
      });
      setClient(updated);
      setTallySaved(true);
      setTimeout(() => setTallySaved(false), 3000);
    } catch (e: unknown) {
      setTallyError(e instanceof Error ? e.message : "Failed to save Tally mapping.");
    } finally {
      setTallySaving(false);
    }
  }

  async function handleTestTally() {
    setTallyError(""); setTallyTestResult(null); setTallyTesting(true);
    try {
      const res = await testTallyConnection(id);
      if (res.connected) {
        const companies = res.company_list?.length ? ` Companies: ${res.company_list.join(", ")}` : "";
        setTallyTestResult({ ok: true, message: `Connected to Tally successfully.${companies}` });
      } else {
        setTallyTestResult({ ok: false, message: res.error || "Connection failed." });
      }
    } catch (e: unknown) {
      setTallyTestResult({ ok: false, message: e instanceof Error ? e.message : "Could not reach Tally." });
    } finally {
      setTallyTesting(false);
    }
  }

  useEffect(() => {
    if (tab === "documents") {
      setDocsLoading(true);
      getClientDocuments(id)
        .then(setDocuments)
        .catch(e => setDocsError(e.message || "Failed to load documents"))
        .finally(() => setDocsLoading(false));
    }
  }, [tab, id]);

  useEffect(() => {
    if (tab === "vouchers") {
      setVouchersLoading(true);
      getClientVouchers(id)
        .then(setVouchers)
        .catch(e => setVouchersError(e.message || "Failed to load vouchers"))
        .finally(() => setVouchersLoading(false));
    }
  }, [tab, id]);

  async function handleApprove(vid: string) {
    try {
      const updated = await approveVoucher(vid);
      setVouchers(prev => prev.map(v => v.id === vid ? updated : v));
    } catch {
      setVouchers(prev => prev.map(v => v.id === vid ? { ...v, status: "approved" as const } : v));
    }
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "Overview", icon: <Building2 size={13} /> },
    { key: "documents", label: "Documents", icon: <FileText size={13} /> },
    { key: "vouchers", label: "Vouchers", icon: <Receipt size={13} /> },
    { key: "tally", label: "Tally", icon: <Plug size={13} /> },
  ];

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#fafafa", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Loader2 size={20} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (clientError) {
    return (
      <div style={{ minHeight: "100vh", background: "#fafafa" }}>
        <Topbar title="Client Detail" />
        <div style={{ padding: "24px 28px" }}>
          <button onClick={() => router.back()} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#525252", background: "none", border: "none", cursor: "pointer", padding: 0, marginBottom: "16px" }}>
            <ArrowLeft size={14} /> Back to Clients
          </button>
          <ErrorBox message={clientError} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title={client?.name ?? "Client Detail"}
        subtitle={client?.trn ? `TRN: ${client.trn}` : undefined}
        actions={
          client && (
            <Badge variant={statusVariant[client.status] ?? "default"}>
              {client.status}
            </Badge>
          )
        }
      />

      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>

        {/* Back */}
        <button
          onClick={() => router.push("/clients")}
          style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#525252", background: "none", border: "none", cursor: "pointer", padding: 0, width: "fit-content" }}
          onMouseEnter={e => (e.currentTarget.style.color = "#0a0a0a")}
          onMouseLeave={e => (e.currentTarget.style.color = "#525252")}
        >
          <ArrowLeft size={14} /> Back to Clients
        </button>

        {/* Tabs */}
        <div style={{ display: "flex", gap: "2px", background: "#f0f0f0", padding: "3px", borderRadius: "10px", width: "fit-content" }}>
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                display: "flex", alignItems: "center", gap: "5px",
                padding: "6px 14px", borderRadius: "7px", border: "none", cursor: "pointer",
                fontSize: "12.5px", fontWeight: tab === t.key ? 600 : 400,
                color: tab === t.key ? "#0a0a0a" : "#737373",
                background: tab === t.key ? "#ffffff" : "transparent",
                boxShadow: tab === t.key ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                transition: "all 0.15s",
                fontFamily: "var(--font-family-sans)",
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* ── OVERVIEW TAB ── */}
        {tab === "overview" && client && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>

            {/* Company Info */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", paddingBottom: "12px", borderBottom: "1px solid #ebebeb" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "#eef0fd", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Building2 size={16} color="#5266eb" />
                </div>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Company Information</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <InfoRow label="Legal Name" value={client.name} />
                <InfoRow label="TRN" value={client.trn} mono />
                <InfoRow label="Entity Type" value={client.type} />
                <InfoRow label="Status" value={client.status} />
                <InfoRow label="Industry" value={client.industry} />
                <InfoRow label="VAT Period" value={client.vatPeriod} />
                <InfoRow label="Registration Date" value={client.registrationDate} />
                <InfoRow label="Last Activity" value={client.lastActivity} />
              </div>
            </div>

            {/* Contact Info */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", paddingBottom: "12px", borderBottom: "1px solid #ebebeb" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "#f0fdf4", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Mail size={16} color="#059669" />
                </div>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Contact Details</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "28px", height: "28px", borderRadius: "7px", background: "#f5f5f5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <Mail size={13} color="#737373" />
                  </div>
                  <div>
                    <p style={{ fontSize: "11px", color: "#a3a3a3", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Email</p>
                    <p style={{ fontSize: "13px", color: client.email ? "#0a0a0a" : "#d4d4d4" }}>{client.email || "—"}</p>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "28px", height: "28px", borderRadius: "7px", background: "#f5f5f5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <Phone size={13} color="#737373" />
                  </div>
                  <div>
                    <p style={{ fontSize: "11px", color: "#a3a3a3", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Phone</p>
                    <p style={{ fontSize: "13px", color: client.phone ? "#0a0a0a" : "#d4d4d4" }}>{client.phone || "—"}</p>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "28px", height: "28px", borderRadius: "7px", background: "#f5f5f5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <MapPin size={13} color="#737373" />
                  </div>
                  <div>
                    <p style={{ fontSize: "11px", color: "#a3a3a3", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Address</p>
                    <p style={{ fontSize: "13px", color: client.address ? "#0a0a0a" : "#d4d4d4" }}>{client.address || "—"}</p>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "28px", height: "28px", borderRadius: "7px", background: "#f5f5f5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <Calendar size={13} color="#737373" />
                  </div>
                  <div>
                    <p style={{ fontSize: "11px", color: "#a3a3a3", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Contact Person</p>
                    <p style={{ fontSize: "13px", color: client.contactPerson ? "#0a0a0a" : "#d4d4d4" }}>{client.contactPerson || "—"}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats row */}
            <div style={{ gridColumn: "span 2", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
              {[
                { label: "Total Documents", value: client.docs?.toString() ?? "0", color: "#5266eb", bg: "#eef0fd" },
                { label: "Pending Vouchers", value: "—", color: "#b45309", bg: "#fef3c7" },
                { label: "VAT Status", value: "Up to date", color: "#059669", bg: "#f0fdf4" },
              ].map(stat => (
                <div key={stat.label} style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "16px 20px" }}>
                  <p style={{ fontSize: "11px", color: "#a3a3a3", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>{stat.label}</p>
                  <p style={{ fontSize: "22px", fontWeight: 700, color: stat.color }}>{stat.value}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── DOCUMENTS TAB ── */}
        {tab === "documents" && (
          <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #ebebeb" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Documents</span>
              <Button size="sm">Upload Document</Button>
            </div>

            {docsLoading && (
              <div style={{ padding: "40px", display: "flex", justifyContent: "center" }}>
                <Loader2 size={18} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
                <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
              </div>
            )}

            {docsError && !docsLoading && (
              <div style={{ padding: "16px" }}>
                <ErrorBox message={docsError} />
              </div>
            )}

            {!docsLoading && !docsError && documents.length === 0 && (
              <div style={{ padding: "48px 20px", textAlign: "center" }}>
                <FileText size={32} color="#d4d4d4" style={{ margin: "0 auto 10px" }} />
                <p style={{ fontSize: "13px", color: "#a3a3a3" }}>No documents uploaded for this client yet.</p>
              </div>
            )}

            {!docsLoading && !docsError && documents.length > 0 && (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                    {["Document", "Type", "AI Confidence", "Status", "Uploaded", ""].map(h => (
                      <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc, i) => (
                    <tr key={doc.id} style={{ borderBottom: i < documents.length - 1 ? "1px solid #ebebeb" : "none" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ padding: "12px 20px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <FileText size={14} color="#a3a3a3" />
                          <span style={{ fontSize: "13px", fontWeight: 500, color: "#0a0a0a", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.file_name ?? doc.name ?? "—"}</span>
                        </div>
                      </td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", whiteSpace: "nowrap" }}>{doc.document_type ?? doc.type ?? "—"}</td>
                      <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                        {(doc.confidence_score ?? doc.confidence ?? 0) > 0 ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <div style={{ width: "56px", height: "5px", borderRadius: "9999px", background: "#f0f0f0" }}>
                              <div style={{ width: `${doc.confidence_score ?? doc.confidence}%`, height: "100%", borderRadius: "9999px", background: "#059669" }} />
                            </div>
                            <span style={{ fontSize: "11px", color: "#a3a3a3" }}>{doc.confidence_score ?? doc.confidence}%</span>
                          </div>
                        ) : <span style={{ fontSize: "12px", color: "#a3a3a3" }}>—</span>}
                      </td>
                      <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}><Badge variant={docStatusVariant[doc.status] ?? "default"}>{doc.status}</Badge></td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", color: "#a3a3a3", whiteSpace: "nowrap" }}>
                        {doc.created_at ? new Date(doc.created_at).toLocaleDateString("en-AE", { day: "numeric", month: "short", year: "numeric" }) : doc.uploaded ?? "—"}
                      </td>
                      <td style={{ padding: "12px 24px 12px 20px", textAlign: "right" }}><Button variant="ghost" size="sm">View</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* ── VOUCHERS TAB ── */}
        {tab === "vouchers" && (
          <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #ebebeb" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Vouchers</span>
              <Button size="sm">+ New Voucher</Button>
            </div>

            {vouchersLoading && (
              <div style={{ padding: "40px", display: "flex", justifyContent: "center" }}>
                <Loader2 size={18} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
                <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
              </div>
            )}

            {vouchersError && !vouchersLoading && (
              <div style={{ padding: "16px" }}>
                <ErrorBox message={vouchersError} />
              </div>
            )}

            {!vouchersLoading && !vouchersError && vouchers.length === 0 && (
              <div style={{ padding: "48px 20px", textAlign: "center" }}>
                <Receipt size={32} color="#d4d4d4" style={{ margin: "0 auto 10px" }} />
                <p style={{ fontSize: "13px", color: "#a3a3a3" }}>No vouchers for this client yet.</p>
              </div>
            )}

            {!vouchersLoading && !vouchersError && vouchers.length > 0 && (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                    {["ID", "Description", "Amount", "Type", "Status", ""].map(h => (
                      <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {vouchers.map((v, i) => (
                    <tr key={v.id} style={{ borderBottom: i < vouchers.length - 1 ? "1px solid #ebebeb" : "none" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ padding: "12px 20px", fontSize: "11px", fontFamily: "monospace", color: "#a3a3a3", whiteSpace: "nowrap" }}>{v.id}</td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", maxWidth: "240px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v.description}</td>
                      <td style={{ padding: "12px 20px", fontSize: "13px", fontWeight: 600, color: "#0a0a0a", whiteSpace: "nowrap" }}>{v.amount}</td>
                      <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                        <Badge variant={v.type === "Income" ? "accent" : "default"}>{v.type}</Badge>
                      </td>
                      <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                        <Badge variant={voucherStatusVariant[v.status]}>{v.status}</Badge>
                      </td>
                      <td style={{ padding: "12px 24px 12px 20px", textAlign: "right" }}>
                        {v.status === "pending"
                          ? <Button size="sm" onClick={() => handleApprove(v.id)}>Approve</Button>
                          : <Button variant="ghost" size="sm">View</Button>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
        {/* ── TALLY TAB ── */}
        {tab === "tally" && (
          <div style={{ maxWidth: "560px", display: "flex", flexDirection: "column", gap: "16px" }}>

            {/* Status banner */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "16px 20px", display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={{ width: "36px", height: "36px", borderRadius: "9px", background: client?.tally_connected ? "#d1fae5" : "#f5f5f5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                {client?.tally_connected
                  ? <Wifi size={16} color="#059669" />
                  : <WifiOff size={16} color="#a3a3a3" />}
              </div>
              <div>
                <p style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a", margin: 0 }}>
                  {client?.tally_connected ? `Connected — ${client.tally_company}` : "Not connected to Tally"}
                </p>
                <p style={{ fontSize: "12px", color: "#a3a3a3", margin: "2px 0 0" }}>
                  {client?.tally_connected
                    ? `${client.tally_host || "localhost"}:${client.tally_port || 9000}`
                    : "Map this client to a Tally company to enable voucher posting."}
                </p>
              </div>
              {client?.tally_last_sync && (
                <span style={{ marginLeft: "auto", fontSize: "11px", color: "#a3a3a3" }}>
                  Last sync: {new Date(client.tally_last_sync).toLocaleDateString("en-AE")}
                </span>
              )}
            </div>

            {/* Connector Credentials */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
              <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Connector Credentials</span>
                <a href={`/settings/tally?clientId=${id}`}
                  style={{ fontSize: "12px", color: "#5266eb", fontWeight: 500, textDecoration: "none" }}
                  onMouseEnter={e => (e.currentTarget.style.textDecoration = "underline")}
                  onMouseLeave={e => (e.currentTarget.style.textDecoration = "none")}
                >
                  Manage →
                </a>
              </div>
              <div style={{ padding: "14px 20px", display: "flex", flexDirection: "column", gap: "10px" }}>
                <p style={{ fontSize: "12px", color: "#737373", margin: 0 }}>
                  Use these credentials when running <strong>ClearbookConnector.exe</strong> on the Tally machine.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#525252" }}>Client ID</label>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <div style={{ flex: 1, height: "32px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "12px", background: "#f5f5f5", fontFamily: "monospace", display: "flex", alignItems: "center", overflow: "hidden", whiteSpace: "nowrap" as const }}>
                      {id}
                    </div>
                    <button onClick={() => navigator.clipboard.writeText(id)}
                      style={{ flexShrink: 0, width: "32px", height: "32px", borderRadius: "7px", border: "1px solid #e0e0e0", background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#737373" }}
                      title="Copy Client ID">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                  </div>
                </div>
                <p style={{ fontSize: "11.5px", color: "#a3a3a3", margin: 0 }}>
                  Click <strong>Manage →</strong> above to generate or view the API Key.
                </p>
              </div>
            </div>

            {/* Config form */}
            <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden" }}>
              <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb" }}>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Tally Connection</span>
              </div>
              <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>

                <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
                  <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#525252" }}>
                    Tally Company Name <span style={{ color: "#dc2626" }}>*</span>
                  </label>
                  <input value={tallyCompany} onChange={e => setTallyCompany(e.target.value)}
                    placeholder="e.g. ABC Trading LLC"
                    style={{ height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", outline: "none", fontFamily: "var(--font-family-sans)" }}
                    onFocus={e => (e.target.style.borderColor = "#5266eb")}
                    onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                  />
                  <p style={{ fontSize: "11px", color: "#a3a3a3", margin: 0 }}>Must match the company name exactly as it appears in Tally</p>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
                    <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#525252" }}>Host</label>
                    <input value={tallyHost} onChange={e => setTallyHost(e.target.value)} placeholder="localhost"
                      style={{ height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a", background: "#fff", outline: "none", fontFamily: "var(--font-family-sans)" }}
                      onFocus={e => (e.target.style.borderColor = "#5266eb")}
                      onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                    />
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
                    <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#525252" }}>Port</label>
                    <input type="number" value={tallyPort} onChange={e => setTallyPort(e.target.value)} placeholder="9000"
                      style={{ height: "34px", padding: "0 10px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "13px", fontFamily: "monospace", color: "#0a0a0a", background: "#fff", outline: "none" }}
                      onFocus={e => (e.target.style.borderColor = "#5266eb")}
                      onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                    />
                  </div>
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                  <input type="checkbox" checked={tallyEduMode} onChange={e => setTallyEduMode(e.target.checked)} style={{ width: "14px", height: "14px", cursor: "pointer" }} />
                  <span style={{ fontSize: "12.5px", color: "#525252" }}>EDU mode (round dates to 1st of month)</span>
                </label>

                {tallyError && (
                  <p style={{ fontSize: "12px", color: "#dc2626", background: "#fef2f2", border: "1px solid #fca5a5", padding: "8px 12px", borderRadius: "7px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <AlertCircle size={12} /> {tallyError}
                  </p>
                )}

                {tallyTestResult && (
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", padding: "10px 14px", background: tallyTestResult.ok ? "#d1fae5" : "#fef2f2", border: `1px solid ${tallyTestResult.ok ? "#6ee7b7" : "#fca5a5"}`, borderRadius: "8px" }}>
                    {tallyTestResult.ok ? <CheckCircle size={13} color="#059669" style={{ flexShrink: 0 }} /> : <AlertCircle size={13} color="#dc2626" style={{ flexShrink: 0 }} />}
                    <span style={{ fontSize: "12px", color: tallyTestResult.ok ? "#059669" : "#dc2626" }}>{tallyTestResult.message}</span>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid #ebebeb" }}>
                <button onClick={handleTestTally} disabled={tallyTesting}
                  style={{ height: "32px", padding: "0 14px", background: "none", border: "1px solid #e0e0e0", borderRadius: "7px", fontSize: "12.5px", color: "#525252", cursor: tallyTesting ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
                  onMouseEnter={e => { if (!tallyTesting) e.currentTarget.style.background = "#f5f5f5"; }}
                  onMouseLeave={e => { if (!tallyTesting) e.currentTarget.style.background = "none"; }}
                >
                  {tallyTesting && <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />}
                  {tallyTesting ? "Testing…" : "Test Connection"}
                </button>
                <button onClick={handleSaveTally} disabled={tallySaving}
                  style={{ height: "32px", padding: "0 16px", background: tallySaving ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "12.5px", fontWeight: 600, cursor: tallySaving ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
                  onMouseEnter={e => { if (!tallySaving) e.currentTarget.style.background = "#4254d4"; }}
                  onMouseLeave={e => { if (!tallySaving) e.currentTarget.style.background = "#5266eb"; }}
                >
                  {tallySaving && <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />}
                  {tallySaved && <CheckCircle size={12} />}
                  {tallySaving ? "Saving…" : tallySaved ? "Saved!" : "Save Mapping"}
                </button>
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}

export default function ClientDetailPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "100vh", background: "#fafafa", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Loader2 size={20} color="#5266eb" style={{ animation: "spin 1s linear infinite" }} />
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    }>
      <ClientDetailInner />
    </Suspense>
  );
}
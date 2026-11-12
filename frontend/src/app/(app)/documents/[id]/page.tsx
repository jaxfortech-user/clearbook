"use client";



import { useEffect, useState, Suspense } from "react";
import { useRouter, useParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, FileText, CheckCircle, AlertCircle, Clock,
  ChevronRight, Loader2, Eye, FilePlus, ThumbsUp
} from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────────────────

interface LineItem {
  date?: string;
  description?: string;
  amount?: number | string;
  debit?: number | string;
  credit?: number | string;
  balance?: number | string;
  reference?: string;
  [key: string]: unknown;
}

interface ExtractedData {
  document_type?: string;
  vendor_name?: string;
  vendor_trn?: string;
  client_name?: string;
  invoice_number?: string;
  invoice_date?: string;
  due_date?: string;
  total_amount?: number | string;
  vat_amount?: number | string;
  net_amount?: number | string;
  currency?: string;
  bank_name?: string;
  account_number?: string;
  account_holder?: string;
  opening_balance?: number | string;
  closing_balance?: number | string;
  period_start?: string;
  period_end?: string;
  line_items?: LineItem[];
  transactions?: LineItem[];
  notes?: string;
  raw_text?: string;
  [key: string]: unknown;
}

interface DocumentDetail {
  id: string;
  file_name?: string;
  name?: string;
  document_type?: string;
  type?: string;
  status: string;
  confidence_score?: number;
  confidence?: number;
  client_id?: string;
  created_at?: string;
  uploaded?: string;
  extracted_data?: ExtractedData;
  file_url?: string;
}

interface VoucherCreated {
  id: string;
  voucher_number?: string;
  status: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(url: string, opts?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("clearbook_token") : null;
  const r = await fetch(url, {
    ...opts,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts?.headers ?? {}),
    },
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${r.status}: ${text || r.statusText}`);
  }
  return r.json() as Promise<T>;
}

function fmt(val: unknown): string {
  if (val == null || val === "") return "—";
  if (typeof val === "number") return val.toLocaleString();
  return String(val);
}

function statusVariant(s: string): "success" | "warning" | "default" {
  if (["verified", "extracted", "voucher_created", "approved"].includes(s)) return "success";
  if (["processing", "needs_review", "review", "pending_approval"].includes(s)) return "warning";
  return "default";
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function FieldRow({ label, value }: { label: string; value: unknown }) {
  return (
    <div style={{ display: "flex", padding: "8px 0", borderBottom: "1px solid #f5f5f5" }}>
      <span style={{ width: "180px", flexShrink: 0, fontSize: "12px", color: "#a3a3a3", fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: "13px", color: "#0a0a0a", fontWeight: 500 }}>{fmt(value)}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
      <div style={{ padding: "12px 20px", borderBottom: "1px solid #ebebeb", background: "#fafafa" }}>
        <span style={{ fontSize: "12px", fontWeight: 600, color: "#525252", textTransform: "uppercase", letterSpacing: "0.06em" }}>{title}</span>
      </div>
      <div style={{ padding: "4px 20px 12px" }}>
        {children}
      </div>
    </div>
  );
}

function LineItemsTable({ items }: { items: LineItem[] }) {
  if (!items?.length) return <p style={{ fontSize: "12px", color: "#a3a3a3", padding: "12px 0" }}>No line items</p>;

  const keys = Array.from(new Set(items.flatMap(i => Object.keys(i)))).filter(k => k !== "reference");

  return (
    <div style={{ overflowX: "auto", marginTop: "8px" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
        <thead>
          <tr style={{ background: "#fafafa" }}>
            {keys.map(k => (
              <th key={k} style={{ padding: "8px 10px", textAlign: "left", fontWeight: 600, color: "#a3a3a3", textTransform: "capitalize", borderBottom: "1px solid #ebebeb", whiteSpace: "nowrap" }}>
                {k.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
              {keys.map(k => (
                <td key={k} style={{ padding: "8px 10px", color: "#0a0a0a" }}>{fmt(item[k])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

function DocumentDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [voucher, setVoucher] = useState<VoucherCreated | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]);
  const [assigningClient, setAssigningClient] = useState(false);
  const [showClientPicker, setShowClientPicker] = useState(false);

  useEffect(() => {
    fetchJson<{ id: string; name: string }[]>(`${API}/api/v1/clients/`)
      .then(setClients).catch(() => {});
  }, []);

  const handleAssignClient = async (clientId: string) => {
    if (!doc) return;
    setAssigningClient(true);
    try {
      await fetchJson(`${API}/api/v1/documents/${doc.id}/assign-client`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId }),
      });
      setDoc({ ...doc, client_id: clientId });
      setShowClientPicker(false);
    } catch (e: unknown) {
      alert("Failed to assign client: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setAssigningClient(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchJson<DocumentDetail>(`${API}/api/v1/documents/${id}`)
      .then(d => { setDoc(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [id]);

  const handleCreateVoucher = async () => {
    if (!doc) return;
    setCreating(true);
    setCreateError(null);
    try {
      const v = await fetchJson<VoucherCreated>(`${API}/api/v1/documents/${doc.id}/create-voucher`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      setVoucher(v);
      // Refresh doc to reflect voucher_created status
      const updated = await fetchJson<DocumentDetail>(`${API}/api/v1/documents/${id}`);
      setDoc(updated);
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : "Failed to create voucher");
    } finally {
      setCreating(false);
    }
  };

  const docName = doc?.file_name ?? doc?.name ?? "Document";
  const docType = doc?.document_type ?? doc?.type ?? "Unknown";
  const confidence = doc?.confidence_score ?? doc?.confidence ?? 0;
  const extracted = doc?.extracted_data;
  const transactions = extracted?.transactions ?? extracted?.line_items ?? [];

  const canCreateVoucher = doc && doc.client_id && !["voucher_created", "approved"].includes(doc.status) && ["extracted", "needs_review", "verified"].includes(doc.status);
  const noClientWarning = doc && !doc.client_id && ["extracted", "needs_review", "verified"].includes(doc.status);

  // ── render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#fafafa" }}>
        <Topbar title="Document" subtitle="Loading…" />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 20px", gap: "12px" }}>
          <Loader2 size={18} color="#5266eb" style={{ animation: "spin 0.7s linear infinite" }} />
          <span style={{ fontSize: "14px", color: "#a3a3a3" }}>Loading document…</span>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div style={{ minHeight: "100vh", background: "#fafafa" }}>
        <Topbar title="Document" subtitle="Error" />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 20px", gap: "12px" }}>
          <AlertCircle size={24} color="#ef4444" />
          <span style={{ fontSize: "14px", color: "#525252" }}>{error ?? "Document not found"}</span>
          <Button variant="outline" size="sm" onClick={() => router.back()}>Go back</Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title={docName}
        subtitle={docType.replace(/_/g, " ")}
        actions={
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            {doc.file_url && (
              <Button variant="outline" size="sm" onClick={() => window.open(doc.file_url, "_blank")}
                style={{ display: "flex", gap: "5px", alignItems: "center" }}>
                <Eye size={12} /> Preview
              </Button>
            )}
            {noClientWarning && (
              <Button size="sm" variant="outline" onClick={() => setShowClientPicker(true)} style={{ display: "flex", gap: "5px", alignItems: "center" }}>
                <FilePlus size={12} /> Assign Client
              </Button>
            {canCreateVoucher && (
              <Button
                size="sm"
                disabled={creating}
                onClick={handleCreateVoucher}
                style={{ display: "flex", gap: "5px", alignItems: "center" }}
              >
                {creating ? <Loader2 size={12} style={{ animation: "spin 0.7s linear infinite" }} /> : <FilePlus size={12} />}
                {creating ? "Creating…" : "Create Voucher"}
              </Button>
            )}
            {voucher && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => router.push(`/vouchers/${voucher.id}`)}
                style={{ display: "flex", gap: "5px", alignItems: "center" }}
              >
                <ChevronRight size={12} /> View Voucher
              </Button>
            )}
          </div>
        }
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px", maxWidth: "900px" }}>

        {/* Back */}
        <button
          onClick={() => router.back()}
          style={{ display: "flex", alignItems: "center", gap: "5px", background: "none", border: "none", cursor: "pointer", fontSize: "12px", color: "#a3a3a3", padding: 0, width: "fit-content" }}
          onMouseEnter={e => (e.currentTarget.style.color = "#525252")}
          onMouseLeave={e => (e.currentTarget.style.color = "#a3a3a3")}
        >
          <ArrowLeft size={12} /> Back to Documents
        </button>

        {/* Success banner */}
        {voucher && (
          <div style={{ padding: "12px 16px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
            <CheckCircle size={15} color="#059669" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: "13px", color: "#059669", fontWeight: 500 }}>
              Voucher {voucher.voucher_number ?? voucher.id} created successfully
            </span>
            <button
              onClick={() => router.push(`/vouchers/${voucher.id}`)}
              style={{ marginLeft: "auto", fontSize: "12px", color: "#059669", background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px" }}
            >
              Review & Approve <ChevronRight size={11} />
            </button>
          </div>
        )}

        {/* Error banner */}
        {createError && (
          <div style={{ padding: "12px 16px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
            <AlertCircle size={15} color="#ef4444" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: "13px", color: "#ef4444" }}>{createError}</span>
          </div>
        )}

        {/* Document meta */}
        <Section title="Document Info">
          <FieldRow label="File Name" value={docName} />
          <FieldRow label="Document Type" value={docType.replace(/_/g, " ")} />
          <FieldRow label="Status" value={doc.status.replace(/_/g, " ")} />
          <FieldRow label="AI Confidence" value={confidence > 0 ? `${(confidence * 100).toFixed(0)}%` : "Processing…"} />
          <FieldRow label="Uploaded" value={doc.created_at ?? doc.uploaded ? new Date((doc.created_at ?? doc.uploaded)!).toLocaleString("en-AE") : "—"} />
        </Section>

        {/* Extracted fields */}
        {extracted && (
          <Section title="Extracted Data">
            {extracted.vendor_name && <FieldRow label="Vendor" value={extracted.vendor_name} />}
            {extracted.vendor_trn && <FieldRow label="Vendor TRN" value={extracted.vendor_trn} />}
            {extracted.client_name && <FieldRow label="Client Name" value={extracted.client_name} />}
            {extracted.invoice_number && <FieldRow label="Invoice Number" value={extracted.invoice_number} />}
            {extracted.invoice_date && <FieldRow label="Invoice Date" value={extracted.invoice_date} />}
            {extracted.due_date && <FieldRow label="Due Date" value={extracted.due_date} />}
            {extracted.bank_name && <FieldRow label="Bank" value={extracted.bank_name} />}
            {extracted.account_number && <FieldRow label="Account Number" value={extracted.account_number} />}
            {extracted.account_holder && <FieldRow label="Account Holder" value={extracted.account_holder} />}
            {extracted.period_start && <FieldRow label="Period Start" value={extracted.period_start} />}
            {extracted.period_end && <FieldRow label="Period End" value={extracted.period_end} />}
            {(extracted.opening_balance != null) && <FieldRow label="Opening Balance" value={`${extracted.currency ?? "AED"} ${fmt(extracted.opening_balance)}`} />}
            {(extracted.closing_balance != null) && <FieldRow label="Closing Balance" value={`${extracted.currency ?? "AED"} ${fmt(extracted.closing_balance)}`} />}
            {(extracted.net_amount != null) && <FieldRow label="Net Amount" value={`${extracted.currency ?? "AED"} ${fmt(extracted.net_amount)}`} />}
            {(extracted.vat_amount != null) && <FieldRow label="VAT Amount" value={`${extracted.currency ?? "AED"} ${fmt(extracted.vat_amount)}`} />}
            {(extracted.total_amount != null) && <FieldRow label="Total Amount" value={`${extracted.currency ?? "AED"} ${fmt(extracted.total_amount)}`} />}
            {extracted.notes && <FieldRow label="Notes" value={extracted.notes} />}
          </Section>
        )}

        {/* Line items / transactions */}
        {transactions.length > 0 && (
          <Section title={extracted?.transactions ? "Transactions" : "Line Items"}>
            <LineItemsTable items={transactions} />
          </Section>
        )}

        {/* Raw text fallback */}
        {extracted?.raw_text && !extracted.vendor_name && !extracted.bank_name && (
          <Section title="Extracted Text">
            <pre style={{ fontSize: "11px", color: "#525252", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: "300px", overflowY: "auto", margin: "8px 0 0", lineHeight: 1.6 }}>
              {extracted.raw_text}
            </pre>
          </Section>
        )}

        {/* CTA if no extracted data */}
        {!extracted && (
          <div style={{ padding: "32px 20px", background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
            {doc.status === "processing" || doc.status === "uploaded" ? (
              <>
                <Clock size={22} color="#b45309" />
                <p style={{ fontSize: "13px", fontWeight: 500, color: "#525252", margin: 0 }}>Extraction in progress</p>
                <p style={{ fontSize: "12px", color: "#a3a3a3", margin: 0 }}>AI is processing this document. Refresh in a few seconds.</p>
                <Button variant="outline" size="sm" onClick={() => window.location.reload()}>Refresh</Button>
              </>
            ) : doc.status === "failed" ? (
              <>
                <AlertCircle size={22} color="#ef4444" />
                <p style={{ fontSize: "13px", fontWeight: 500, color: "#525252", margin: 0 }}>Extraction failed</p>
                <p style={{ fontSize: "12px", color: "#a3a3a3", margin: 0 }}>The AI could not extract data from this document.</p>
              </>
            ) : (
              <>
                <FileText size={22} color="#a3a3a3" />
                <p style={{ fontSize: "13px", fontWeight: 500, color: "#525252", margin: 0 }}>No extracted data</p>
              </>
            )}
          </div>
        )}

        {/* Approve shortcut (if voucher already exists for this doc) */}
        {doc.status === "voucher_created" && !voucher && (
          <div style={{ padding: "14px 18px", background: "#eef0fd", border: "1px solid #c7d2fe", borderRadius: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
            <ThumbsUp size={15} color="#5266eb" />
            <span style={{ fontSize: "13px", color: "#5266eb", fontWeight: 500 }}>Voucher already created for this document</span>
            <Button
              variant="outline" size="sm"
              style={{ marginLeft: "auto" }}
              onClick={() => router.push("/vouchers")}
            >
              Go to Vouchers
            </Button>
          </div>
        )}

      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      {showClientPicker && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div style={{ background: "#fff", borderRadius: "12px", padding: "24px", minWidth: "320px", boxShadow: "0 8px 32px rgba(0,0,0,0.12)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: "14px", fontWeight: 600 }}>Assign Client to Document</h3>
            {clients.length === 0 && <p style={{ fontSize: "13px", color: "#a3a3a3" }}>No clients found.</p>}
            {clients.map(c => (
              <button key={c.id} onClick={() => handleAssignClient(c.id)}
                disabled={assigningClient}
                style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 12px", borderRadius: "8px", border: "1px solid #ebebeb", marginBottom: "8px", cursor: "pointer", fontSize: "13px", background: "#fafafa" }}>
                {c.name}
              </button>
            ))}
            <button onClick={() => setShowClientPicker(false)} style={{ marginTop: "8px", padding: "8px 16px", borderRadius: "8px", border: "1px solid #ebebeb", cursor: "pointer", fontSize: "13px" }}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DocumentDetailPageWrapper() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "100vh", background: "#fafafa", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}>
        <div style={{ width: "18px", height: "18px", border: "2px solid #ebebeb", borderTopColor: "#5266eb", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
        <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Loading…</span>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    }>
      <DocumentDetailPage />
    </Suspense>
  );
}
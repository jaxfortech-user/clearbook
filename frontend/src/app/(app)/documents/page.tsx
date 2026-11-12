"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Upload, FileText, CheckCircle, Clock, AlertCircle, ChevronDown } from "lucide-react";
import { getDocuments, getClients, uploadDocument, type Document, type Client } from "@/lib/api";

const statusVariant: Record<string, "success" | "warning" | "default"> = {
  verified: "success", review: "warning", pending: "default",
  uploaded: "default", processing: "warning", failed: "default",
  extracted: "success", needs_review: "warning", voucher_created: "success",
};

function docName(doc: import("@/lib/api").Document) {
  return doc.file_name ?? doc.name ?? "—";
}
function docType(doc: import("@/lib/api").Document) {
  return doc.document_type ?? doc.type ?? "Processing…";
}
function docConfidence(doc: import("@/lib/api").Document): number {
  return doc.confidence_score ?? doc.confidence ?? 0;
}
function docUploaded(doc: import("@/lib/api").Document) {
  const raw = doc.created_at ?? doc.uploaded;
  if (!raw) return "—";
  return new Date(raw).toLocaleDateString("en-AE", { day: "numeric", month: "short", year: "numeric" });
}

const cols = ["Document", "Client", "Type", "AI Confidence", "Status", "Uploaded", ""];

type UploadingFile = {
  id: string;
  name: string;
  progress: number;
  error?: string;
};

export default function DocumentsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [allDocuments, setAllDocuments] = useState<Document[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<UploadingFile[]>([]);
  const [clientDropdownOpen, setClientDropdownOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const docs = await getDocuments();
      setAllDocuments(docs);
      setDocuments(docs);
    } catch {
      setError("Failed to load documents. Please retry.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    getClients().then(setClients).catch(() => {});
    fetchDocuments();
  }, []);

  useEffect(() => {
    const hasPending = allDocuments.some(
      d => d.status === "uploaded" || d.status === "processing"
    );
    if (!hasPending) return;
    const timer = setInterval(() => {
      getDocuments().then(docs => {
        setAllDocuments(docs);
        setDocuments(selectedClientId ? docs.filter(d => d.client_id === selectedClientId) : docs);
      }).catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [allDocuments, selectedClientId]);

  useEffect(() => {
    if (!selectedClientId) {
      setDocuments(allDocuments);
    } else {
      setDocuments(allDocuments.filter(d => d.client_id === selectedClientId));
    }
  }, [selectedClientId, allDocuments, clients]);

  const selectedClient = clients.find(c => c.id === selectedClientId);

  const handleFiles = async (files: FileList | File[]) => {
    const fileArr = Array.from(files);
    if (fileArr.length === 0) return;

    const newUploads: UploadingFile[] = fileArr.map(f => ({
      id: Math.random().toString(36).slice(2),
      name: f.name,
      progress: 0,
    }));
    setUploading(prev => [...prev, ...newUploads]);

    for (let i = 0; i < fileArr.length; i++) {
      const file = fileArr[i];
      const uid = newUploads[i].id;

      setUploading(prev => prev.map(u => u.id === uid ? { ...u, progress: 30 } : u));

      try {
        setUploading(prev => prev.map(u => u.id === uid ? { ...u, progress: 60 } : u));
        const doc = await uploadDocument(file, selectedClientId || undefined);
        setUploading(prev => prev.map(u => u.id === uid ? { ...u, progress: 100 } : u));

        setDocuments(prev => [doc, ...prev]);
        setAllDocuments(prev => [doc, ...prev]);
        setTimeout(() => {
          setUploading(prev => prev.filter(u => u.id !== uid));
        }, 1200);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setUploading(prev => prev.map(u => u.id === uid ? { ...u, error: msg, progress: 0 } : u));
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) handleFiles(e.target.files);
    e.target.value = "";
  };

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Documents"
        subtitle={loading ? "Loading…" : `${documents.length} document${documents.length !== 1 ? "s" : ""}`}
        actions={
          <Button
            size="sm"
            style={{ display: "flex", alignItems: "center", gap: "5px" }}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={13} /> Upload
          </Button>
        }
      />

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.xlsx,.xls,.docx,.doc,.csv,.png,.jpg,.jpeg"
        style={{ display: "none" }}
        onChange={handleInputChange}
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>

        {/* Upload Zone */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>

          {/* Client Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "12px", fontWeight: 500, color: "#525252", whiteSpace: "nowrap" }}>Upload for:</span>
            <div style={{ position: "relative" }}>
              <button
                onClick={() => setClientDropdownOpen(o => !o)}
                style={{ display: "flex", alignItems: "center", gap: "6px", padding: "6px 10px", border: "1px solid #ebebeb", borderRadius: "8px", background: "#fafafa", cursor: "pointer", fontSize: "12px", color: selectedClient ? "#0a0a0a" : "#a3a3a3", fontWeight: selectedClient ? 500 : 400 }}
              >
                {selectedClient ? selectedClient.name : "Select client (optional)"}
                <ChevronDown size={12} color="#a3a3a3" />
              </button>
              {clientDropdownOpen && (
                <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, minWidth: "240px", background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "10px", boxShadow: "0 4px 16px rgba(0,0,0,0.08)", zIndex: 50, overflow: "hidden" }}>
                  <div
                    onClick={() => { setSelectedClientId(""); setClientDropdownOpen(false); }}
                    style={{ padding: "9px 14px", fontSize: "12px", color: "#a3a3a3", cursor: "pointer", borderBottom: "1px solid #ebebeb" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    No client
                  </div>
                  {clients.map(c => (
                    <div
                      key={c.id}
                      onClick={() => { setSelectedClientId(c.id); setClientDropdownOpen(false); }}
                      style={{ padding: "9px 14px", fontSize: "12px", color: "#0a0a0a", cursor: "pointer", fontWeight: c.id === selectedClientId ? 500 : 400, background: c.id === selectedClientId ? "#eef0fd" : "transparent" }}
                      onMouseEnter={e => { if (c.id !== selectedClientId) e.currentTarget.style.background = "#fafafa"; }}
                      onMouseLeave={e => { if (c.id !== selectedClientId) e.currentTarget.style.background = "transparent"; }}
                    >
                      {c.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Drop Zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{ border: `2px dashed ${dragging ? "#5266eb" : "#d4d4d4"}`, borderRadius: "10px", padding: "28px 24px", display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", cursor: "pointer", background: dragging ? "#eef0fd" : "#fafafa", transition: "all 0.15s" }}
            onMouseEnter={e => { if (!dragging) (e.currentTarget.style.borderColor = "#a3a3a3"); }}
            onMouseLeave={e => { if (!dragging) (e.currentTarget.style.borderColor = "#d4d4d4"); }}
          >
            <div style={{ width: "38px", height: "38px", borderRadius: "10px", background: "#eef0fd", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Upload size={16} color="#5266eb" />
            </div>
            <p style={{ fontSize: "13px", fontWeight: 500, color: "#0a0a0a", margin: 0 }}>Drop files here or click to browse</p>
            <p style={{ fontSize: "12px", color: "#a3a3a3", margin: 0 }}>PDF, XLSX, DOCX, CSV, Images — up to 50MB each</p>
          </div>

          {/* Upload Progress Items */}
          {uploading.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {uploading.map(u => (
                <div key={u.id} style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", background: u.error ? "#fef2f2" : "#fafafa", border: `1px solid ${u.error ? "#fecaca" : "#ebebeb"}`, borderRadius: "8px" }}>
                  <FileText size={13} color={u.error ? "#ef4444" : "#a3a3a3"} style={{ flexShrink: 0 }} />
                  <span style={{ fontSize: "12px", color: u.error ? "#ef4444" : "#0a0a0a", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {u.name}
                  </span>
                  {u.error ? (
                    <span style={{ fontSize: "11px", color: "#ef4444", display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
                      <AlertCircle size={11} /> {u.error}
                    </span>
                  ) : u.progress === 100 ? (
                    <CheckCircle size={13} color="#059669" style={{ flexShrink: 0 }} />
                  ) : (
                    <div style={{ width: "80px", height: "4px", borderRadius: "9999px", background: "#e5e5e5", overflow: "hidden", flexShrink: 0 }}>
                      <div style={{ width: `${u.progress}%`, height: "100%", borderRadius: "9999px", background: "#5266eb", transition: "width 0.4s ease" }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Documents Table */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #ebebeb" }}>
            <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>All Documents</span>
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              <span style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "11px", color: "#a3a3a3" }}><CheckCircle size={12} color="#059669" /> Verified</span>
              <span style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "11px", color: "#a3a3a3" }}><Clock size={12} color="#b45309" /> In Review</span>
            </div>
          </div>

          {loading ? (
            <div style={{ padding: "48px 20px", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}>
              <div style={{ width: "18px", height: "18px", border: "2px solid #ebebeb", borderTopColor: "#5266eb", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
              <span style={{ fontSize: "13px", color: "#a3a3a3" }}>Loading documents…</span>
            </div>
          ) : error ? (
            <div style={{ padding: "32px 20px", display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
              <AlertCircle size={20} color="#ef4444" />
              <span style={{ fontSize: "13px", color: "#525252" }}>{error}</span>
              <Button variant="outline" size="sm" onClick={() => fetchDocuments()}>Retry</Button>
            </div>
          ) : documents.length === 0 ? (
            <div style={{ padding: "48px 20px", display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
              <FileText size={28} color="#d4d4d4" />
              <p style={{ fontSize: "13px", fontWeight: 500, color: "#525252", margin: 0 }}>No documents yet</p>
              <p style={{ fontSize: "12px", color: "#a3a3a3", margin: 0 }}>Upload your first document above to get started</p>
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ebebeb" }}>
                  {cols.map(h => (
                    <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: "11px", fontWeight: 600, color: "#a3a3a3", textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {documents.map((doc, i) => (
                  <tr
                    key={doc.id}
                    style={{ borderBottom: i < documents.length - 1 ? "1px solid #ebebeb" : "none" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "#fafafa")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <FileText size={14} color="#a3a3a3" style={{ flexShrink: 0 }} />
                        <span style={{ fontSize: "13px", fontWeight: 500, color: "#0a0a0a", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{docName(doc)}</span>
                      </div>
                    </td>
                    <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", whiteSpace: "nowrap" }}>
                      {clients.find(c => c.id === doc.client_id)?.name ?? doc.client ?? "—"}
                    </td>
                    <td style={{ padding: "12px 20px", fontSize: "13px", color: "#525252", whiteSpace: "nowrap" }}>{docType(doc)}</td>
                    <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                      {docConfidence(doc) > 0 ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <div style={{ width: "56px", height: "5px", borderRadius: "9999px", background: "#f0f0f0", overflow: "hidden" }}>
                            <div style={{ width: `${docConfidence(doc) * 100}%`, height: "100%", borderRadius: "9999px", background: docConfidence(doc) >= 0.85 ? "#059669" : docConfidence(doc) >= 0.60 ? "#b45309" : "#ef4444" }} />
                          </div>
                          <span style={{ fontSize: "11px", color: "#a3a3a3" }}>{(docConfidence(doc) * 100).toFixed(0)}%</span>
                        </div>
                      ) : <span style={{ fontSize: "12px", color: "#a3a3a3" }}>Processing…</span>}
                    </td>
                    <td style={{ padding: "12px 20px", whiteSpace: "nowrap" }}>
                      <Badge variant={statusVariant[doc.status] ?? "default"}>{doc.status}</Badge>
                    </td>
                    <td style={{ padding: "12px 20px", fontSize: "13px", color: "#a3a3a3", whiteSpace: "nowrap" }}>{docUploaded(doc)}</td>
                    <td style={{ padding: "12px 24px 12px 20px", whiteSpace: "nowrap", textAlign: "right" }}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.push(`/documents/${doc.id}`)}
                      >
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
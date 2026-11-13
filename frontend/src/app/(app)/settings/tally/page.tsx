"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { AlertCircle, CheckCircle, Loader2, Plug, Copy, Check, Download } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const inputStyle = {
  height: "36px", padding: "0 11px", borderRadius: "7px",
  border: "1px solid #e0e0e0", fontSize: "13px", color: "#0a0a0a",
  background: "#ffffff", outline: "none", width: "100%",
  fontFamily: "var(--font-family-sans)", boxSizing: "border-box" as const,
};

function Field({ label, hint, required, children }: { label: string; hint?: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      <label style={{ fontSize: "12px", fontWeight: 600, color: "#525252", letterSpacing: "0.01em" }}>
        {label}{required && <span style={{ color: "#dc2626", marginLeft: "2px" }}>*</span>}
      </label>
      {children}
      {hint && <p style={{ fontSize: "11.5px", color: "#a3a3a3", margin: 0 }}>{hint}</p>}
    </div>
  );
}

function CopyField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      <label style={{ fontSize: "12px", fontWeight: 600, color: "#525252", letterSpacing: "0.01em" }}>{label}</label>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div style={{
          flex: 1, height: "36px", padding: "0 11px", borderRadius: "7px",
          border: "1px solid #e0e0e0", fontSize: "12.5px", color: "#0a0a0a",
          background: "#f5f5f5", fontFamily: mono ? "monospace" : "var(--font-family-sans)",
          display: "flex", alignItems: "center", overflow: "hidden",
          whiteSpace: "nowrap" as const, textOverflow: "ellipsis",
        }}>
          {value || <span style={{ color: "#a3a3a3" }}>—</span>}
        </div>
        <button
          onClick={handleCopy}
          disabled={!value}
          title="Copy to clipboard"
          style={{
            flexShrink: 0, width: "36px", height: "36px", display: "flex", alignItems: "center",
            justifyContent: "center", borderRadius: "7px", border: "1px solid #e0e0e0",
            background: copied ? "#d1fae5" : "#ffffff", cursor: value ? "pointer" : "not-allowed",
            color: copied ? "#059669" : "#737373", transition: "all 0.15s",
          }}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
    </div>
  );
}

const STATUS_STYLE: Record<string, { color: string; label: string }> = {
  online:        { color: "#059669", label: "Connector online" },
  offline:       { color: "#f59e0b", label: "Connector offline" },
  not_installed: { color: "#a3a3a3", label: "Connector not installed" },
};

function TallySettingsInner() {
  const searchParams = useSearchParams();
  const clientId = searchParams.get("clientId");

  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("9000");
  const [company, setCompany] = useState("");
  const [connectorStatus, setConnectorStatus] = useState("not_installed");
  const [connectorApiKey, setConnectorApiKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [generatingKey, setGeneratingKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testError, setTestError] = useState("");

  function getToken() {
    return typeof window !== "undefined" ? localStorage.getItem("clearbook_token") : null;
  }
  function authHeader() {
    const t = getToken();
    return t ? { Authorization: `Bearer ${t}` } as HeadersInit : undefined;
  }

  useEffect(() => {
    async function load() {
      if (clientId) {
        setLoading(true);
        try {
          const res = await fetch(`${API}/api/v1/tally/settings/${clientId}`, {
            headers: { ...authHeader() },
          });
          if (res.ok) {
            const cfg = await res.json();
            if (cfg.tally_host)             setHost(cfg.tally_host);
            if (cfg.tally_port)             setPort(String(cfg.tally_port));
            if (cfg.tally_company)          setCompany(cfg.tally_company);
            if (cfg.tally_connector_status) setConnectorStatus(cfg.tally_connector_status);
            if (cfg.connector_api_key)      setConnectorApiKey(cfg.connector_api_key);
          }
        } catch {}
        setLoading(false);
      } else {
        try {
          const stored = localStorage.getItem("clearbook_tally_config");
          if (stored) {
            const cfg = JSON.parse(stored);
            if (cfg.host)    setHost(cfg.host);
            if (cfg.port)    setPort(String(cfg.port));
            if (cfg.company) setCompany(cfg.company);
          }
        } catch {}
      }
      setMounted(true);
    }
    load();
  }, [clientId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    if (!company.trim()) return;
    setSaving(true);
    if (clientId) {
      try {
        await fetch(`${API}/api/v1/tally/settings/${clientId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...authHeader() },
          body: JSON.stringify({
            tally_host:    host.trim() || "localhost",
            tally_port:    parseInt(port) || 9000,
            tally_company: company.trim(),
          }),
        });
      } catch {}
    } else {
      try {
        localStorage.setItem("clearbook_tally_config", JSON.stringify({
          host:    host.trim() || "localhost",
          port:    parseInt(port) || 9000,
          company: company.trim(),
        }));
      } catch {}
    }
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  async function handleGenerateKey() {
    setGeneratingKey(true);
    try {
      const res = await fetch(`${API}/api/v1/connector/generate-key`, {
        method: "POST",
        headers: { ...authHeader() },
      });
      if (res.ok) {
        const data = await res.json();
        setConnectorApiKey(data.api_key);
      }
    } catch {}
    setGeneratingKey(false);
  }

  async function handleTest() {
    setTestError("");
    if (!company.trim()) {
      setTestError("Please enter the Tally company name before testing.");
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const url = clientId
        ? `${API}/api/v1/tally/test/${clientId}`
        : `${API}/api/v1/tally/test-connection`;
      const body = clientId
        ? undefined
        : JSON.stringify({ host: host.trim() || "localhost", port: parseInt(port) || 9000 });
      const res = await fetch(url, {
        method: clientId ? "GET" : "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        ...(body ? { body } : {}),
      });
      if (res.ok) {
        const data = await res.json();
        setTestResult({ ok: true, message: data?.message || "Connected to Tally successfully." });
      } else {
        const err = await res.json().catch(() => ({}));
        const msg = Array.isArray(err?.detail)
          ? err.detail.map((e: any) => e.msg).join("; ")
          : err?.detail || `Connection failed (${res.status})`;
        setTestResult({ ok: false, message: msg });
      }
    } catch (e: any) {
      setTestResult({ ok: false, message: e?.message || "Could not reach Tally. Make sure Tally is running and the port is open." });
    } finally {
      setTesting(false);
    }
  }

  const isConfigured = host && port && company.trim();
  const statusInfo = STATUS_STYLE[connectorStatus] ?? STATUS_STYLE["not_installed"];

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar title="Settings" subtitle="Tally Integration" />

      <div style={{ padding: "24px 28px", maxWidth: "600px", display: "flex", flexDirection: "column", gap: "20px" }}>

        {/* Header card */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: "20px 24px", display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ width: "40px", height: "40px", background: "#eef0fd", borderRadius: "10px", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <Plug size={18} color="#5266eb" />
          </div>
          <div>
            <p style={{ fontSize: "14px", fontWeight: 650, color: "#0a0a0a", margin: 0 }}>Tally Integration</p>
            <p style={{ fontSize: "12px", color: "#a3a3a3", margin: "2px 0 0" }}>
              Configure your Tally connection to post approved vouchers directly into Tally.
            </p>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px", flexShrink: 0 }}>
            {isConfigured && (
              <span style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "12px", color: "#059669", fontWeight: 500 }}>
                <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: "#059669" }} />
                Configured
              </span>
            )}
            {clientId && (
              <span style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "11.5px", color: statusInfo.color, fontWeight: 500 }}>
                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: statusInfo.color }} />
                {statusInfo.label}
              </span>
            )}
          </div>
        </div>

        {/* Connector Credentials card */}
        {clientId && (
          <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
            <div style={{ padding: "14px 20px", borderBottom: "1px solid #ebebeb", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Connector Credentials</span>
              <a
                href="https://github.com/jaxfortech-user/clearbook/releases/download/connector-latest/ClearbookConnector.exe"
                download
                style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "12px", color: "#5266eb", fontWeight: 500, textDecoration: "none" }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = "underline")}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = "none")}
              >
                <Download size={12} /> Download Connector
              </a>
            </div>
            <div style={{ padding: "16px 24px 20px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <p style={{ fontSize: "12px", color: "#737373", margin: 0, lineHeight: "1.5" }}>
                Enter these when you run <strong>ClearbookConnector.exe</strong> for the first time on the Tally machine.
              </p>
              {loading ? (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#a3a3a3", fontSize: "12.5px" }}>
                  <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> Loading…
                </div>
              ) : (
                <>
                  <CopyField label="Client ID" value={clientId} mono />
                  <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#525252" }}>API Key</label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <div style={{ flex: 1, height: "36px", padding: "0 11px", borderRadius: "7px", border: "1px solid #e0e0e0", fontSize: "12.5px", background: "#f5f5f5", fontFamily: "monospace", display: "flex", alignItems: "center", overflow: "hidden", whiteSpace: "nowrap" as const }}>
                    {connectorApiKey || <span style={{ color: "#a3a3a3" }}>Not generated yet</span>}
                  </div>
                  <button onClick={handleGenerateKey} disabled={generatingKey}
                    style={{ height: "36px", padding: "0 14px", borderRadius: "7px", border: "1px solid #e0e0e0", background: "#fff", cursor: "pointer", fontSize: "12px", color: "#5266eb", fontWeight: 600 }}>
                    {generatingKey ? "…" : connectorApiKey ? "Regenerate" : "Generate"}
                  </button>
                </div>
              </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Config form */}
        <div style={{ background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "12px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", overflow: "hidden" }}>
          <div style={{ padding: "14px 20px", borderBottom: "1px solid #ebebeb" }}>
            <span style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>Connection Settings</span>
          </div>
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
            {loading && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#a3a3a3", fontSize: "12.5px" }}>
                <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> Loading settings…
              </div>
            )}
            <Field label="Tally Company Name" required hint="Must match the company name exactly as it appears in Tally">
              <input
                value={mounted ? company : ""}
                onChange={e => { setCompany(e.target.value); setTestError(""); }}
                placeholder="e.g. ABC Trading LLC"
                style={{ ...inputStyle, borderColor: testError ? "#dc2626" : "#e0e0e0" }}
                onFocus={e => (e.target.style.borderColor = testError ? "#dc2626" : "#5266eb")}
                onBlur={e => (e.target.style.borderColor = testError ? "#dc2626" : "#e0e0e0")}
              />
              {testError && (
                <p style={{ fontSize: "11.5px", color: "#dc2626", margin: "2px 0 0", display: "flex", alignItems: "center", gap: "4px" }}>
                  <AlertCircle size={11} /> {testError}
                </p>
              )}
            </Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <Field label="Tally Host" hint="IP or hostname where Tally is running">
                <input
                  value={mounted ? host : ""}
                  onChange={e => setHost(e.target.value)}
                  placeholder="localhost"
                  style={inputStyle}
                  onFocus={e => (e.target.style.borderColor = "#5266eb")}
                  onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                />
              </Field>
              <Field label="Tally Port" hint="Default Tally port is 9000">
                <input
                  type="number"
                  value={mounted ? port : ""}
                  onChange={e => setPort(e.target.value)}
                  placeholder="9000"
                  style={{ ...inputStyle, fontFamily: "monospace" }}
                  onFocus={e => (e.target.style.borderColor = "#5266eb")}
                  onBlur={e => (e.target.style.borderColor = "#e0e0e0")}
                />
              </Field>
            </div>
            {testResult && (
              <div style={{ display: "flex", alignItems: "flex-start", gap: "10px", padding: "12px 14px", background: testResult.ok ? "#d1fae5" : "#fef2f2", border: `1px solid ${testResult.ok ? "#6ee7b7" : "#fca5a5"}`, borderRadius: "8px" }}>
                {testResult.ok
                  ? <CheckCircle size={14} color="#059669" style={{ flexShrink: 0, marginTop: "1px" }} />
                  : <AlertCircle size={14} color="#dc2626" style={{ flexShrink: 0, marginTop: "1px" }} />
                }
                <span style={{ fontSize: "12.5px", color: testResult.ok ? "#059669" : "#dc2626" }}>{testResult.message}</span>
              </div>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderTop: "1px solid #ebebeb" }}>
            <button
              onClick={handleTest}
              disabled={testing}
              style={{ height: "34px", padding: "0 16px", background: "none", border: "1px solid #e0e0e0", borderRadius: "7px", fontSize: "12.5px", color: "#525252", cursor: testing ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
              onMouseEnter={e => { if (!testing) e.currentTarget.style.background = "#f5f5f5"; }}
              onMouseLeave={e => { if (!testing) e.currentTarget.style.background = "none"; }}
            >
              {testing && <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />}
              {testing ? "Testing…" : "Test Connection"}
            </button>
            <button
              onClick={handleSave}
              disabled={!company.trim() || saving}
              style={{ height: "34px", padding: "0 20px", background: !company.trim() ? "#a5b0f5" : "#5266eb", color: "#fff", border: "none", borderRadius: "7px", fontSize: "12.5px", fontWeight: 600, cursor: !company.trim() ? "not-allowed" : "pointer", fontFamily: "var(--font-family-sans)", display: "flex", alignItems: "center", gap: "6px" }}
              onMouseEnter={e => { if (company.trim()) e.currentTarget.style.background = "#4254d4"; }}
              onMouseLeave={e => { if (company.trim()) e.currentTarget.style.background = "#5266eb"; }}
            >
              {saving && <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />}
              {saved && <CheckCircle size={12} />}
              {saving ? "Saving…" : saved ? "Saved!" : "Save Settings"}
            </button>
          </div>
        </div>

        {/* Help card */}
        <div style={{ background: "#fafafa", border: "1px solid #ebebeb", borderRadius: "10px", padding: "14px 18px" }}>
          <p style={{ fontSize: "12px", fontWeight: 600, color: "#525252", margin: "0 0 6px" }}>How to enable Tally gateway</p>
          <ol style={{ margin: 0, paddingLeft: "16px", display: "flex", flexDirection: "column", gap: "4px" }}>
            {[
              "Open Tally on the machine you want to connect to",
              "Go to F12 → Advanced Configuration",
              "Enable 'Tally Gateway Server' and set port to 9000",
              "Make sure the Tally machine is on the same network",
            ].map((step, i) => (
              <li key={i} style={{ fontSize: "12px", color: "#737373" }}>{step}</li>
            ))}
          </ol>
        </div>

      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function TallySettingsPage() {
  return (
    <Suspense fallback={null}>
      <TallySettingsInner />
    </Suspense>
  );
}

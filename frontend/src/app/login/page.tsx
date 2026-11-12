"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BookOpen } from "lucide-react";
import { login } from "@/lib/api";
import { setToken, setAuthUser } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(email, password);
      setToken(res.access_token);
      setAuthUser({ user_id: res.user_id, email: res.email, full_name: res.full_name ?? undefined, role: res.role, tenant_id: res.tenant_id });
      router.push(res.role === "super_admin" ? "/admin/tenants" : next);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", background: "#fafafa",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--font-family-sans)",
    }}>
      <div style={{ width: "100%", maxWidth: "380px", padding: "0 24px" }}>

        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "32px", justifyContent: "center" }}>
          <div style={{
            width: "32px", height: "32px", background: "#5266eb",
            borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <BookOpen size={16} color="#fff" strokeWidth={2.5} />
          </div>
          <span style={{ fontSize: "16px", fontWeight: 700, color: "#0a0a0a", letterSpacing: "-0.3px" }}>Clearbook</span>
        </div>

        {/* Card */}
        <div style={{
          background: "#ffffff", border: "1px solid #ebebeb",
          borderRadius: "12px", padding: "32px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        }}>
          <h1 style={{ fontSize: "17px", fontWeight: 650, color: "#0a0a0a", marginBottom: "4px", letterSpacing: "-0.2px" }}>
            Sign in
          </h1>
          <p style={{ fontSize: "13px", color: "#a3a3a3", marginBottom: "24px" }}>
            CA Practice Management Platform
          </p>

          {error && (
            <div style={{
              padding: "10px 14px", marginBottom: "16px",
              background: "#fee2e2", border: "1px solid #fca5a5",
              borderRadius: "8px", fontSize: "13px", color: "#dc2626",
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ fontSize: "12px", fontWeight: 500, color: "#525252", display: "block", marginBottom: "6px" }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@clearbook.ae"
                required
                style={{
                  width: "100%", height: "36px", padding: "0 12px",
                  border: "1px solid #e8e8e8", borderRadius: "8px",
                  fontSize: "13px", color: "#0a0a0a", background: "#ffffff",
                  outline: "none", fontFamily: "var(--font-family-sans)",
                  boxSizing: "border-box", transition: "border-color 0.15s, box-shadow 0.15s",
                }}
                onFocus={e => { e.target.style.borderColor = "#5266eb"; e.target.style.boxShadow = "0 0 0 3px rgba(82,102,235,0.08)"; }}
                onBlur={e => { e.target.style.borderColor = "#e8e8e8"; e.target.style.boxShadow = "none"; }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: 500, color: "#525252", display: "block", marginBottom: "6px" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: "100%", height: "36px", padding: "0 12px",
                  border: "1px solid #e8e8e8", borderRadius: "8px",
                  fontSize: "13px", color: "#0a0a0a", background: "#ffffff",
                  outline: "none", fontFamily: "var(--font-family-sans)",
                  boxSizing: "border-box", transition: "border-color 0.15s, box-shadow 0.15s",
                }}
                onFocus={e => { e.target.style.borderColor = "#5266eb"; e.target.style.boxShadow = "0 0 0 3px rgba(82,102,235,0.08)"; }}
                onBlur={e => { e.target.style.borderColor = "#e8e8e8"; e.target.style.boxShadow = "none"; }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: "4px", height: "36px", width: "100%",
                background: loading ? "#8b9cf4" : "#5266eb",
                color: "#ffffff", border: "none", borderRadius: "8px",
                fontSize: "13px", fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                fontFamily: "var(--font-family-sans)",
                transition: "background 0.15s",
              }}
              onMouseEnter={e => { if (!loading) e.currentTarget.style.background = "#4254d4"; }}
              onMouseLeave={e => { if (!loading) e.currentTarget.style.background = "#5266eb"; }}
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>

        <p style={{ textAlign: "center", fontSize: "11.5px", color: "#c0c0c0", marginTop: "20px" }}>
          Clearbook · UAE CA Practice Platform
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
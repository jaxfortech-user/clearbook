"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  FileText,
  Receipt,
  Settings,
  BookOpen,
  ChevronDown,
  LogOut,
  TrendingUp,
  Landmark,
  ClipboardCheck,
  Building2,
  BookMarked,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { clearToken, getAuthUser } from "@/lib/auth";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/clients", label: "Clients", icon: Users },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/vouchers", label: "Vouchers", icon: Receipt },
];

const reportsNav = [
  { href: "/reports", label: "Reports", icon: TrendingUp },
  { href: "/bank-rec", label: "Bank Reconciliation", icon: Landmark },
  { href: "/checklist", label: "Month-end Checklist", icon: ClipboardCheck },
];

const settingsNav = [
  { href: "/settings/tally", label: "Tally Settings", icon: Settings },
  { href: "/settings/ledgers", label: "Ledger Master", icon: BookMarked },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [userOpen, setUserOpen] = useState(false);
  const [authUser, setAuthUser] = useState<ReturnType<typeof getAuthUser>>(null);
  const isSuperAdmin = authUser?.role === "super_admin";

  useEffect(() => {
    setAuthUser(getAuthUser());
  }, []);

  function handleLogout() {
    clearToken();
    router.push("/login");
  }


  return (
    <aside style={{
      position: "fixed",
      top: 0,
      left: 0,
      width: "236px",
      height: "100vh",
      background: "#ffffff",
      borderRight: "1px solid #ebebeb",
      display: "flex",
      flexDirection: "column",
      zIndex: 50,
      fontFamily: "var(--font-family-sans)",
    }}>

      {/* Logo */}
      <div style={{
        height: "56px",
        display: "flex",
        alignItems: "center",
        padding: "0 18px",
        borderBottom: "1px solid #f0f0f0",
        gap: "10px",
        flexShrink: 0,
      }}>
        <div style={{
          width: "28px",
          height: "28px",
          background: "#5266eb",
          borderRadius: "7px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}>
          <BookOpen size={14} color="#fff" strokeWidth={2.5} />
        </div>
        <div>
          <div style={{ fontSize: "13.5px", fontWeight: 700, color: "#0a0a0a", letterSpacing: "-0.3px", lineHeight: 1 }}>
            Clearbook
          </div>
          <div style={{ fontSize: "10px", color: "#a3a3a3", marginTop: "2px", fontWeight: 500 }}>
            CA Platform
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "10px 10px", overflowY: "auto" }}>
        <div style={{ marginBottom: "4px" }}>
          <div style={{
            fontSize: "10px",
            fontWeight: 600,
            color: "#c0c0c0",
            letterSpacing: "0.07em",
            textTransform: "uppercase",
            padding: "8px 8px 4px",
          }}>
            Workspace
          </div>
        </div>

        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "9px",
                padding: "7px 10px",
                borderRadius: "7px",
                marginBottom: "1px",
                fontSize: "13px",
                fontWeight: active ? 600 : 450,
                color: active ? "#5266eb" : "#525252",
                background: active ? "#eef0fd" : "transparent",
                textDecoration: "none",
                transition: "background 0.1s, color 0.1s",
              }}
              onMouseEnter={e => {
                if (!active) {
                  (e.currentTarget as HTMLElement).style.background = "#f5f5f5";
                  (e.currentTarget as HTMLElement).style.color = "#0a0a0a";
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                  (e.currentTarget as HTMLElement).style.color = "#525252";
                }
              }}
            >
              <Icon
                size={15}
                strokeWidth={active ? 2.2 : 1.8}
                color={active ? "#5266eb" : "currentColor"}
              />
              {label}
            </Link>
          );
        })}

        <div style={{ marginTop: "12px", marginBottom: "4px" }}>
          <div style={{
            fontSize: "10px",
            fontWeight: 600,
            color: "#c0c0c0",
            letterSpacing: "0.07em",
            textTransform: "uppercase",
            padding: "8px 8px 4px",
          }}>
            Finance
          </div>
        </div>

        {reportsNav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "9px",
                padding: "7px 10px",
                borderRadius: "7px",
                marginBottom: "1px",
                fontSize: "13px",
                fontWeight: active ? 600 : 450,
                color: active ? "#5266eb" : "#525252",
                background: active ? "#eef0fd" : "transparent",
                textDecoration: "none",
                transition: "background 0.1s, color 0.1s",
              }}
              onMouseEnter={e => {
                if (!active) {
                  (e.currentTarget as HTMLElement).style.background = "#f5f5f5";
                  (e.currentTarget as HTMLElement).style.color = "#0a0a0a";
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                  (e.currentTarget as HTMLElement).style.color = "#525252";
                }
              }}
            >
              <Icon
                size={15}
                strokeWidth={active ? 2.2 : 1.8}
                color={active ? "#5266eb" : "currentColor"}
              />
              {label}
            </Link>
          );
        })}

        {isSuperAdmin && (
          <>
            <div style={{ marginTop: "12px", marginBottom: "4px" }}>
              <div style={{ fontSize: "10px", fontWeight: 600, color: "#c0c0c0", letterSpacing: "0.07em", textTransform: "uppercase", padding: "8px 8px 4px" }}>
                Platform Admin
              </div>
            </div>
            {[{ href: "/admin/tenants", label: "Tenants", icon: Building2 }].map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(href + "/");
              return (
                <Link key={href} href={href} style={{ display: "flex", alignItems: "center", gap: "9px", padding: "7px 10px", borderRadius: "7px", marginBottom: "1px", fontSize: "13px", fontWeight: active ? 600 : 450, color: active ? "#5266eb" : "#525252", background: active ? "#eef0fd" : "transparent", textDecoration: "none", transition: "background 0.1s, color 0.1s" }}
                  onMouseEnter={e => { if (!active) { (e.currentTarget as HTMLElement).style.background = "#f5f5f5"; (e.currentTarget as HTMLElement).style.color = "#0a0a0a"; } }}
                  onMouseLeave={e => { if (!active) { (e.currentTarget as HTMLElement).style.background = "transparent"; (e.currentTarget as HTMLElement).style.color = "#525252"; } }}
                >
                  <Icon size={15} strokeWidth={active ? 2.2 : 1.8} color={active ? "#5266eb" : "currentColor"} />
                  {label}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* Bottom */}
      <div style={{
        borderTop: "1px solid #f0f0f0",
        padding: "10px",
        flexShrink: 0,
      }}>
        {settingsNav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link key={href} href={href} style={{ display: "flex", alignItems: "center", gap: "9px", padding: "7px 10px", borderRadius: "7px", fontSize: "13px", fontWeight: active ? 600 : 450, color: active ? "#5266eb" : "#525252", background: active ? "#eef0fd" : "transparent", textDecoration: "none", marginBottom: "2px", transition: "background 0.1s" }}
              onMouseEnter={e => { if (!active) { (e.currentTarget as HTMLElement).style.background = "#f5f5f5"; (e.currentTarget as HTMLElement).style.color = "#0a0a0a"; } }}
              onMouseLeave={e => { if (!active) { (e.currentTarget as HTMLElement).style.background = "transparent"; (e.currentTarget as HTMLElement).style.color = "#525252"; } }}
            >
              <Icon size={15} strokeWidth={active ? 2.2 : 1.8} color={active ? "#5266eb" : "currentColor"} />
              {label}
            </Link>
          );
        })}

        <button
          onClick={() => setUserOpen(o => !o)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: "9px",
            padding: "8px 10px",
            borderRadius: "8px",
            background: "#fafafa",
            border: "1px solid #ebebeb",
            cursor: "pointer",
            textAlign: "left",
            transition: "background 0.1s",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = "#f0f0f0")}
          onMouseLeave={e => (e.currentTarget.style.background = "#fafafa")}
        >
          <div style={{
            width: "24px",
            height: "24px",
            borderRadius: "50%",
            background: "#5266eb",
            color: "#fff",
            fontSize: "10px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            letterSpacing: "0.02em",
          }}>
            {(authUser?.full_name || authUser?.email || "U").slice(0, 2).toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: 600, color: "#0a0a0a", lineHeight: 1.2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {authUser?.full_name || authUser?.email?.split("@")[0] || "User"}
            </div>
            <div style={{ fontSize: "10.5px", color: "#a3a3a3", marginTop: "1px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {authUser?.email || ""}
            </div>
          </div>
          <ChevronDown size={12} color="#c0c0c0" style={{ flexShrink: 0, transform: userOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.15s" }} />
        </button>

        {userOpen && (
          <div style={{
            marginTop: "6px",
            background: "#ffffff",
            border: "1px solid #ebebeb",
            borderRadius: "8px",
            overflow: "hidden",
            boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          }}>
            <button onClick={handleLogout} style={{
              width: "100%", display: "flex", alignItems: "center", gap: "8px",
              padding: "9px 12px", fontSize: "13px", color: "#dc2626",
              background: "none", border: "none", cursor: "pointer", textAlign: "left",
              fontFamily: "var(--font-family-sans)",
            }}
              onMouseEnter={e => (e.currentTarget.style.background = "#fee2e2")}
              onMouseLeave={e => (e.currentTarget.style.background = "none")}
            >
              <LogOut size={13} /> Sign out
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
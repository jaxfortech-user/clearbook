"use client";

import { Search, Bell } from "lucide-react";
import { useState } from "react";

interface TopbarProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function Topbar({ title, subtitle, actions }: TopbarProps) {
  const [searchFocused, setSearchFocused] = useState(false);

  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 40, height: "56px",
      background: "rgba(255,255,255,0.92)", backdropFilter: "blur(12px)",
      borderBottom: "1px solid #ebebeb",
      display: "flex", alignItems: "center",
      padding: "0 28px", gap: "16px",
      fontFamily: "var(--font-family-sans)",
    }}>

      {/* Page title */}
      <div style={{ flex: "0 0 auto" }}>
        <h1 style={{ fontSize: "15px", fontWeight: 650, color: "#0a0a0a", letterSpacing: "-0.2px", lineHeight: 1 }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{ fontSize: "11.5px", color: "#a3a3a3", marginTop: "2px", fontWeight: 400 }}>
            {subtitle}
          </p>
        )}
      </div>

      {/* Search bar */}
      <div style={{ flex: 1, maxWidth: "360px", marginLeft: "8px" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: "8px",
          padding: "0 12px", height: "32px",
          background: searchFocused ? "#ffffff" : "#f5f5f5",
          border: `1px solid ${searchFocused ? "#5266eb" : "#e8e8e8"}`,
          borderRadius: "8px", transition: "all 0.15s",
          boxShadow: searchFocused ? "0 0 0 3px rgba(82,102,235,0.08)" : "none",
        }}>
          <Search size={13} color={searchFocused ? "#5266eb" : "#b0b0b0"} style={{ flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search clients, documents…"
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            style={{
              flex: 1, border: "none", outline: "none",
              background: "transparent", fontSize: "12.5px",
              color: "#0a0a0a", fontFamily: "var(--font-family-sans)",
            }}
          />
          <kbd style={{
            fontSize: "10px", color: "#c0c0c0", background: "#ebebeb",
            border: "1px solid #e0e0e0", borderRadius: "4px",
            padding: "1px 5px", flexShrink: 0,
          }}>⌘K</kbd>
        </div>
      </div>

      <div style={{ flex: 1 }} />

      {/* Right side */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <button style={{
          width: "32px", height: "32px", display: "flex",
          alignItems: "center", justifyContent: "center",
          borderRadius: "8px", border: "1px solid #ebebeb",
          background: "#ffffff", cursor: "pointer",
          position: "relative", transition: "background 0.1s",
        }}
          onMouseEnter={e => (e.currentTarget.style.background = "#f5f5f5")}
          onMouseLeave={e => (e.currentTarget.style.background = "#ffffff")}
        >
          <Bell size={14} color="#525252" />
          <span style={{
            position: "absolute", top: "6px", right: "7px",
            width: "6px", height: "6px",
            background: "#5266eb", borderRadius: "50%",
            border: "1.5px solid #fff",
          }} />
        </button>

        {actions && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px", paddingRight: "8px" }}>
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}
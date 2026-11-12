"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { Users, FileText, Receipt, AlertCircle, ArrowUpRight, RefreshCw, Clock, CheckCircle, Upload, Wifi } from "lucide-react";
import { getDashboard, type DashboardData } from "@/lib/api";

const statConfig = [
  { key: "activeClients", label: "Active Clients", icon: Users, urgent: false },
  { key: "documents", label: "Documents", icon: FileText, urgent: false },
  { key: "vouchers", label: "Vouchers", icon: Receipt, urgent: false },
  { key: "complianceAlerts", label: "Compliance Alerts", icon: AlertCircle, urgent: true },
];

const statSub: Record<string, string> = {
  activeClients: "Total active",
  documents: "On record",
  vouchers: "Total entries",
  complianceAlerts: "Action required",
};

const statusDot: Record<string, string> = {
  success: "#059669",
  warning: "#b45309",
  danger: "#dc2626",
  default: "#a3a3a3",
};

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [today, setToday] = useState("");

  useEffect(() => {
    setToday(
      new Date().toLocaleDateString("en-AE", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    );
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getDashboard();
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load dashboard data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Topbar
        title="Dashboard"
        subtitle={today}
        actions={
          <button
            style={{
              height: "32px",
              padding: "0 14px",
              background: "#5266eb",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              fontSize: "12.5px",
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "var(--font-family-sans)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#4254d4")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#5266eb")}
            onClick={() => router.push("/clients?new=true")}
          >
            + New Client
          </button>
        }
      />

      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: "20px" }}>

        {/* Loading */}
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* Skeleton stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  style={{
                    background: "#ffffff",
                    border: "1px solid #ebebeb",
                    borderRadius: "12px",
                    padding: "20px",
                    height: "108px",
                    animation: "pulse 1.5s ease-in-out infinite",
                  }}
                />
              ))}
            </div>
            {/* Skeleton activity */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #ebebeb",
                borderRadius: "12px",
                height: "280px",
                animation: "pulse 1.5s ease-in-out infinite",
              }}
            />
            <style>{`
              @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
              }
            `}</style>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div
            style={{
              background: "#fff5f5",
              border: "1px solid #fecaca",
              borderRadius: "12px",
              padding: "32px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <AlertCircle size={28} color="#dc2626" />
            <p style={{ fontSize: "14px", fontWeight: 600, color: "#dc2626" }}>
              Failed to load dashboard
            </p>
            <p style={{ fontSize: "13px", color: "#b91c1c" }}>{error}</p>
            <button
              onClick={fetchData}
              style={{
                marginTop: "4px",
                height: "34px",
                padding: "0 16px",
                background: "#dc2626",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <RefreshCw size={13} /> Retry
            </button>
          </div>
        )}

        {/* Real data */}
        {!loading && !error && data && (
          <>
            {/* Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
              {statConfig.map(({ key, label, icon: Icon, urgent }) => {
                const value = data.stats[key as keyof typeof data.stats];
                return (
                  <div
                    key={key}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #ebebeb",
                      borderRadius: "12px",
                      padding: "20px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          color: "#a3a3a3",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                        }}
                      >
                        {label}
                      </span>
                      <div
                        style={{
                          width: "28px",
                          height: "28px",
                          borderRadius: "6px",
                          background: urgent ? "#fee2e2" : "#f5f5f5",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <Icon
                          size={13}
                          color={urgent ? "#dc2626" : "#525252"}
                          strokeWidth={2}
                        />
                      </div>
                    </div>
                    <div>
                      <p
                        style={{
                          fontSize: "36px",
                          fontWeight: 600,
                          lineHeight: 1,
                          letterSpacing: "-0.02em",
                          color: urgent ? "#dc2626" : "#0a0a0a",
                        }}
                      >
                        {value}
                      </p>
                      <p
                        style={{
                          fontSize: "12px",
                          marginTop: "6px",
                          color: urgent ? "#dc2626" : "#a3a3a3",
                        }}
                      >
                        {statSub[key]}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Voucher Pipeline KPIs */}
            {data.extraStats && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
                {[
                  {
                    label: "Pending Review",
                    value: data.extraStats.pendingVouchers ?? 0,
                    icon: Clock,
                    color: "#b45309",
                    bg: "#fef3c7",
                    href: "/vouchers?status=pending",
                    sub: "Awaiting approval",
                  },
                  {
                    label: "Approved",
                    value: data.extraStats.approvedVouchers ?? 0,
                    icon: CheckCircle,
                    color: "#059669",
                    bg: "#d1fae5",
                    href: "/vouchers?status=approved",
                    sub: "Ready to post",
                  },
                  {
                    label: "Posted to Tally",
                    value: data.extraStats.postedVouchers ?? 0,
                    icon: Upload,
                    color: "#5266eb",
                    bg: "#eef0fd",
                    href: "/vouchers?status=posted_to_tally",
                    sub: "Synced entries",
                  },
                  {
                    label: "Tally Connected",
                    value: data.extraStats.tallyConnected ?? 0,
                    icon: Wifi,
                    color: "#0891b2",
                    bg: "#e0f2fe",
                    href: "/clients",
                    sub: "Active connections",
                  },
                ].map(({ label, value, icon: Icon, color, bg, href, sub }) => (
                  <div
                    key={label}
                    onClick={() => router.push(href)}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #ebebeb",
                      borderRadius: "12px",
                      padding: "16px 20px",
                      display: "flex",
                      alignItems: "center",
                      gap: "14px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                      cursor: "pointer",
                      transition: "box-shadow 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.10)")}
                    onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.06)")}
                  >
                    <div
                      style={{
                        width: "40px",
                        height: "40px",
                        borderRadius: "10px",
                        background: bg,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Icon size={18} color={color} strokeWidth={2} />
                    </div>
                    <div>
                      <p style={{ fontSize: "22px", fontWeight: 700, color: "#0a0a0a", lineHeight: 1 }}>
                        {value}
                      </p>
                      <p style={{ fontSize: "12px", fontWeight: 600, color: "#525252", marginTop: "3px" }}>
                        {label}
                      </p>
                      <p style={{ fontSize: "11px", color: "#a3a3a3", marginTop: "1px" }}>
                        {sub}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Recent Activity */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #ebebeb",
                borderRadius: "12px",
                boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 20px",
                  borderBottom: "1px solid #ebebeb",
                }}
              >
                <div>
                  <h2 style={{ fontSize: "13px", fontWeight: 600, color: "#0a0a0a" }}>
                    Recent Activity
                  </h2>
                  <p style={{ fontSize: "11px", color: "#a3a3a3", marginTop: "2px" }}>
                    Latest updates across all clients
                  </p>
                </div>
                <button
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    fontSize: "12px",
                    color: "#5266eb",
                    fontWeight: 500,
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: "4px 8px",
                    borderRadius: "6px",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#eef0fd")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                >
                  View all <ArrowUpRight size={12} />
                </button>
              </div>

              {data.recentActivity.length === 0 ? (
                <div
                  style={{
                    padding: "48px 20px",
                    textAlign: "center",
                    color: "#a3a3a3",
                    fontSize: "13px",
                  }}
                >
                  No recent activity yet.
                </div>
              ) : (
                data.recentActivity.map(({ client, action, time, status }, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "12px 20px",
                      borderBottom:
                        i < data.recentActivity.length - 1
                          ? "1px solid #ebebeb"
                          : "none",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "#fafafa")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "transparent")
                    }
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <div
                        style={{
                          width: "32px",
                          height: "32px",
                          borderRadius: "50%",
                          background: "#f5f5f5",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#525252",
                          }}
                        >
                          {client
                            .split(" ")
                            .map((w) => w[0])
                            .slice(0, 2)
                            .join("")}
                        </span>
                      </div>
                      <div>
                        <p
                          style={{
                            fontSize: "13px",
                            fontWeight: 500,
                            color: "#0a0a0a",
                            lineHeight: 1,
                          }}
                        >
                          {client}
                        </p>
                        <p
                          style={{
                            fontSize: "11px",
                            color: "#a3a3a3",
                            marginTop: "3px",
                          }}
                        >
                          {action}
                        </p>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                          fontSize: "11px",
                          fontWeight: 500,
                          padding: "2px 8px",
                          borderRadius: "9999px",
                          background:
                            status === "success"
                              ? "#d1fae5"
                              : status === "warning"
                              ? "#fef3c7"
                              : status === "danger"
                              ? "#fee2e2"
                              : "#f5f5f5",
                          color: statusDot[status],
                        }}
                      >
                        <span
                          style={{
                            width: "5px",
                            height: "5px",
                            borderRadius: "50%",
                            background: statusDot[status],
                            flexShrink: 0,
                          }}
                        />
                        {status === "success"
                          ? "Done"
                          : status === "warning"
                          ? "Pending"
                          : status === "danger"
                          ? "Urgent"
                          : "Info"}
                      </span>
                      <span
                        style={{
                          fontSize: "11px",
                          color: "#a3a3a3",
                          minWidth: "36px",
                          textAlign: "right",
                        }}
                      >
                        {time}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

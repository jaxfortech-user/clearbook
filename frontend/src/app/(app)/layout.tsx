import { Suspense } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { FloatingChat } from "@/components/chat/FloatingChat";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", background: "#fafafa" }}>
      <Suspense fallback={<div style={{ width: "236px" }} />}>
        <Sidebar />
      </Suspense>
      <div style={{ marginLeft: "236px", minHeight: "100vh" }}>
        {children}
      </div>
      <FloatingChat />
    </div>
  );
}
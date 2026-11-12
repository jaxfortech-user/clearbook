import { Sidebar } from "@/components/layout/sidebar";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="ml-56 min-h-screen">{children}</main>
    </div>
  );
}
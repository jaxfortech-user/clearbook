export const instant = false;

import { Suspense } from "react";
import ClientDetailPage from "./client-page";

export default async function Page() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", textAlign: "center", color: "#a3a3a3" }}>Loading...</div>}>
      <ClientDetailPage />
    </Suspense>
  );
}

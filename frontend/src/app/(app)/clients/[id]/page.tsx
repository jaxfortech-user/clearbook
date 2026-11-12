export const instant = false;

import { Suspense } from "react";
import ClientDetailPage from "./client-page";

type Props = { params: Promise<{ id: string }> };

export default async function Page({ params }: Props) {
  const { id } = await params;
  return (
    <Suspense fallback={<div style={{ padding: "40px", textAlign: "center", color: "#a3a3a3" }}>Loading…</div>}>
      <ClientDetailPage id={id} />
    </Suspense>
  );
}
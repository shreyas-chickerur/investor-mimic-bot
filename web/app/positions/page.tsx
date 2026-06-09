import { getSnapshot } from "@/lib/snapshot";
import { Shell } from "@/components/Shell";
import { AwaitingSnapshot } from "@/components/AwaitingSnapshot";
import { PositionsPage } from "@/components/pages/PositionsPage";

export const revalidate = 3600;

export default async function Page() {
  const snapshot = await getSnapshot();
  return (
    <Shell snapshot={snapshot}>
      {snapshot ? <PositionsPage snapshot={snapshot} /> : <AwaitingSnapshot />}
    </Shell>
  );
}

import { getSnapshot } from "@/lib/snapshot";
import { Shell } from "@/components/Shell";
import { AwaitingSnapshot } from "@/components/AwaitingSnapshot";
import { TradesPage } from "@/components/pages/TradesPage";

export const revalidate = 3600;

export default async function Page() {
  const snapshot = await getSnapshot();
  return (
    <Shell snapshot={snapshot}>
      {snapshot ? <TradesPage snapshot={snapshot} /> : <AwaitingSnapshot />}
    </Shell>
  );
}

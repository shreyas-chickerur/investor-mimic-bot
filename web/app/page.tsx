import { getSnapshot } from "@/lib/snapshot";
import { Shell } from "@/components/Shell";
import { AwaitingSnapshot } from "@/components/AwaitingSnapshot";
import { OverviewPage } from "@/components/pages/OverviewPage";

export const revalidate = 3600;

export default async function Page() {
  const snapshot = await getSnapshot();
  return (
    <Shell snapshot={snapshot}>
      {snapshot ? <OverviewPage snapshot={snapshot} /> : <AwaitingSnapshot />}
    </Shell>
  );
}

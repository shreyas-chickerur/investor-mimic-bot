import { getSnapshot } from "@/lib/snapshot";
import { Shell } from "@/components/Shell";
import { AwaitingSnapshot } from "@/components/AwaitingSnapshot";
import { AnalyticsPage } from "@/components/pages/AnalyticsPage";

export const revalidate = 3600;

export default async function Page() {
  const snapshot = await getSnapshot();
  return (
    <Shell snapshot={snapshot}>
      {snapshot ? <AnalyticsPage snapshot={snapshot} /> : <AwaitingSnapshot />}
    </Shell>
  );
}

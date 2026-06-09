import { getSnapshot } from "@/lib/snapshot";
import { Shell } from "@/components/Shell";
import { AwaitingSnapshot } from "@/components/AwaitingSnapshot";
import { StrategiesPage } from "@/components/pages/StrategiesPage";

export const revalidate = 3600;

export default async function Page() {
  const snapshot = await getSnapshot();
  return (
    <Shell snapshot={snapshot}>
      {snapshot ? <StrategiesPage snapshot={snapshot} /> : <AwaitingSnapshot />}
    </Shell>
  );
}

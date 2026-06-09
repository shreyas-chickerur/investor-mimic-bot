import { getSnapshot } from "@/lib/snapshot";
import { Shell } from "@/components/Shell";
import { AwaitingSnapshot } from "@/components/AwaitingSnapshot";
import { SignalsPage } from "@/components/pages/SignalsPage";

export const revalidate = 3600;

export default async function Page() {
  const snapshot = await getSnapshot();
  return (
    <Shell snapshot={snapshot}>
      {snapshot ? <SignalsPage snapshot={snapshot} /> : <AwaitingSnapshot />}
    </Shell>
  );
}

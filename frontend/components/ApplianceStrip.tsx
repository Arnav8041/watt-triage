import { ApplianceCard } from "./ApplianceCard";
import type { Appliance, Reading } from "@/lib/types";

export function ApplianceStrip({
  appliances,
  traces,
}: {
  appliances: Appliance[];
  traces: Record<string, Reading[]>;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {appliances.map((appliance) => (
        <ApplianceCard key={appliance.id} appliance={appliance} readings={traces[appliance.id] ?? []} />
      ))}
    </div>
  );
}

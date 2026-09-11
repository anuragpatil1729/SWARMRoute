import Section from "../../components/Section";
import Stat from "../../components/Stat";
import RouteMap from "../../components/RouteMap";
import { getRouteMap } from "../../lib/data";

export default function RoutesPage() {
  const { dataset, status, totalDistance, customers, depot, routes } = getRouteMap();

  return (
    <div>
      <Section index="1" title="Route map">
        <p className="text-sm text-muted max-w-2xl">
          The OR-Tools CVRPTW solution for the {dataset} benchmark — 100
          customers, up to 25 vehicles, capacity and time-window constraints.
          Click a truck below to isolate its route.
        </p>
      </Section>

      <Section index="2">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Stat label="solver status" value={status} />
          <Stat label="trucks used" value={routes.length} unit="/ 25" />
          <Stat label="customers" value={customers.length - 1} />
          <Stat label="total distance" value={totalDistance ? Math.round(totalDistance) : "—"} unit="units" />
        </div>
      </Section>

      <Section
        index="3"
        title={`Figure 2 — ${dataset} depot & customer layout`}
        description="Red square is the depot. Each colored line is one truck's tour; gray dots are customer locations."
      >
        <RouteMap customers={customers} depot={depot} routes={routes} />
      </Section>
    </div>
  );
}

import Section from "../../components/Section";
import Stat from "../../components/Stat";
import RouteMap from "../../components/RouteMap";
import { getRouteMap } from "../../lib/data";

export default function RoutesPage() {
  const { dataset, status, totalDistance, customers, depot, routes } = getRouteMap();

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white mb-1">Route map</h1>
      <p className="text-sm text-muted mb-8 max-w-2xl">
        The OR-Tools CVRPTW solution for the {dataset} benchmark — 100
        customers, up to 25 vehicles, capacity and time-window constraints.
        Click a truck below to isolate its route.
      </p>

      <Section>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Stat label="Solver status" value={status} tickColor="#4dd9c4" />
          <Stat label="Trucks used" value={routes.length} unit={`/ 25`} tickColor="#f5a623" />
          <Stat label="Customers" value={customers.length - 1} tickColor="#818cf8" />
          <Stat
            label="Total distance"
            value={totalDistance ? Math.round(totalDistance) : "—"}
            unit="units"
            tickColor="#4dd9c4"
          />
        </div>
      </Section>

      <Section
        title={`${dataset} — depot & customer layout`}
        description="Orange square is the depot. Each colored line is one truck's tour; gray dots are customer locations."
      >
        <RouteMap customers={customers} depot={depot} routes={routes} />
      </Section>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

// Smooth multi-waypoint Bezier generator between start and end
export function generateRouteWaypoints(start, end, isDetour = false, numPoints = 50) {
  const [lat1, lon1] = start;
  const [lat2, lon2] = end;
  const points = [];

  const midLat = (lat1 + lat2) / 2;
  const midLon = (lon1 + lon2) / 2;
  const dLat = lat2 - lat1;
  const dLon = lon2 - lon1;

  // Perpendicular vector for offset
  const curvature = isDetour ? 0.38 : 0.03;
  const perpLat = -dLon * curvature;
  const perpLon = dLat * curvature;

  const apexLat = midLat + perpLat;
  const apexLon = midLon + perpLon;

  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints;
    const u = 1 - t;
    const lat = u * u * lat1 + 2 * u * t * apexLat + t * t * lat2;
    const lon = u * u * lon1 + 2 * u * t * apexLon + t * t * lon2;
    points.push([Number(lat.toFixed(6)), Number(lon.toFixed(6))]);
  }
  return points;
}

export default function SimulatorMap({
  tripStartLat = 18.5204,
  tripStartLon = 73.8567,
  vehicleLat = 18.5204,
  vehicleLon = 73.8567,
  destLat = 18.5912,
  destLon = 73.7389,
  heading = 90,
  speedKmh = 35,
  fuelLevel = 80,
  vehicleCondition = 1.0,
  trafficLevel = "NORMAL",
  ppoAction = "KEEP_ROUTE",
  peerCount = 2,
  vehicleId = "PTR_MH12CE1047",
  allVehicles = [],
  roadCoordinates = [],
  detourCoordinates = [],
  onSelectVehicle = null,
  onLocationSelect = null,
  onDestinationSelect = null,
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const leafletRef = useRef(null);
  const layersRef = useRef({
    vehicleMarker: null,
    destMarker: null,
    peerMarkers: [],
    fleetMarkers: [],
    primaryRoute: null,
    reroutePath: null,
    trafficZone: null,
    rescuePath: null,
  });

  const [mapReady, setMapReady] = useState(false);
  const [clickMode, setClickMode] = useState("destination"); // "vehicle" | "destination"

  const clickModeRef = useRef(clickMode);
  clickModeRef.current = clickMode;
  const onLocationSelectRef = useRef(onLocationSelect);
  onLocationSelectRef.current = onLocationSelect;
  const onDestinationSelectRef = useRef(onDestinationSelect);
  onDestinationSelectRef.current = onDestinationSelect;

  // Initialize Map
  useEffect(() => {
    if (typeof window === "undefined" || !mapContainerRef.current) return;
    let isMounted = true;

    import("leaflet").then((leaflet) => {
      if (!isMounted || !mapContainerRef.current) return;
      const L = leaflet.default || leaflet;
      leafletRef.current = L;

      if (!mapInstanceRef.current && mapContainerRef.current) {
        const map = L.map(mapContainerRef.current, {
          center: [vehicleLat, vehicleLon],
          zoom: 13,
          zoomControl: true,
          attributionControl: false,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          subdomains: ["a", "b", "c"],
        }).addTo(map);

        // Click handler to set coordinates interactively based on active clickMode
        map.on("click", (e) => {
          const coords = {
            lat: Number(e.latlng.lat.toFixed(6)),
            lon: Number(e.latlng.lng.toFixed(6)),
          };
          if (clickModeRef.current === "destination") {
            if (onDestinationSelectRef.current) {
              onDestinationSelectRef.current(coords);
            }
          } else {
            if (onLocationSelectRef.current) {
              onLocationSelectRef.current(coords);
            }
          }
        });

        mapInstanceRef.current = map;
        setMapReady(true);
        setTimeout(() => map.invalidateSize(), 200);
      }
    });

    return () => {
      isMounted = false;
    };
  }, []);

  // Update Markers, Paths, and Traffic depending on PPO prediction
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !L || !mapReady) return;

    const layers = layersRef.current;

    // 1. Clear old path layers
    if (layers.primaryRoute) map.removeLayer(layers.primaryRoute);
    if (layers.reroutePath) map.removeLayer(layers.reroutePath);
    if (layers.trafficZone) map.removeLayer(layers.trafficZone);
    if (layers.rescuePath) map.removeLayer(layers.rescuePath);
    layers.peerMarkers.forEach((m) => map.removeLayer(m));
    layers.peerMarkers = [];
    layers.fleetMarkers.forEach((m) => map.removeLayer(m));
    const tripOrigin = [tripStartLat || vehicleLat, tripStartLon || vehicleLon];
    const currentVehiclePos = [vehicleLat, vehicleLon];
    const endPos = [destLat, destLon];

    // 2. Render Vehicle Marker
    const isBroken = ppoAction === "REQUEST_ASSISTANCE" || vehicleCondition < 0.3;
    const isRerouting = ppoAction === "REROUTE";

    const markerColor = isBroken
      ? "#e11d48" // Rose red
      : isRerouting
      ? "#d97706" // Amber
      : "#2563eb"; // Blue

    const vehicleIconSvg = isBroken
      ? `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
      : isRerouting
      ? `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`
      : `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="1" y="3" width="15" height="13" rx="2"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`;

    const vehicleHtml = `
      <div style="position: relative; display: flex; flex-direction: column; align-items: center;">
        <div style="
          width: 44px;
          height: 44px;
          border-radius: 50%;
          background: ${markerColor};
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 12px rgba(0,0,0,0.35);
          border: 3px solid white;
          transform: rotate(${heading}deg);
          transition: transform 0.3s ease, background 0.3s ease;
        ">
          ${vehicleIconSvg}
        </div>
        <div style="
          margin-top: 4px;
          background: rgba(15, 23, 42, 0.92);
          color: white;
          font-size: 10px;
          font-family: monospace;
          font-weight: bold;
          padding: 2px 7px;
          border-radius: 6px;
          white-space: nowrap;
          box-shadow: 0 2px 6px rgba(0,0,0,0.25);
        ">
          ${vehicleId.slice(0, 14)} · ${Math.round(speedKmh)} km/h
        </div>
      </div>
    `;

    const vehicleIcon = L.divIcon({
      className: "sim-vehicle-icon",
      html: vehicleHtml,
      iconSize: [44, 62],
      iconAnchor: [22, 31],
    });

    if (layers.vehicleMarker) {
      layers.vehicleMarker.setLatLng(currentVehiclePos);
      layers.vehicleMarker.setIcon(vehicleIcon);
    } else {
      layers.vehicleMarker = L.marker(currentVehiclePos, { icon: vehicleIcon, draggable: true }).addTo(map);
      layers.vehicleMarker.bindTooltip("Drag to reposition vehicle", { direction: "top", offset: [0, -20] });
      layers.vehicleMarker.on("dragend", (e) => {
        const ll = e.target.getLatLng();
        if (onLocationSelectRef.current) {
          onLocationSelectRef.current({
            lat: Number(ll.lat.toFixed(6)),
            lon: Number(ll.lng.toFixed(6)),
          });
        }
      });
    }

    // 3. Render Destination Target Marker
    const destHtml = `
      <div style="position: relative; display: flex; flex-direction: column; align-items: center;">
        <div style="
          width: 38px;
          height: 38px;
          border-radius: 50%;
          background: #10b981;
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 10px rgba(0,0,0,0.3);
          border: 3px solid white;
        ">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="1" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="1" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="23" y2="12"/></svg>
        </div>
        <div style="
          margin-top: 3px;
          background: #064e3b;
          color: #a7f3d0;
          font-size: 10px;
          font-family: monospace;
          font-weight: bold;
          padding: 2px 6px;
          border-radius: 5px;
          white-space: nowrap;
        ">
          Delivery Target
        </div>
      </div>
    `;

    const destIcon = L.divIcon({
      className: "sim-dest-icon",
      html: destHtml,
      iconSize: [38, 56],
      iconAnchor: [19, 28],
    });

    if (layers.destMarker) {
      layers.destMarker.setLatLng(endPos);
      layers.destMarker.setIcon(destIcon);
    } else {
      layers.destMarker = L.marker(endPos, { icon: destIcon, draggable: true }).addTo(map);
      layers.destMarker.bindTooltip("Drag to change destination", { direction: "top", offset: [0, -20] });
      layers.destMarker.on("dragend", (e) => {
        const ll = e.target.getLatLng();
        if (onDestinationSelectRef.current) {
          onDestinationSelectRef.current({
            lat: Number(ll.lat.toFixed(6)),
            lon: Number(ll.lng.toFixed(6)),
          });
        }
      });
    }

    // 4. Render Peer Vehicles in Range (BLE Mesh Swarm)
    if (peerCount > 0) {
      for (let i = 0; i < Math.min(peerCount, 5); i++) {
        const angle = (i * (360 / peerCount) * Math.PI) / 180;
        const distOffset = 0.015 + (i * 0.005);
        const peerPos = [
          vehicleLat + distOffset * Math.cos(angle),
          vehicleLon + distOffset * Math.sin(angle),
        ];

        const peerIcon = L.divIcon({
          className: "peer-icon",
          html: `
            <div style="
              width: 28px;
              height: 28px;
              border-radius: 50%;
              background: #6366f1;
              color: white;
              display: flex;
              align-items: center;
              justify-content: center;
              border: 2px solid white;
              box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            ">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M4.93 19.07A10 10 0 0 1 12 2a10 10 0 0 1 7.07 17.07"/><path d="M7.76 16.24A6 6 0 0 1 12 6a6 6 0 0 1 4.24 10.24"/><circle cx="12" cy="18" r="1"/></svg>
            </div>
          `,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        });

        const peerMarker = L.marker(peerPos, { icon: peerIcon }).addTo(map);
        peerMarker.bindTooltip(`Peer Vehicle ${i + 1} (Mesh Active)`, { direction: "top", offset: [0, -10] });
        layers.peerMarkers.push(peerMarker);

        // Draw light mesh link line to current vehicle position
        const meshLine = L.polyline([currentVehiclePos, peerPos], {
          color: "#818cf8",
          weight: 2,
          dashArray: "4, 6",
          opacity: 0.65,
        }).addTo(map);
        layers.peerMarkers.push(meshLine);
      }
    }

    // 5. Render All Other Fleet Vehicles on the Map
    if (allVehicles && allVehicles.length > 0) {
      allVehicles.forEach((ov) => {
        if (ov.id === vehicleId) return; // Active vehicle is already rendered as primary marker
        if (typeof ov.lat !== "number" || typeof ov.lon !== "number") return;

        const ovPos = [ov.lat, ov.lon];
        const ovHtml = `
          <div style="position: relative; display: flex; flex-direction: column; align-items: center; cursor: pointer;">
            <div style="
              width: 32px;
              height: 32px;
              border-radius: 50%;
              background: #4f46e5;
              color: white;
              display: flex;
              align-items: center;
              justify-content: center;
              border: 2px solid white;
              box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            ">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13" rx="1.5"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>
            </div>
            <div style="
              margin-top: 3px;
              background: rgba(30, 27, 75, 0.9);
              color: #c7d2fe;
              font-size: 9px;
              font-family: monospace;
              font-weight: bold;
              padding: 1px 5px;
              border-radius: 4px;
              white-space: nowrap;
            ">
              ${ov.id.slice(0, 12)}
            </div>
          </div>
        `;

        const ovIcon = L.divIcon({
          className: "other-fleet-icon",
          html: ovHtml,
          iconSize: [32, 48],
          iconAnchor: [16, 24],
        });

        const ovMarker = L.marker(ovPos, { icon: ovIcon }).addTo(map);
        ovMarker.bindTooltip(`<b>${ov.name || ov.id}</b><br/>${ov.model || "Fleet Vehicle"}<br/>Status: ${ov.status || "AVAILABLE"}<br/>Speed: ${Math.round(ov.speed || 0)} km/h<br/><i>Click to select & simulate</i>`, {
          direction: "top",
          offset: [0, -12],
        });

        ovMarker.on("click", () => {
          if (onSelectVehicle) onSelectVehicle(ov.id);
        });

        layers.fleetMarkers.push(ovMarker);
      });
    }

    // 6. Traffic Congestion Zone (Midpoint between vehicle and destination)
    const midPoint = [(vehicleLat + destLat) / 2, (vehicleLon + destLon) / 2];
    const isTrafficHigh = trafficLevel === "SEVERE" || trafficLevel === "BLOCKED";

    if (isTrafficHigh) {
      layers.trafficZone = L.circle(midPoint, {
        radius: 750,
        color: "#dc2626",
        fillColor: "#ef4444",
        fillOpacity: 0.35,
        weight: 2,
        dashArray: "6, 6",
      }).addTo(map);

      layers.trafficZone.bindTooltip(`Severe Traffic Gridlock (${trafficLevel})`, {
        permanent: true,
        direction: "center",
        className: "bg-red-900 text-white font-mono text-[11px] px-2 py-1 rounded shadow-md border border-red-500",
      });
    }

    const normalizeCoords = (pts) => {
      if (!pts || !Array.isArray(pts)) return [];
      return pts
        .map((p) => {
          if (Array.isArray(p)) return [Number(p[0]), Number(p[1])];
          if (p && typeof p === "object") {
            const lat = p.lat !== undefined ? p.lat : p[0];
            const lon = p.lon !== undefined ? p.lon : (p.lng !== undefined ? p.lng : p[1]);
            return [Number(lat), Number(lon)];
          }
          return null;
        })
        .filter((p) => p && !isNaN(p[0]) && !isNaN(p[1]));
    };

    const cleanRoad = normalizeCoords(roadCoordinates);
    const cleanDetour = normalizeCoords(detourCoordinates);

    const directPoints = cleanRoad.length > 2
      ? cleanRoad
      : generateRouteWaypoints(tripOrigin, endPos, false, 40);

    const detourPoints = cleanDetour.length > 2
      ? cleanDetour
      : generateRouteWaypoints(tripOrigin, endPos, true, 50);

    // 6. Dynamic Path Routing based on PPO Prediction
    if (isBroken) {
      // Breakdown SOS: Draw stranded route & rescue path from nearest peer
      layers.primaryRoute = L.polyline(directPoints, {
        color: "#94a3b8",
        weight: 4,
        dashArray: "6, 8",
        opacity: 0.6,
      }).addTo(map);

      // Rescue dispatch route from peer to stranded truck
      if (layers.peerMarkers.length > 0) {
        const rescueStart = [vehicleLat + 0.018, vehicleLon + 0.012];
        layers.rescuePath = L.polyline([rescueStart, currentVehiclePos], {
          color: "#e11d48",
          weight: 5,
          opacity: 0.9,
        }).addTo(map);

        layers.rescuePath.bindTooltip("Peer Rescue & Cargo Adoption Detour", {
          permanent: true,
          direction: "top",
          className: "bg-rose-900 text-white font-mono text-[10px] px-2 py-0.5 rounded",
        });
      }
    } else if (isRerouting) {
      // REROUTE: Congested path in dashed red + Alternate Detour in Solid Amber/Orange
      layers.primaryRoute = L.polyline(directPoints, {
        color: "#ef4444",
        weight: 4,
        dashArray: "6, 8",
        opacity: 0.65,
      }).addTo(map);

      layers.reroutePath = L.polyline(detourPoints, {
        color: "#f59e0b",
        weight: 6,
        opacity: 0.95,
      }).addTo(map);

      layers.reroutePath.bindTooltip("PPO Recommended Detour Corridor", {
        permanent: true,
        direction: "top",
        className: "bg-amber-800 text-amber-100 font-mono text-[11px] px-2.5 py-1 rounded shadow-md font-bold",
      });
    } else {
      // Normal KEEP_ROUTE: Solid Emerald Green Path along Real Roads
      layers.primaryRoute = L.polyline(directPoints, {
        color: "#10b981",
        weight: 5,
        opacity: 0.9,
      }).addTo(map);

      layers.primaryRoute.bindTooltip("Optimal On-Time Road Route", {
        permanent: false,
        direction: "top",
        className: "bg-emerald-800 text-white font-mono text-[10px] px-2 py-0.5 rounded",
      });
    }

    // Fit map bounds only on origin/destination changes or first render
    const boundsKey = `${tripOrigin[0]}_${tripOrigin[1]}_${endPos[0]}_${endPos[1]}`;
    if (layersRef.current.lastBoundsKey !== boundsKey) {
      layersRef.current.lastBoundsKey = boundsKey;
      try {
        const allCoords = directPoints.length > 0 ? directPoints : [tripOrigin, endPos];
        if (isRerouting && detourPoints.length > 0) {
          allCoords.push(...detourPoints);
        }
        const bounds = L.latLngBounds(allCoords).pad(0.25);
        map.fitBounds(bounds, { maxZoom: 15, animate: true });
      } catch (e) {
        // fallback
      }
    }
  }, [tripStartLat, tripStartLon, vehicleLat, vehicleLon, destLat, destLon, heading, speedKmh, fuelLevel, vehicleCondition, trafficLevel, ppoAction, peerCount, vehicleId, allVehicles, roadCoordinates, detourCoordinates, mapReady]);

  return (
    <div className="relative w-full h-full min-h-[380px] rounded-xl overflow-hidden border border-slate-200 shadow-sm bg-slate-100">
      {/* Map Container */}
      <div ref={mapContainerRef} className="w-full h-full min-h-[380px] z-0" />

      {/* Floating Dynamic Legend */}
      <div className="absolute top-3 right-3 z-10 bg-white/95 backdrop-blur p-2.5 rounded-xl border border-slate-200 shadow-md font-mono text-[11px] space-y-1.5 max-w-[240px]">
        <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
          PPO Dynamic Route State
        </div>

        {ppoAction === "REROUTE" ? (
          <div className="space-y-1 text-amber-900 bg-amber-50 p-2 rounded-lg border border-amber-200">
            <div className="font-bold flex items-center gap-1.5">
              <span>REROUTE ACTIVE</span>
            </div>
            <div className="text-[10px] text-amber-800">
              Corridor diverted around traffic congestion zone.
            </div>
            <div className="flex items-center gap-2 pt-1 border-t border-amber-200/60">
              <span className="w-3 h-1 bg-amber-500 rounded" />
              <span className="text-[10px]">Detour Path</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-1 border-t-2 border-dashed border-red-500" />
              <span className="text-[10px] text-red-600">Blocked Path</span>
            </div>
          </div>
        ) : ppoAction === "REQUEST_ASSISTANCE" ? (
          <div className="space-y-1 text-rose-900 bg-rose-50 p-2 rounded-lg border border-rose-200">
            <div className="font-bold flex items-center gap-1.5">
              <span>EMERGENCY SOS</span>
            </div>
            <div className="text-[10px] text-rose-800">
              Breakdown / Fuel failure. Peer rescue route dispatched.
            </div>
            <div className="flex items-center gap-2 pt-1 border-t border-rose-200/60">
              <span className="w-3 h-1 bg-rose-600 rounded" />
              <span className="text-[10px]">Rescue Detour</span>
            </div>
          </div>
        ) : (
          <div className="space-y-1 text-emerald-900 bg-emerald-50 p-2 rounded-lg border border-emerald-200">
            <div className="font-bold flex items-center gap-1.5">
              <span>OPTIMAL TOUR</span>
            </div>
            <div className="text-[10px] text-emerald-800">
              Primary road route clear & fuel feasible.
            </div>
            <div className="flex items-center gap-2 pt-1 border-t border-emerald-200/60">
              <span className="w-3 h-1 bg-emerald-500 rounded" />
              <span className="text-[10px]">Active Tour</span>
            </div>
          </div>
        )}

        <div className="text-[10px] text-slate-500 pt-1.5 border-t border-slate-100 flex flex-col gap-1.5">
          <div className="flex items-center justify-between font-mono">
            <span className="text-[10px] text-slate-500 font-semibold">Map Click Target:</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setClickMode("vehicle")}
                className={`px-1.5 py-0.5 rounded text-[10px] border transition ${
                  clickMode === "vehicle"
                    ? "bg-blue-600 text-white border-blue-600 font-bold shadow-sm"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                Vehicle
              </button>
              <button
                type="button"
                onClick={() => setClickMode("destination")}
                className={`px-1.5 py-0.5 rounded text-[10px] border transition ${
                  clickMode === "destination"
                    ? "bg-emerald-600 text-white border-emerald-600 font-bold shadow-sm"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                Destination
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between text-[9px] text-slate-400">
            <span>Markers are draggable</span>
            <span>{peerCount} BLE Peers</span>
          </div>
        </div>
      </div>
    </div>
  );
}

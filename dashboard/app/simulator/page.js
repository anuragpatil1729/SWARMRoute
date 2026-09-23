"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useDashboardState } from "../../lib/useDashboardState";
import SimulatorMap, { generateRouteWaypoints } from "../../components/SimulatorMap";


const PRESET_DESTINATIONS = {
  "Hinjawadi IT": { lat: 18.5912, lon: 73.7389 },
  "Pune Airport": { lat: 18.5822, lon: 73.9197 },
  "Magarpatta": { lat: 18.5158, lon: 73.9272 },
  "PCMC Hub": { lat: 18.6298, lon: 73.7997 },
  "Swargate": { lat: 18.5018, lon: 73.8587 },
};

const LOCATION_DIRECTORY = [
  { name: "Shivajinagar Station, Pune", lat: 18.5314, lon: 73.8446 },
  { name: "Pune Junction (Railway Station)", lat: 18.5284, lon: 73.8744 },
  { name: "Hinjawadi Phase 1 (Infotech Park)", lat: 18.5912, lon: 73.7389 },
  { name: "Hinjawadi Phase 2", lat: 18.5861, lon: 73.7145 },
  { name: "Hinjawadi Phase 3", lat: 18.5772, lon: 73.6934 },
  { name: "Pune Airport (Lohegaon)", lat: 18.5822, lon: 73.9197 },
  { name: "Magarpatta Cybercity, Hadapsar", lat: 18.5158, lon: 73.9272 },
  { name: "Koregaon Park (North Main Rd)", lat: 18.5362, lon: 73.894 },
  { name: "Kalyani Nagar", lat: 18.5463, lon: 73.9034 },
  { name: "Viman Nagar (Phoenix Mall)", lat: 18.5679, lon: 73.9143 },
  { name: "Kothrud (Chandani Chowk)", lat: 18.5074, lon: 73.8077 },
  { name: "Swargate Bus Terminal", lat: 18.5018, lon: 73.8587 },
  { name: "Deccan Gymkhana / FC Road", lat: 18.5196, lon: 73.8415 },
  { name: "Baner (High Street)", lat: 18.559, lon: 73.7868 },
  { name: "Aundh (Bremen Chowk)", lat: 18.558, lon: 73.807 },
  { name: "Wakad (Dange Chowk)", lat: 18.5987, lon: 73.7686 },
  { name: "Bhosari MIDC (PCMC)", lat: 18.6298, lon: 73.8497 },
  { name: "Talawade Software Park", lat: 18.6914, lon: 73.7865 },
  { name: "Chakan Industrial Zone", lat: 18.7606, lon: 73.8543 },
  { name: "Hadapsar Industrial Estate", lat: 18.5089, lon: 73.9259 },
  { name: "Katraj (Bypass Chowk)", lat: 18.4575, lon: 73.8677 },
  { name: "Mumbai Port Trust (MbPT)", lat: 19.076, lon: 72.8777 },
  { name: "Bandra Kurla Complex (BKC), Mumbai", lat: 19.0596, lon: 72.8295 },
  { name: "Electronic City, Bengaluru", lat: 12.9716, lon: 77.5946 },
  { name: "Connaught Place, New Delhi", lat: 28.6139, lon: 77.209 },
];

function calcHaversineKm(lat1, lon1, lat2, lon2) {
  if (!lat1 || !lon1 || !lat2 || !lon2) return 0;
  const R = 6371; // km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Number((R * c).toFixed(1));
}

export default function ApiSimulatorPage() {
  const { state } = useDashboardState();
  const [activeTab, setActiveTab] = useState("telemetry"); // 'telemetry' | 'intelligence' | 'mesh'
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState(null);
  const [responseLatency, setResponseLatency] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Autonomous Continuous Simulation & Drive State
  const [tripStartLat, setTripStartLat] = useState(18.5204);
  const [tripStartLon, setTripStartLon] = useState(73.8567);
  const [isDriving, setIsDriving] = useState(false);
  const [driveStep, setDriveStep] = useState(0);
  const driveTimerRef = useRef(null);

  // Authentic Street Network Geometries from OSRM
  const [roadCoordinates, setRoadCoordinates] = useState([]);
  const [detourRoadCoordinates, setDetourRoadCoordinates] = useState([]);
  const [isRoadLoading, setIsRoadLoading] = useState(false);
  const [evaluatorFeedback, setEvaluatorFeedback] = useState(null);

  // Live Continuous PPO Decision Logs Stream
  const [decisionLogs, setDecisionLogs] = useState([
    {
      id: "init_1",
      time: new Date().toLocaleTimeString(),
      step: 0,
      vehicleId: "PTR_MH12CE1047",
      lat: 18.5204,
      lon: 73.8567,
      distanceRemaining: 12.8,
      trafficLevel: "NORMAL",
      action: "KEEP_ROUTE",
      actionCode: 4,
      reason: "Initial baseline: Route optimal, on schedule, physically feasible.",
      delayRisk: 0.016,
      latencyMs: 14,
    },
  ]);
  const [logFilter, setLogFilter] = useState("ALL"); // "ALL" | "REROUTE_ONLY"

  // Coordinate / Location Name Mode Toggles
  const [startInputMode, setStartInputMode] = useState("coords"); // "coords" | "name"
  const [destInputMode, setDestInputMode] = useState("coords");   // "coords" | "name"
  const [startLocationName, setStartLocationName] = useState("Shivajinagar Station, Pune");
  const [destLocationName, setDestLocationName] = useState("Hinjawadi Phase 1 (Infotech Park)");
  const [isGeocodingStart, setIsGeocodingStart] = useState(false);
  const [isGeocodingDest, setIsGeocodingDest] = useState(false);

  // Form State (100% editable manual inputs)
  const [vehicleId, setVehicleId] = useState("PTR_MH12CE1047");
  const [latitude, setLatitude] = useState(18.5204);
  const [longitude, setLongitude] = useState(73.8567);
  const [destLat, setDestLat] = useState(18.5912);
  const [destLon, setDestLon] = useState(73.7389);
  const [speedKmh, setSpeedKmh] = useState(35.0);
  const [heading, setHeading] = useState(90.0);
  const [fuelLevel, setFuelLevel] = useState(80.0);
  const [fuelCapacityLiters, setFuelCapacityLiters] = useState(60.0);
  const [vehicleCondition, setVehicleCondition] = useState(1.0);
  const [remainingDistanceKm, setRemainingDistanceKm] = useState(8.5);
  const [trafficLevel, setTrafficLevel] = useState("NORMAL");
  const [internetStatus, setInternetStatus] = useState("ONLINE");
  const [bleStatus, setBleStatus] = useState("ACTIVE");
  const [blePeerCount, setBlePeerCount] = useState(2);
  const [currentLoadKg, setCurrentLoadKg] = useState(50.0);
  const [maxLoadKg, setMaxLoadKg] = useState(3000.0);

  // Mesh Relay Form State
  const [relaySource, setRelaySource] = useState("DRIVER_STRANDED_01");
  const [relayDestination, setRelayDestination] = useState("BACKEND");
  const [relayBridge, setRelayBridge] = useState("DRIVER_GATEWAY_02");
  const [relayMsgType, setRelayMsgType] = useState("ASSISTANCE_REQUEST");
  const [relayHops, setRelayHops] = useState(2);
  const [relayTtl, setRelayTtl] = useState(4);

  // Dynamic Fleet Vehicles state (allows adding arbitrary vehicles to fleet)
  const defaultFleet = [
    {
      id: "PTR_MH12CE1047",
      name: "Test user 1",
      model: "Tata Ace EV (Mini Truck)",
      registration: "MH12CE1047",
      lat: 18.5204,
      lon: 73.8567,
      destLat: 18.5912,
      destLon: 73.7389,
      speed: 35.0,
      heading: 90.0,
      fuel: 80.0,
      fuelCapacity: 60.0,
      condition: 1.0,
      remainingDist: 8.5,
      traffic: "NORMAL",
      status: "AVAILABLE",
      maxWeight: 3000,
      currentLoad: 50,
    },
    {
      id: "PTR_MH12CE1046",
      name: "Testuser2",
      model: "Tata Ace EV (Mini Truck)",
      registration: "MH12CE1046",
      lat: 18.5312,
      lon: 73.8445,
      destLat: 18.5601,
      destLon: 73.7802,
      speed: 28.0,
      heading: 140.0,
      fuel: 65.0,
      fuelCapacity: 60.0,
      condition: 1.0,
      remainingDist: 5.2,
      traffic: "NORMAL",
      status: "AVAILABLE",
      maxWeight: 3000,
      currentLoad: 120,
    },
    {
      id: "TRUCK_01",
      name: "Fleet Driver 1",
      model: "Medium Delivery Truck",
      registration: "MH-01-FL-1001",
      lat: 18.5089,
      lon: 73.8312,
      destLat: 18.5721,
      destLon: 73.7541,
      speed: 40.0,
      heading: 45.0,
      fuel: 90.0,
      fuelCapacity: 80.0,
      condition: 1.0,
      remainingDist: 11.0,
      traffic: "NORMAL",
      status: "AVAILABLE",
      maxWeight: 2500,
      currentLoad: 0,
    },
    {
      id: "TRUCK_02",
      name: "Fleet Driver 2",
      model: "Electric Cargo Van",
      registration: "MH-01-FL-1002",
      lat: 18.5421,
      lon: 73.8721,
      destLat: 18.6102,
      destLon: 73.7621,
      speed: 30.0,
      heading: 270.0,
      fuel: 55.0,
      fuelCapacity: 70.0,
      condition: 0.95,
      remainingDist: 6.8,
      traffic: "NORMAL",
      status: "AVAILABLE",
      maxWeight: 1500,
      currentLoad: 300,
    },
  ];

  const [fleetVehicles, setFleetVehicles] = useState(defaultFleet);
  const [showAddModal, setShowAddModal] = useState(false);

  // New vehicle creation form inputs
  const [newVehicleId, setNewVehicleId] = useState("");
  const [newVehicleName, setNewVehicleName] = useState("");
  const [newVehicleModel, setNewVehicleModel] = useState("Tata Ace EV (Mini Truck)");
  const [newVehicleReg, setNewVehicleReg] = useState("");
  const [newVehicleLat, setNewVehicleLat] = useState(18.5204);
  const [newVehicleLon, setNewVehicleLon] = useState(73.8567);
  const [newVehicleCapacity, setNewVehicleCapacity] = useState(3000);
  const [newVehicleFuel, setNewVehicleFuel] = useState(90);

  const handleSelectVehicle = (id) => {
    const v = fleetVehicles.find((item) => item.id === id);
    if (!v) return;
    setVehicleId(v.id);
    setLatitude(v.lat);
    setLongitude(v.lon);
    if (v.destLat) setDestLat(v.destLat);
    if (v.destLon) setDestLon(v.destLon);
    setSpeedKmh(v.speed ?? 30.0);
    setHeading(v.heading ?? 90.0);
    setFuelLevel(v.fuel ?? 80.0);
    setFuelCapacityLiters(v.fuelCapacity ?? 60.0);
    setVehicleCondition(v.condition ?? 1.0);
    setRemainingDistanceKm(v.remainingDist ?? 7.0);
    setTrafficLevel(v.traffic ?? "NORMAL");
    setMaxLoadKg(v.maxWeight ?? 3000.0);
    setCurrentLoadKg(v.currentLoad ?? 0.0);
  };

  // Sync active vehicle edits to fleetVehicles
  useEffect(() => {
    setFleetVehicles((prev) =>
      prev.map((item) => {
        if (item.id === vehicleId) {
          return {
            ...item,
            lat: latitude,
            lon: longitude,
            destLat,
            destLon,
            speed: speedKmh,
            heading,
            fuel: fuelLevel,
            fuelCapacity: fuelCapacityLiters,
            condition: vehicleCondition,
            remainingDist: remainingDistanceKm,
            traffic: trafficLevel,
            currentLoad: currentLoadKg,
            maxWeight: maxLoadKg,
          };
        }
        return item;
      })
    );
  }, [latitude, longitude, destLat, destLon, speedKmh, heading, fuelLevel, fuelCapacityLiters, vehicleCondition, remainingDistanceKm, trafficLevel, currentLoadKg, maxLoadKg, vehicleId]);

  const handleAddVehicle = (e) => {
    if (e) e.preventDefault();
    const nextNum = fleetVehicles.length + 1;
    const cleanId = newVehicleId.trim() || `TRUCK_0${nextNum}`;
    const cleanName = newVehicleName.trim() || `Rider ${nextNum}`;
    const cleanReg = newVehicleReg.trim() || `MH-12-EV-${1000 + nextNum}`;

    const newVeh = {
      id: cleanId,
      name: cleanName,
      model: newVehicleModel,
      registration: cleanReg,
      lat: Number(newVehicleLat),
      lon: Number(newVehicleLon),
      destLat: Number(newVehicleLat) + 0.03,
      destLon: Number(newVehicleLon) + 0.03,
      speed: 35.0,
      heading: 90.0,
      fuel: Number(newVehicleFuel),
      fuelCapacity: 60.0,
      condition: 1.0,
      remainingDist: 8.0,
      traffic: "NORMAL",
      status: "AVAILABLE",
      maxWeight: Number(newVehicleCapacity),
      currentLoad: 0,
      isCustom: true,
    };

    setFleetVehicles((prev) => [...prev, newVeh]);
    setShowAddModal(false);
    setNewVehicleId("");
    setNewVehicleName("");
    setNewVehicleReg("");
    handleSelectVehicle(newVeh.id);
  };

  const handleQuickSpawn = () => {
    const nextNum = fleetVehicles.length + 1;
    const offset = (nextNum * 0.008);
    const spawnId = `TRUCK_0${nextNum}`;
    const newVeh = {
      id: spawnId,
      name: `Fleet Truck ${nextNum}`,
      model: "Tata Ace EV (Mini Truck)",
      registration: `MH-12-EV-${2000 + nextNum}`,
      lat: Number((latitude + offset).toFixed(4)),
      lon: Number((longitude + offset).toFixed(4)),
      destLat: Number((destLat + offset).toFixed(4)),
      destLon: Number((destLon + offset).toFixed(4)),
      speed: 32.0,
      heading: (nextNum * 50) % 360,
      fuel: 90.0,
      fuelCapacity: 60.0,
      condition: 1.0,
      remainingDist: 7.5,
      traffic: "NORMAL",
      status: "AVAILABLE",
      maxWeight: 3000,
      currentLoad: 0,
      isCustom: true,
    };
    setFleetVehicles((prev) => [...prev, newVeh]);
    handleSelectVehicle(spawnId);
  };

  const handleRemoveVehicle = (idToRemove) => {
    if (fleetVehicles.length <= 1) return;
    setFleetVehicles((prev) => prev.filter((v) => v.id !== idToRemove));
    if (vehicleId === idToRemove) {
      const remaining = fleetVehicles.filter((v) => v.id !== idToRemove);
      if (remaining.length > 0) {
        handleSelectVehicle(remaining[0].id);
      }
    }
  };

  const handleGeocodeLocation = async (query, isStart = true) => {
    if (!query || !query.trim()) return;
    const clean = query.trim();
    if (isStart) {
      setIsGeocodingStart(true);
      setStartLocationName(clean);
    } else {
      setIsGeocodingDest(true);
      setDestLocationName(clean);
    }

    // 1. Direct local directory lookup
    const qLower = clean.toLowerCase();
    const local = LOCATION_DIRECTORY.find((item) =>
      item.name.toLowerCase().includes(qLower) || qLower.includes(item.name.toLowerCase().split(" ")[0])
    );
    if (local) {
      if (isStart) {
        setLatitude(local.lat);
        setLongitude(local.lon);
        setIsGeocodingStart(false);
      } else {
        setDestLat(local.lat);
        setDestLon(local.lon);
        setIsGeocodingDest(false);
      }
      return;
    }

    // 2. OpenStreetMap Nominatim geocoding lookup
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(clean + ", Maharashtra")}&limit=1`,
        { headers: { "User-Agent": "SWARMRoute-Simulator/1.0" } }
      );
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          const foundLat = Number(parseFloat(data[0].lat).toFixed(4));
          const foundLon = Number(parseFloat(data[0].lon).toFixed(4));
          if (isStart) {
            setLatitude(foundLat);
            setLongitude(foundLon);
          } else {
            setDestLat(foundLat);
            setDestLon(foundLon);
          }
        }
      }
    } catch (e) {
      console.warn("Geocoding lookup error:", e);
    } finally {
      if (isStart) setIsGeocodingStart(false);
      else setIsGeocodingDest(false);
    }
  };

  // Auto-stream interval ref
  const streamTimerRef = useRef(null);

  // Get current browser GPS location
  const handleUseBrowserGps = () => {
    if (typeof window !== "undefined" && "geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLatitude(Number(pos.coords.latitude.toFixed(6)));
          setLongitude(Number(pos.coords.longitude.toFixed(6)));
          if (pos.coords.speed !== null && pos.coords.speed > 0) {
            setSpeedKmh(Number((pos.coords.speed * 3.6).toFixed(1)));
          }
        },
        (err) => {
          setErrorMessage(`Geolocation access failed: ${err.message}`);
        },
        { enableHighAccuracy: true, timeout: 5000 }
      );
    } else {
      setErrorMessage("Geolocation is not supported by your browser.");
    }
  };

  // Fetch authentic street network paths from OSRM router
  useEffect(() => {
    let isMounted = true;
    const fetchRoadPath = async () => {
      setIsRoadLoading(true);
      try {
        // 1. Fetch direct optimal road route along real street networks
        const resDirect = await fetch(
          `/api/v1/route/road?origin_lat=${tripStartLat}&origin_lon=${tripStartLon}&dest_lat=${destLat}&dest_lon=${destLon}`
        );
        if (resDirect.ok) {
          const dData = await resDirect.json();
          if (isMounted && dData.success && dData.route) {
            const rawPts = dData.route.lat_lon || dData.route.coordinates || [];
            const cleanPts = rawPts.map((p) =>
              Array.isArray(p) ? [p[0], p[1]] : [p.lat, p.lon !== undefined ? p.lon : p.lng]
            );
            if (cleanPts.length > 2) {
              setRoadCoordinates(cleanPts);
              setRemainingDistanceKm(dData.route.distance_km);
            }
          }
        }

        // 2. Fetch alternative detour road route around congestion
        const resDetour = await fetch(
          `/api/v1/route/road?origin_lat=${tripStartLat}&origin_lon=${tripStartLon}&dest_lat=${destLat}&dest_lon=${destLon}&detour=true`
        );
        if (resDetour.ok) {
          const dtData = await resDetour.json();
          if (isMounted && dtData.success && dtData.route) {
            const rawDt = dtData.route.lat_lon || dtData.route.coordinates || [];
            const cleanDt = rawDt.map((p) =>
              Array.isArray(p) ? [p[0], p[1]] : [p.lat, p.lon !== undefined ? p.lon : p.lng]
            );
            if (cleanDt.length > 2) {
              setDetourRoadCoordinates(cleanDt);
            }
          }
        }
      } catch (err) {
        console.warn("Failed to fetch real road network paths:", err);
      } finally {
        if (isMounted) setIsRoadLoading(false);
      }
    };

    fetchRoadPath();
    return () => {
      isMounted = false;
    };
  }, [tripStartLat, tripStartLon, destLat, destLon]);

  // 1. Send Driver Telemetry to `/api/v1/driver/telemetry`
  const handleSendTelemetry = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    const startTime = performance.now();

    const payload = {
      vehicle_id: vehicleId.trim(),
      latitude: Number(latitude),
      longitude: Number(longitude),
      dest_lat: Number(destLat),
      dest_lon: Number(destLon),
      traffic_level: trafficLevel,
      speed_kmh: Number(speedKmh),
      heading: Number(heading),
      accuracy: 5.0,
      fuel_level: Number(fuelLevel),
      vehicle_condition: Number(vehicleCondition),
      internet_status: internetStatus,
      ble_status: bleStatus,
      ble_peer_count: Number(blePeerCount),
      remaining_distance_km: Number(remainingDistanceKm),
    };

    try {
      const res = await fetch("/api/v1/driver/telemetry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const elapsed = Math.round(performance.now() - startTime);
      setResponseLatency(elapsed);

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText}`);
      }

      const data = await res.json();
      setLastResponse({
        endpoint: "/api/v1/driver/telemetry",
        status: res.status,
        timestamp: new Date().toLocaleTimeString(),
        payloadSent: payload,
        data,
      });

      const ppo = data?.route_intelligence;
      if (ppo) {
        setDecisionLogs((prev) => [
          {
            id: `log_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
            time: new Date().toLocaleTimeString(),
            step: driveStep,
            vehicleId: vehicleId.trim(),
            lat: Number(latitude),
            lon: Number(longitude),
            distanceRemaining: Number(remainingDistanceKm),
            trafficLevel: trafficLevel,
            action: ppo.recommended_action || "KEEP_ROUTE",
            actionCode: ppo.action_code !== undefined ? ppo.action_code : 4,
            reason: ppo.reason || "Route optimal and feasible.",
            delayRisk: ppo.transformer_inference?.trends?.delay_risk ?? 0.02,
            latencyMs: elapsed,
          },
          ...prev.slice(0, 49),
        ]);
      }
    } catch (err) {
      setErrorMessage(err.message || "Failed to transmit telemetry to server.");
    } finally {
      setIsLoading(false);
    }
  };

  // 2. Query Direct Route Intelligence to `/api/v1/route/intelligence`
  const handleEvaluateIntelligence = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    const startTime = performance.now();

    const fuelRemainingLiters = (Number(fuelLevel) / 100.0) * Number(fuelCapacityLiters);

    const payload = {
      vehicle_id: vehicleId.trim(),
      current_lat: Number(latitude),
      current_lon: Number(longitude),
      dest_lat: Number(destLat),
      dest_lon: Number(destLon),
      remaining_distance_km: Number(remainingDistanceKm),
      speed_kmh: Number(speedKmh),
      fuel_remaining_liters: Number(fuelRemainingLiters.toFixed(2)),
      fuel_capacity_liters: Number(fuelCapacityLiters),
      vehicle_condition: Number(vehicleCondition),
      traffic_level: trafficLevel,
      connectivity: internetStatus === "ONLINE" ? "CLOUD_MODE" : "MESH_MODE",
      current_load_kg: Number(currentLoadKg),
      max_load_kg: Number(maxLoadKg),
    };

    try {
      const res = await fetch("/api/v1/route/intelligence", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const elapsed = Math.round(performance.now() - startTime);
      setResponseLatency(elapsed);

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText}`);
      }

      const data = await res.json();
      setLastResponse({
        endpoint: "/api/v1/route/intelligence",
        status: res.status,
        timestamp: new Date().toLocaleTimeString(),
        payloadSent: payload,
        data,
      });

      // Update authentic road geometry if embedded
      if (data.road_route) {
        const rawPts = data.road_route.lat_lon || data.road_route.coordinates || [];
        const cleanPts = rawPts.map((p) =>
          Array.isArray(p) ? [p[0], p[1]] : [p.lat, p.lon !== undefined ? p.lon : p.lng]
        );
        if (cleanPts.length > 2) {
          setRoadCoordinates(cleanPts);
        }
        if (data.road_route.distance_km) {
          setRemainingDistanceKm(data.road_route.distance_km);
        }
      }

      // Extract and append decision to the continuous live decision feed stream
      const action = data.recommended_action || "KEEP_ROUTE";
      const actionCode = data.action_code !== undefined ? data.action_code : 4;
      const reason = data.reason || "Evaluator: optimal path analyzed.";
      const delayRisk = data.transformer_inference?.trends?.delay_risk ?? 0.02;

      setDecisionLogs((prev) => [
        {
          id: `log_eval_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
          time: new Date().toLocaleTimeString(),
          step: driveStep,
          vehicleId: vehicleId.trim(),
          lat: Number(latitude),
          lon: Number(longitude),
          distanceRemaining: Number(data.metrics?.remaining_distance_km ?? remainingDistanceKm),
          trafficLevel: trafficLevel,
          action: action,
          actionCode: actionCode,
          reason: reason,
          delayRisk: delayRisk,
          latencyMs: elapsed,
        },
        ...prev.slice(0, 49),
      ]);

      // Set high-visibility visual feedback badge for the evaluator button
      setEvaluatorFeedback({
        action,
        actionCode,
        reason,
        latencyMs: elapsed,
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      setErrorMessage(err.message || "Failed to execute route intelligence evaluation.");
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Send Mesh Relay Packet to `/api/v1/mesh/relay`
  const handleSendMeshRelay = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    const startTime = performance.now();

    const payload = {
      message_id: `SIM_RELAY_${Date.now()}`,
      source_device_id: relaySource.trim(),
      destination_device_id: relayDestination.trim(),
      message_type: relayMsgType,
      timestamp: Date.now() / 1000.0,
      ttl: Number(relayTtl),
      hop_count: Number(relayHops),
      bridge_device_id: relayBridge.trim(),
      payload: {
        alert: "SOS_BREAKDOWN",
        lat: latitude,
        lon: longitude,
        fuel: fuelLevel,
      },
    };

    try {
      const res = await fetch("/api/v1/mesh/relay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const elapsed = Math.round(performance.now() - startTime);
      setResponseLatency(elapsed);

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText}`);
      }

      const data = await res.json();
      setLastResponse({
        endpoint: "/api/v1/mesh/relay",
        status: res.status,
        timestamp: new Date().toLocaleTimeString(),
        payloadSent: payload,
        data,
      });
    } catch (err) {
      setErrorMessage(err.message || "Failed to transmit mesh relay packet.");
    } finally {
      setIsLoading(false);
    }
  };

  const ppoResult = lastResponse?.data?.route_intelligence || (lastResponse?.endpoint === "/api/v1/route/intelligence" ? lastResponse?.data : null);
  const transformerResult = ppoResult?.transformer_inference;
  const metricsResult = ppoResult?.metrics;

  const activePpoAction = ppoResult?.recommended_action 
    || (trafficLevel === "SEVERE" || trafficLevel === "BLOCKED" 
        ? "REROUTE" 
        : (vehicleCondition < 0.3 || (fuelLevel < 5 && remainingDistanceKm > 10) ? "REQUEST_ASSISTANCE" : "KEEP_ROUTE"));

  const handleResetDrive = () => {
    setIsDriving(false);
    setDriveStep(0);
    setLatitude(tripStartLat);
    setLongitude(tripStartLon);
    setRemainingDistanceKm(calcHaversineKm(tripStartLat, tripStartLon, destLat, destLon));
    setDecisionLogs((prev) => [
      {
        id: `log_rst_${Date.now()}`,
        time: new Date().toLocaleTimeString(),
        step: 0,
        vehicleId: vehicleId.trim(),
        lat: tripStartLat,
        lon: tripStartLon,
        distanceRemaining: calcHaversineKm(tripStartLat, tripStartLon, destLat, destLon),
        trafficLevel: trafficLevel,
        action: "KEEP_ROUTE",
        actionCode: 4,
        reason: "Simulation reset to origin location.",
        delayRisk: 0.016,
        latencyMs: 8,
      },
      ...prev,
    ]);
  };

  // Continuous Autonomous Driving & Real-time PPO Reroute Loop
  useEffect(() => {
    if (!isDriving) {
      if (driveTimerRef.current) clearInterval(driveTimerRef.current);
      return;
    }

    const intervalMs = 1200;
    driveTimerRef.current = setInterval(() => {
      // 1. Generate active corridor waypoints (prefer authentic street geometries)
      const isCurrentlyRerouted = activePpoAction === "REROUTE";
      const directWps = (roadCoordinates && roadCoordinates.length > 5)
        ? roadCoordinates
        : generateRouteWaypoints([tripStartLat, tripStartLon], [destLat, destLon], false, 50);
      const detourWps = (detourRoadCoordinates && detourRoadCoordinates.length > 5)
        ? detourRoadCoordinates
        : generateRouteWaypoints([tripStartLat, tripStartLon], [destLat, destLon], true, 50);
      const activeWps = isCurrentlyRerouted ? detourWps : directWps;

      setDriveStep((prevStep) => {
        const stepIncrement = Math.max(1, Math.floor(activeWps.length / 50));
        const nextStep = prevStep + stepIncrement;
        if (nextStep >= activeWps.length) {
          setIsDriving(false);
          setRemainingDistanceKm(0);
          setDecisionLogs((prev) => [
            {
              id: `log_arr_${Date.now()}`,
              time: new Date().toLocaleTimeString(),
              step: nextStep,
              vehicleId: vehicleId.trim(),
              lat: destLat,
              lon: destLon,
              distanceRemaining: 0,
              trafficLevel: trafficLevel,
              action: "KEEP_ROUTE",
              actionCode: 4,
              reason: "Vehicle reached delivery destination target successfully along street network.",
              delayRisk: 0.0,
              latencyMs: 12,
            },
            ...prev,
          ]);
          return prevStep;
        }

        const curPt = activeWps[nextStep];
        const nextPt = activeWps[Math.min(activeWps.length - 1, nextStep + 1)];

        // Compute angle for heading
        const dLat = nextPt[0] - curPt[0];
        const dLon = nextPt[1] - curPt[1];
        const angleDeg = ((Math.atan2(dLon, dLat) * 180) / Math.PI + 360) % 360;

        setLatitude(curPt[0]);
        setLongitude(curPt[1]);
        setHeading(Number(angleDeg.toFixed(1)));

        // Decrement remaining distance accurately
        const totalDist = calcHaversineKm(tripStartLat, tripStartLon, destLat, destLon);
        const distLeft = Number((totalDist * (1 - nextStep / activeWps.length)).toFixed(2));
        setRemainingDistanceKm(distLeft);

        // Slightly consume fuel
        setFuelLevel((prev) => Math.max(0, Number((prev - 0.1).toFixed(2))));

        // Fire live telemetry ping to backend PPO
        const payload = {
          vehicle_id: vehicleId.trim(),
          latitude: curPt[0],
          longitude: curPt[1],
          dest_lat: Number(destLat),
          dest_lon: Number(destLon),
          traffic_level: trafficLevel,
          speed_kmh: Number(speedKmh),
          heading: Number(angleDeg.toFixed(1)),
          accuracy: 5.0,
          fuel_level: Math.max(0, Number((fuelLevel - 0.1).toFixed(2))),
          vehicle_condition: Number(vehicleCondition),
          internet_status: internetStatus,
          ble_status: bleStatus,
          ble_peer_count: Number(blePeerCount),
          remaining_distance_km: distLeft,
        };

        const tStart = performance.now();
        fetch("/api/v1/driver/telemetry", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
          .then((r) => r.json())
          .then((data) => {
            const elapsed = Math.round(performance.now() - tStart);
            setResponseLatency(elapsed);
            setLastResponse({
              endpoint: "/api/v1/driver/telemetry",
              status: 200,
              timestamp: new Date().toLocaleTimeString(),
              payloadSent: payload,
              data,
            });

            const ppo = data?.route_intelligence;
            if (ppo) {
              setDecisionLogs((prev) => [
                {
                  id: `log_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                  time: new Date().toLocaleTimeString(),
                  step: nextStep,
                  vehicleId: vehicleId.trim(),
                  lat: curPt[0],
                  lon: curPt[1],
                  distanceRemaining: distLeft,
                  trafficLevel: trafficLevel,
                  action: ppo.recommended_action || "KEEP_ROUTE",
                  actionCode: ppo.action_code !== undefined ? ppo.action_code : 4,
                  reason: ppo.reason || "Route optimal and feasible.",
                  delayRisk: ppo.transformer_inference?.trends?.delay_risk ?? 0.02,
                  latencyMs: elapsed,
                },
                ...prev.slice(0, 49),
              ]);
            }
          })
          .catch(() => {});

        // Slightly animate background fleet vehicles
        setFleetVehicles((prevFleet) =>
          prevFleet.map((fv) => {
            if (fv.id === vehicleId) return { ...fv, lat: curPt[0], lon: curPt[1] };
            const driftLat = (Math.random() - 0.5) * 0.0003;
            const driftLon = (Math.random() - 0.5) * 0.0003;
            return {
              ...fv,
              lat: Number((fv.lat + driftLat).toFixed(6)),
              lon: Number((fv.lon + driftLon).toFixed(6)),
            };
          })
        );

        return nextStep;
      });
    }, intervalMs);

    return () => {
      if (driveTimerRef.current) clearInterval(driveTimerRef.current);
    };
  }, [isDriving, tripStartLat, tripStartLon, destLat, destLon, trafficLevel, speedKmh, vehicleId, fuelLevel, vehicleCondition, internetStatus, bleStatus, blePeerCount, activePpoAction, roadCoordinates, detourRoadCoordinates]);

  return (
    <div className="space-y-6 w-full max-w-7xl mx-auto">
      {/* 1. Header Banner */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              Live Vehicle Telemetry & AI Route Intelligence
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Configure real telemetry parameters, manage active fleet vehicles, and evaluate real-time road routing, fuel kinematics, and Transformer + PPO AI decision synthesis.
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setActiveTab("telemetry")}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
              activeTab === "telemetry"
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Driver Telemetry Ingestion
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("intelligence")}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
              activeTab === "intelligence"
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Route Intelligence & PPO
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("mesh")}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
              activeTab === "mesh"
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            BLE Mesh Relay Gateway
          </button>
        </div>
      </div>

      {/* 2. Swarm Fleet Vehicle Management Bar */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-800 uppercase font-mono">Swarm Fleet Management</span>
              <span className="px-2 py-0.5 text-[11px] font-mono font-bold bg-blue-50 text-blue-700 border border-blue-200 rounded-full">
                {fleetVehicles.length} Vehicles Active
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Add, spawn, and switch between vehicles to simulate multi-agent swarm telemetry and real-time PPO decisions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleQuickSpawn}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 transition shadow-sm"
              title="Instantly deploy another active truck with auto-offset coordinates"
            >
              + Quick Spawn (+1 Truck)
            </button>
            <button
              type="button"
              onClick={() => setShowAddModal(!showAddModal)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition shadow-sm ${
                showAddModal
                  ? "bg-slate-800 text-white border-slate-800"
                  : "bg-blue-600 hover:bg-blue-700 text-white border-blue-600"
              }`}
            >
              {showAddModal ? "Close Form" : "+ Add Custom Vehicle"}
            </button>
          </div>
        </div>

        {/* Collapsible Manual Vehicle Registration Form */}
        {showAddModal && (
          <form
            onSubmit={handleAddVehicle}
            className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3"
          >
            <div className="flex items-center justify-between border-b border-slate-200 pb-2">
              <span className="text-xs font-bold text-slate-800 uppercase font-mono">Register New Vehicle into Fleet</span>
              <span className="text-[11px] text-slate-400 font-mono">Enter manual parameters</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Vehicle ID</label>
                <input
                  type="text"
                  placeholder={`TRUCK_0${fleetVehicles.length + 1}`}
                  value={newVehicleId}
                  onChange={(e) => setNewVehicleId(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Driver / Label</label>
                <input
                  type="text"
                  placeholder={`Driver ${fleetVehicles.length + 1}`}
                  value={newVehicleName}
                  onChange={(e) => setNewVehicleName(e.target.value)}
                  className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Model</label>
                <select
                  value={newVehicleModel}
                  onChange={(e) => setNewVehicleModel(e.target.value)}
                  className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="Tata Ace EV (Mini Truck)">Tata Ace EV (Mini Truck)</option>
                  <option value="Mahindra Treo Zor (EV Cargo)">Mahindra Treo Zor (EV Cargo)</option>
                  <option value="Medium Delivery Truck">Medium Delivery Truck</option>
                  <option value="Electric Cargo Van">Electric Cargo Van</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Registration #</label>
                <input
                  type="text"
                  placeholder={`MH-12-EV-${1000 + fleetVehicles.length + 1}`}
                  value={newVehicleReg}
                  onChange={(e) => setNewVehicleReg(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={newVehicleLat}
                  onChange={(e) => setNewVehicleLat(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={newVehicleLon}
                  onChange={(e) => setNewVehicleLon(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fuel Level (%)</label>
                <input
                  type="number"
                  min="5"
                  max="100"
                  value={newVehicleFuel}
                  onChange={(e) => setNewVehicleFuel(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Payload Cap (kg)</label>
                <input
                  type="number"
                  step="100"
                  value={newVehicleCapacity}
                  onChange={(e) => setNewVehicleCapacity(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white transition shadow-sm"
              >
                Deploy Vehicle to Fleet
              </button>
            </div>
          </form>
        )}

        {/* Fleet Vehicles Strip: Interactive Pills */}
        <div className="pt-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 font-mono mb-2">
            <span>SELECT VEHICLE TO INSPECT / CONTROL:</span>
            <span className="text-slate-400">({fleetVehicles.length} deployed across Pune grid)</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {fleetVehicles.map((v) => {
              const isSelected = v.id === vehicleId;
              return (
                <div
                  key={v.id}
                  onClick={() => handleSelectVehicle(v.id)}
                  className={`group cursor-pointer px-3 py-2 rounded-xl text-xs transition-all flex items-center gap-2 border ${
                    isSelected
                      ? "bg-blue-50/80 border-blue-500 text-blue-900 shadow-sm ring-2 ring-blue-500/20 font-bold"
                      : "bg-slate-50/80 hover:bg-slate-100 border-slate-200 text-slate-700"
                  }`}
                >
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${isSelected ? "bg-blue-600 animate-pulse" : "bg-slate-400"}`} />
                  <div className="flex flex-col text-left">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono">{v.id}</span>
                      {isSelected && (
                        <span className="px-1.5 py-0.2 bg-blue-600 text-white rounded text-[9px] font-mono">ACTIVE</span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-500 font-normal">
                      {v.name} • {v.fuel}% fuel • {v.speed} km/h
                    </span>
                  </div>
                  {fleetVehicles.length > 1 && (
                    <button
                      type="button"
                      title="Remove vehicle"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveVehicle(v.id);
                      }}
                      className="ml-1 text-slate-400 hover:text-rose-600 p-0.5 rounded transition text-xs opacity-60 group-hover:opacity-100"
                    >
                      ✕
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 3. Live Interactive Map with Real-Time PPO Route Adaptation */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-2.5">
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
              Live Vehicle Path & PPO Route Adaptation Map
            </h3>
            <p className="text-xs text-slate-500">
              Vehicles continuously drive towards delivery destination. Route dynamically shifts in real time based on continuous PPO evaluation: <span className="text-emerald-700 font-semibold">Optimal Tour (Green)</span> ↔ <span className="text-amber-700 font-semibold">Reroute Detour (Amber)</span> ↔ <span className="text-rose-700 font-semibold">Emergency SOS (Red)</span>.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className={`text-[11px] font-mono px-2.5 py-1 rounded-lg font-bold border ${
              activePpoAction === "REROUTE"
                ? "bg-amber-50 text-amber-800 border-amber-300 animate-pulse"
                : activePpoAction === "REQUEST_ASSISTANCE"
                ? "bg-rose-50 text-rose-800 border-rose-300 animate-pulse"
                : "bg-emerald-50 text-emerald-800 border-emerald-300"
            }`}>
              Active Path: {activePpoAction === "REROUTE" ? "Detour Corridor" : activePpoAction === "REQUEST_ASSISTANCE" ? "Peer Rescue Detour" : "Direct On-Time Tour"}
            </span>
          </div>
        </div>

        {/* Autonomous Drive & PPO Stress-Test Control Bar */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsDriving(!isDriving)}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all shadow-sm flex items-center gap-2 ${
                isDriving
                  ? "bg-amber-600 hover:bg-amber-700 text-white animate-pulse"
                  : "bg-emerald-600 hover:bg-emerald-700 text-white"
              }`}
            >
              <span>{isDriving ? "⏸ Pause Autonomous Drive" : "▶ Start Autonomous Drive"}</span>
            </button>
            <button
              type="button"
              onClick={handleResetDrive}
              className="px-3 py-2 rounded-lg text-xs font-semibold bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 transition shadow-sm"
              title="Reset vehicle position to origin coordinates"
            >
              ↺ Reset to Start
            </button>
          </div>

          {/* Quick Real-Time Reroute Trigger */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-mono hidden sm:inline">PPO Stress Test:</span>
            <button
              type="button"
              onClick={() => setTrafficLevel(trafficLevel === "SEVERE" ? "NORMAL" : "SEVERE")}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition border shadow-sm ${
                trafficLevel === "SEVERE"
                  ? "bg-rose-100 hover:bg-rose-200 text-rose-800 border-rose-300"
                  : "bg-slate-200 hover:bg-amber-100 text-slate-800 border-slate-300"
              }`}
              title="Inject severe traffic to demonstrate immediate continuous PPO rerouting"
            >
              {trafficLevel === "SEVERE" ? "Clear Traffic Gridlock" : "Simulate Road Gridlock (Trigger PPO Reroute)"}
            </button>
          </div>

          <div className="text-xs font-mono text-slate-600 flex flex-wrap items-center gap-3">
            <span className="text-[11px] px-2 py-0.5 rounded font-bold font-mono bg-emerald-50 text-emerald-800 border border-emerald-200">
              {isRoadLoading ? "Fetching Road..." : `Road Snapped (${roadCoordinates.length > 0 ? `${roadCoordinates.length} pts` : "OSRM Direct"})`}
            </span>
            <span>
              <b>Status:</b>{" "}
              <span className={isDriving ? "text-emerald-700 font-bold" : "text-slate-500"}>
                {isDriving ? "DRIVING ALONG CORRIDOR" : "STANDING BY"}
              </span>
            </span>
            <span>
              <b>Step:</b> {driveStep}/50
            </span>
            <span>
              <b>Remaining:</b> {remainingDistanceKm} km
            </span>
          </div>
        </div>

        <div className="h-[420px] w-full">
          <SimulatorMap
            tripStartLat={tripStartLat}
            tripStartLon={tripStartLon}
            vehicleLat={latitude}
            vehicleLon={longitude}
            destLat={destLat}
            destLon={destLon}
            heading={heading}
            speedKmh={speedKmh}
            fuelLevel={fuelLevel}
            vehicleCondition={vehicleCondition}
            trafficLevel={trafficLevel}
            ppoAction={activePpoAction}
            peerCount={blePeerCount}
            vehicleId={vehicleId}
            allVehicles={fleetVehicles}
            roadCoordinates={roadCoordinates}
            detourCoordinates={detourRoadCoordinates}
            onSelectVehicle={handleSelectVehicle}
            onLocationSelect={({ lat, lon }) => {
              setTripStartLat(lat);
              setTripStartLon(lon);
              setLatitude(lat);
              setLongitude(lon);
              setDriveStep(0);
            }}
            onDestinationSelect={({ lat, lon }) => {
              setDestLat(lat);
              setDestLon(lon);
              setRemainingDistanceKm(calcHaversineKm(latitude, longitude, lat, lon));
              setDriveStep(0);
            }}
          />
        </div>
      </div>

      {/* 4. Main Grid: Manual Inputs Form (Left) + Live AI Response (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-6 items-start">
        {/* Left Column: Manual Form Controls */}
        <div className="space-y-4">
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
                  Manual Telemetry & Physical Parameters
                </h3>
                <p className="text-xs text-slate-500">Every input field below is fully editable in real time.</p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsDriving(!isDriving)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-sm ${
                    isDriving
                      ? "bg-amber-600 text-white animate-pulse"
                      : "bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300"
                  }`}
                >
                  <span>{isDriving ? "⏸ Pause Drive" : "▶ Start Drive"}</span>
                </button>
              </div>
            </div>

            {/* Vehicle Selection & Custom ID */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select Registered Vehicle
                </label>
                <select
                  value={vehicleId}
                  onChange={(e) => handleSelectVehicle(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  {fleetVehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.id} - {v.name} ({v.registration || v.model})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Or Custom Vehicle ID
                </label>
                <input
                  type="text"
                  value={vehicleId}
                  onChange={(e) => setVehicleId(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. PTR_MH12CE1047"
                />
              </div>
            </div>

            {/* 1. Vehicle Start Location (Toggle: Coordinates vs Location Name) */}
            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-800 uppercase font-mono">
                  Vehicle Start Location
                </span>
                <div className="flex items-center gap-2">
                  {/* Mode Toggle */}
                  <div className="flex items-center bg-slate-200/90 p-0.5 rounded-lg text-[10px] font-mono shadow-inner">
                    <button
                      type="button"
                      onClick={() => setStartInputMode("coords")}
                      className={`px-2 py-0.5 rounded-md transition font-semibold ${
                        startInputMode === "coords"
                          ? "bg-white text-blue-700 shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Coordinates
                    </button>
                    <button
                      type="button"
                      onClick={() => setStartInputMode("name")}
                      className={`px-2 py-0.5 rounded-md transition font-semibold ${
                        startInputMode === "name"
                          ? "bg-white text-blue-700 shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Location Name
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={handleUseBrowserGps}
                    className="px-2.5 py-1 text-[10px] font-mono bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg font-semibold hover:bg-emerald-100 transition shadow-xs"
                    title="Use current device GPS location"
                  >
                    My GPS
                  </button>
                </div>
              </div>

              {startInputMode === "coords" ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-mono text-slate-500 mb-0.5">Start Latitude</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={latitude}
                      onChange={(e) => setLatitude(parseFloat(e.target.value) || 0)}
                      className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      placeholder="18.5204"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-mono text-slate-500 mb-0.5">Start Longitude</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={longitude}
                      onChange={(e) => setLongitude(parseFloat(e.target.value) || 0)}
                      className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      placeholder="73.8567"
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={startLocationName}
                      onChange={(e) => setStartLocationName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleGeocodeLocation(startLocationName, true);
                        }
                      }}
                      placeholder="Type location name (e.g. Shivajinagar, Koregaon Park, FC Road)..."
                      className="flex-1 text-xs p-2 rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    />
                    <button
                      type="button"
                      disabled={isGeocodingStart}
                      onClick={() => handleGeocodeLocation(startLocationName, true)}
                      className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition shadow-xs disabled:opacity-60"
                    >
                      {isGeocodingStart ? "Locating..." : "Set Location"}
                    </button>
                  </div>
                  <div className="text-right text-[11px] font-mono text-slate-500">
                    Resolved Coordinates: <span className="font-semibold text-slate-800">{latitude}, {longitude}</span>
                  </div>
                </div>
              )}
            </div>

            {/* 2. Destination Target Location (Toggle: Coordinates vs Location Name) */}
            <div className="p-3.5 bg-emerald-50/60 rounded-xl border border-emerald-200 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-emerald-950 uppercase font-mono">
                  Destination Target Location
                </span>
                <div className="flex items-center gap-2">
                  {/* Mode Toggle */}
                  <div className="flex items-center bg-emerald-200/80 p-0.5 rounded-lg text-[10px] font-mono shadow-inner">
                    <button
                      type="button"
                      onClick={() => setDestInputMode("coords")}
                      className={`px-2 py-0.5 rounded-md transition font-semibold ${
                        destInputMode === "coords"
                          ? "bg-white text-emerald-800 shadow-xs"
                          : "text-emerald-900/70 hover:text-emerald-950"
                      }`}
                    >
                      Coordinates
                    </button>
                    <button
                      type="button"
                      onClick={() => setDestInputMode("name")}
                      className={`px-2 py-0.5 rounded-md transition font-semibold ${
                        destInputMode === "name"
                          ? "bg-white text-emerald-800 shadow-xs"
                          : "text-emerald-900/70 hover:text-emerald-950"
                      }`}
                    >
                      Location Name
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setDestLat(Number((latitude + 0.04).toFixed(4)));
                      setDestLon(Number((longitude + 0.04).toFixed(4)));
                      setDestLocationName("Offset Point (+5km)");
                    }}
                    className="px-2 py-0.5 text-[10px] font-mono bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 text-emerald-900 rounded-lg font-semibold transition"
                    title="Offset target ~5km north-east"
                  >
                    +5km Offset
                  </button>
                </div>
              </div>

              {destInputMode === "coords" ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-mono text-emerald-900 mb-0.5">
                      Destination Latitude
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={destLat}
                      onChange={(e) => setDestLat(parseFloat(e.target.value) || 0)}
                      className="w-full text-xs font-mono p-2 rounded-lg border border-emerald-300 bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                      placeholder="18.5912"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-mono text-emerald-900 mb-0.5">
                      Destination Longitude
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={destLon}
                      onChange={(e) => setDestLon(parseFloat(e.target.value) || 0)}
                      className="w-full text-xs font-mono p-2 rounded-lg border border-emerald-300 bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                      placeholder="73.7389"
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={destLocationName}
                      onChange={(e) => setDestLocationName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleGeocodeLocation(destLocationName, false);
                        }
                      }}
                      placeholder="Type destination name (e.g. Hinjawadi, Magarpatta, Pune Airport)..."
                      className="flex-1 text-xs p-2 rounded-lg border border-emerald-300 bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    />
                    <button
                      type="button"
                      disabled={isGeocodingDest}
                      onClick={() => handleGeocodeLocation(destLocationName, false)}
                      className="px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold transition shadow-xs disabled:opacity-60"
                    >
                      {isGeocodingDest ? "Locating..." : "Set Destination"}
                    </button>
                  </div>
                  <div className="text-right text-[11px] font-mono text-emerald-800">
                    Resolved Coordinates: <span className="font-semibold text-emerald-950">{destLat}, {destLon}</span>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] font-mono text-emerald-900 border-t border-emerald-200/60">
                <span>
                  Direct Air Distance: <strong>{calcHaversineKm(latitude, longitude, destLat, destLon)} km</strong>
                </span>
                <button
                  type="button"
                  onClick={() => setRemainingDistanceKm(calcHaversineKm(latitude, longitude, destLat, destLon))}
                  className="px-2.5 py-1 text-[10px] bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-sans font-semibold transition shadow-xs"
                  title="Copy calculated distance into Remaining Distance field"
                >
                  Sync Remaining Dist
                </button>
              </div>
            </div>

            {/* Speed & Distance */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                  <span>Speed</span>
                  <span className="font-mono text-blue-600 font-bold">{speedKmh} km/h</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="120"
                  step="1"
                  value={speedKmh}
                  onChange={(e) => setSpeedKmh(parseFloat(e.target.value))}
                  className="w-full accent-blue-600"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                  <span>Remaining Route Distance</span>
                  <span className="font-mono text-blue-600 font-bold">{remainingDistanceKm} km</span>
                </div>
                <input
                  type="number"
                  min="0.1"
                  max="150"
                  step="0.5"
                  value={remainingDistanceKm}
                  onChange={(e) => setRemainingDistanceKm(parseFloat(e.target.value) || 0.1)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300"
                />
              </div>
            </div>

            {/* Fuel & Battery Level */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                  <span>Fuel / Battery Level</span>
                  <span className={`font-mono font-bold ${fuelLevel < 20 ? "text-red-600" : "text-emerald-600"}`}>
                    {fuelLevel}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={fuelLevel}
                  onChange={(e) => setFuelLevel(parseFloat(e.target.value))}
                  className={`w-full ${fuelLevel < 20 ? "accent-red-600" : "accent-emerald-600"}`}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tank / Battery Capacity (Liters or kWh)
                </label>
                <input
                  type="number"
                  min="10"
                  max="500"
                  step="5"
                  value={fuelCapacityLiters}
                  onChange={(e) => setFuelCapacityLiters(parseFloat(e.target.value) || 60)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300"
                />
              </div>
            </div>

            {/* Vehicle Mechanical Condition & Heading */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                  <span>Vehicle Condition</span>
                  <span className={`font-mono font-bold ${vehicleCondition < 0.3 ? "text-red-600" : "text-slate-800"}`}>
                    {vehicleCondition.toFixed(2)} {vehicleCondition < 0.3 ? "(Breakdown)" : "(Healthy)"}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.05"
                  max="1.0"
                  step="0.05"
                  value={vehicleCondition}
                  onChange={(e) => setVehicleCondition(parseFloat(e.target.value))}
                  className={`w-full ${vehicleCondition < 0.3 ? "accent-red-600" : "accent-blue-600"}`}
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                  <span>Compass Heading</span>
                  <span className="font-mono text-slate-800 font-bold">{heading}°</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="360"
                  step="5"
                  value={heading}
                  onChange={(e) => setHeading(parseFloat(e.target.value))}
                  className="w-full accent-slate-600"
                />
              </div>
            </div>

            {/* Environment, Traffic & Network */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Traffic Friction
                </label>
                <select
                  value={trafficLevel}
                  onChange={(e) => setTrafficLevel(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white"
                >
                  <option value="NORMAL">NORMAL (Free Flow)</option>
                  <option value="HEAVY">HEAVY (Moderate Slowdown)</option>
                  <option value="SEVERE">SEVERE (Gridlock)</option>
                  <option value="BLOCKED">BLOCKED (Road Impassable)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Cloud Connectivity
                </label>
                <select
                  value={internetStatus}
                  onChange={(e) => setInternetStatus(e.target.value)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-white"
                >
                  <option value="ONLINE">ONLINE (Cloud Mode)</option>
                  <option value="OFFLINE">OFFLINE (Mesh / Edge Mode)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  BLE Mesh Peers in Range
                </label>
                <input
                  type="number"
                  min="0"
                  max="15"
                  value={blePeerCount}
                  onChange={(e) => setBlePeerCount(parseInt(e.target.value, 10) || 0)}
                  className="w-full text-xs font-mono p-2 rounded-lg border border-slate-300"
                />
              </div>
            </div>

            {/* Action Execution Button */}
            <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-3">
              {activeTab === "telemetry" && (
                <button
                  type="button"
                  onClick={handleSendTelemetry}
                  disabled={isLoading}
                  className="flex-1 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition shadow-sm flex items-center justify-center gap-2"
                >
                  <span>{isLoading ? "Transmitting..." : "Ingest Telemetry Ping"}</span>
                </button>
              )}

              {activeTab === "intelligence" && (
                <div className="flex-1 flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={handleEvaluateIntelligence}
                    disabled={isLoading}
                    className="w-full py-3 px-4 rounded-xl bg-purple-600 hover:bg-purple-700 active:bg-purple-800 disabled:opacity-60 text-white text-xs font-bold transition shadow-sm flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {isLoading ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                        </svg>
                        <span>Evaluating Neural Policy & Road Routes...</span>
                      </>
                    ) : (
                      <>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                        </svg>
                        <span>Run Transformer + PPO Evaluator</span>
                      </>
                    )}
                  </button>

                  {evaluatorFeedback && (
                    <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 flex items-start gap-2.5 shadow-xs">
                      <span className="w-2.5 h-2.5 rounded-full bg-purple-600 mt-1 flex-shrink-0 animate-ping" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between font-mono text-xs">
                          <span className="font-bold text-purple-950 flex items-center gap-1.5">
                            <span>Decision:</span>
                            <span className="px-2 py-0.5 rounded bg-purple-200 text-purple-900 font-bold">
                              {evaluatorFeedback.action}
                            </span>
                            <span className="text-[10px] text-purple-600 font-normal">
                              (Code {evaluatorFeedback.actionCode})
                            </span>
                          </span>
                          <span className="text-slate-500 text-[11px]">{evaluatorFeedback.latencyMs}ms</span>
                        </div>
                        <p className="text-purple-800 text-xs mt-1 leading-snug">
                          {evaluatorFeedback.reason}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === "mesh" && (
                <button
                  type="button"
                  onClick={handleSendMeshRelay}
                  disabled={isLoading}
                  className="flex-1 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition shadow-sm flex items-center justify-center gap-2"
                >
                  <span>{isLoading ? "Relaying..." : "Broadcast BLE Relay Packet"}</span>
                </button>
              )}
            </div>

            {/* Error Display */}
            {errorMessage && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 font-mono">
                Error: {errorMessage}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Continuous PPO Decision Stream & Telemetry Log */}
        <div className="space-y-4">
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
                  Autonomous PPO Decision State
                </h3>
                <p className="text-xs text-slate-500 font-mono">
                  {isDriving ? "Continuous neural inference streaming active" : "Standing by for autonomous mission"}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-mono px-2.5 py-1 rounded font-bold border flex items-center gap-1.5 ${
                  isDriving ? "bg-emerald-50 text-emerald-800 border-emerald-300 animate-pulse" : "bg-slate-100 text-slate-600 border-slate-200"
                }`}>
                  <span className={`w-2 h-2 rounded-full ${isDriving ? "bg-emerald-500" : "bg-slate-400"}`} />
                  {isDriving ? "LIVE INFERENCE" : "PAUSED"}
                </span>
              </div>
            </div>

            {/* PPO Active Recommendation Hero Card */}
            <div
              className={`p-4 rounded-xl border flex flex-col gap-2 transition-all ${
                activePpoAction === "KEEP_ROUTE"
                  ? "bg-emerald-50 border-emerald-200 text-emerald-950"
                  : activePpoAction === "REROUTE"
                  ? "bg-amber-50 border-amber-300 text-amber-950 ring-2 ring-amber-500/20 shadow-sm"
                  : "bg-red-50 border-red-200 text-red-950"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-3 h-3 rounded-full ${
                    activePpoAction === "KEEP_ROUTE" ? "bg-emerald-500" : activePpoAction === "REROUTE" ? "bg-amber-500 animate-ping" : "bg-rose-500 animate-bounce"
                  }`} />
                  <span className="text-base font-bold tracking-tight">
                    {activePpoAction}
                  </span>
                </div>

                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-white/80 border border-current">
                  Action Code: {activePpoAction === "REROUTE" ? "0 (ASSIGN_BEST_ORDER / REROUTE)" : activePpoAction === "REQUEST_ASSISTANCE" ? "1 (RESCUE_DISPATCH)" : "4 (HOLD_OR_CONTINUE)"}
                </span>
              </div>

              <p className="text-xs leading-relaxed font-mono">
                {ppoResult?.reason || (
                  activePpoAction === "REROUTE"
                    ? "Severe corridor degradation detected. PPO policy dynamically engaging bypass detour."
                    : "Current route optimal, on schedule, and physically feasible."
                )}
              </p>
            </div>

            {/* Transformer Trajectory Trends */}
            {transformerResult && (
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center text-slate-700 font-bold border-b border-slate-200 pb-1.5">
                  <span>Trajectory Temporal Transformer</span>
                  <span className="text-blue-700">
                    Memory Buffer: {transformerResult.steps_in_memory || 3}/6 Steps
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                  <div className="p-2 rounded bg-white border border-slate-200">
                    <div className="text-slate-400">Delay Risk</div>
                    <div className="text-sm font-bold text-slate-800">
                      {transformerResult.trends?.delay_risk !== undefined
                        ? transformerResult.trends.delay_risk.toFixed(3)
                        : "0.016"}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-white border border-slate-200">
                    <div className="text-slate-400">Reroute Desirability</div>
                    <div className="text-sm font-bold text-slate-800">
                      {transformerResult.trends?.reroute_desirability !== undefined
                        ? transformerResult.trends.reroute_desirability.toFixed(3)
                        : "-0.086"}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Fuel & Mechanical Feasibility */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 font-mono text-xs">
              <div className="text-slate-700 font-bold border-b border-slate-200 pb-1 flex justify-between">
                <span>Fuel Feasibility Assessment</span>
                <span className={fuelLevel < 10 ? "text-red-600 font-bold" : "text-emerald-700 font-bold"}>
                  {fuelLevel < 10 ? "Critical Low Fuel" : "Fuel Feasible"}
                </span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Current Fuel:</span>
                <span className="font-bold">{fuelLevel}% ({((fuelLevel / 100) * fuelCapacityLiters).toFixed(1)} L)</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Distance Remaining:</span>
                <span className="font-bold">{remainingDistanceKm} km</span>
              </div>
            </div>

            {/* Quick Navigation Links */}
            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-blue-600">
              <Link href="/partner" className="hover:underline flex items-center gap-1">
                <span>View on Rider Cockpit</span>
                <span>→</span>
              </Link>
              <Link href="/fleet" className="hover:underline flex items-center gap-1">
                <span>View on Fleet Telematics</span>
                <span>→</span>
              </Link>
            </div>
          </div>

          {/* Continuous PPO Decision & Telemetry Stream Log */}
          <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-900 text-slate-100 font-mono text-xs shadow-sm">
            <div className="p-3 bg-slate-950 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${isDriving ? "bg-emerald-400 animate-ping" : "bg-slate-400"}`} />
                <span className="font-bold text-slate-200 text-xs uppercase tracking-wider">
                  Continuous PPO Decision Stream
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300 font-bold border border-slate-700">
                  {decisionLogs.length} Decisions Logged
                </span>
              </div>

              <div className="flex items-center gap-1.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setLogFilter("ALL")}
                  className={`px-2 py-1 rounded transition ${
                    logFilter === "ALL"
                      ? "bg-blue-600 text-white font-bold"
                      : "bg-slate-800 hover:bg-slate-700 text-slate-400"
                  }`}
                >
                  All
                </button>
                <button
                  type="button"
                  onClick={() => setLogFilter("REROUTE_ONLY")}
                  className={`px-2 py-1 rounded transition ${
                    logFilter === "REROUTE_ONLY"
                      ? "bg-amber-600 text-white font-bold"
                      : "bg-slate-800 hover:bg-slate-700 text-slate-400"
                  }`}
                >
                  Reroutes Only
                </button>
                <button
                  type="button"
                  onClick={() => setDecisionLogs([])}
                  className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
                  title="Clear log feed"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Scrollable Decision Stream Feed */}
            <div className="p-3 space-y-2 max-h-[380px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
              {decisionLogs
                .filter((log) => (logFilter === "REROUTE_ONLY" ? log.action === "REROUTE" : true))
                .map((log, idx) => {
                  const isReroute = log.action === "REROUTE";
                  const isEmergency = log.action === "REQUEST_ASSISTANCE";
                  const isArrived = log.action === "DESTINATION_ARRIVED";

                  return (
                    <div
                      key={log.id}
                      className={`p-2.5 rounded-lg border transition-all text-[11px] ${
                        idx === 0
                          ? isReroute
                            ? "bg-amber-950/70 border-amber-500/80 ring-1 ring-amber-500/40"
                            : isEmergency
                            ? "bg-rose-950/70 border-rose-500/80 ring-1 ring-rose-500/40"
                            : "bg-slate-800/90 border-slate-700 shadow-sm"
                          : isReroute
                          ? "bg-amber-950/30 border-amber-700/50 text-amber-200"
                          : isEmergency
                          ? "bg-rose-950/30 border-rose-700/50 text-rose-200"
                          : "bg-slate-950/50 border-slate-800/80 text-slate-300"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400 text-[10px]">[{log.time}]</span>
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-bold text-[10px]">
                            Step #{log.step}
                          </span>
                          <span className="text-slate-400 text-[10px]">{log.vehicleId}</span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded font-bold text-[10px] uppercase border ${
                              isReroute
                                ? "bg-amber-500/20 text-amber-300 border-amber-500/50 animate-pulse"
                                : isEmergency
                                ? "bg-rose-500/20 text-rose-300 border-rose-500/50"
                                : isArrived
                                ? "bg-blue-500/20 text-blue-300 border-blue-500/50"
                                : "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                            }`}
                          >
                            {log.action}
                          </span>
                          <span className="text-[10px] text-slate-500">{log.latencyMs}ms</span>
                        </div>
                      </div>

                      <p className="text-slate-200 leading-snug font-sans text-xs">
                        {log.reason}
                      </p>

                      <div className="mt-1.5 pt-1.5 border-t border-slate-800/60 flex flex-wrap items-center justify-between text-[10px] text-slate-400">
                        <span>
                          GPS: {Number(log.lat).toFixed(4)}, {Number(log.lon).toFixed(4)}
                        </span>
                        <span>Dist Left: {log.distanceRemaining} km</span>
                        <span>
                          Traffic:{" "}
                          <span
                            className={
                              log.trafficLevel === "SEVERE"
                                ? "text-rose-400 font-bold"
                                : log.trafficLevel === "HEAVY"
                                ? "text-amber-400"
                                : "text-emerald-400"
                            }
                          >
                            {log.trafficLevel}
                          </span>
                        </span>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

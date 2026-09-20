"use client";

import { useState, useEffect, useCallback, useRef } from "react";

function getStateSignature(s) {
  if (!s) return "";
  const sim = s.simulation || {};
  const perf = s.performance || {};
  const vehSig = (s.vehicles || []).map(v => `${v.id}:${v.status}:${v.current_load}:${v.speed_kmh}:${v.location?.x || v.x || ""}:${v.location?.y || v.y || ""}`).join("|");
  const ordSig = (s.orders || []).map(o => `${o.id}:${o.status}:${o.assigned_vehicle || ""}`).join("|");
  return `${sim.status}-${sim.time}-${vehSig}-${ordSig}-${perf.delivered}-${perf.reassigned}-${(s.incidents || []).length}-${(s.delivery_partners || []).length}`;
}

// Module-level persistent singleton store across all Next.js client-side page transitions
let globalState = null;
let globalConnectionStatus = "CONNECTING";
let globalEventSource = null;
let globalLastSig = "";
const subscribers = new Set();

function broadcast(newState, newStatus) {
  if (newState !== undefined) globalState = newState;
  if (newStatus !== undefined) globalConnectionStatus = newStatus;
  subscribers.forEach((cb) => {
    try {
      cb(globalState, globalConnectionStatus);
    } catch (e) {
      console.error("Subscriber update error:", e);
    }
  });
}

async function fetchGlobalState() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    globalLastSig = getStateSignature(data);
    broadcast(data, "CONNECTED");
    return data;
  } catch (err) {
    if (!globalState) {
      broadcast(undefined, "OFFLINE");
    }
    return null;
  }
}

function initSingletonSSE() {
  if (typeof window === "undefined" || globalEventSource) return;

  try {
    const es = new EventSource("/api/stream");
    globalEventSource = es;

    es.onopen = () => {
      broadcast(undefined, "CONNECTED");
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const sig = getStateSignature(data);
        if (sig && sig === globalLastSig) {
          return;
        }
        globalLastSig = sig;
        broadcast(data, "CONNECTED");
      } catch (e) {
        console.error("SSE parse error", e);
      }
    };

    es.onerror = () => {
      if (globalEventSource) {
        globalEventSource.close();
        globalEventSource = null;
      }
      setTimeout(() => {
        if (typeof window !== "undefined") {
          fetchGlobalState().then(initSingletonSSE);
        }
      }, 3000);
    };
  } catch (err) {
    console.warn("SSE singleton error:", err);
  }
}

// Automatically start fetching and streaming as soon as module loads on client
if (typeof window !== "undefined") {
  fetchGlobalState().then(initSingletonSSE);
}

export function useDashboardState() {
  // Immediately initialize state from the shared global cache (0ms lag, no loading spinner)
  const [state, setState] = useState(globalState);
  const [connectionStatus, setConnectionStatus] = useState(globalConnectionStatus);
  const [error, setError] = useState(null);

  useEffect(() => {
    // If globalState is available and local state isn't in sync, sync immediately
    if (globalState && state !== globalState) {
      setState(globalState);
      setConnectionStatus(globalConnectionStatus);
    } else if (!globalState) {
      fetchGlobalState();
    }
    initSingletonSSE();

    const listener = (s, status) => {
      setState(s);
      setConnectionStatus(status);
    };
    subscribers.add(listener);

    return () => {
      subscribers.delete(listener);
    };
  }, [state]);

  // Simulation Control Actions
  const start = useCallback(async () => {
    try {
      await fetch("/api/simulation/start", { method: "POST" });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  const pause = useCallback(async () => {
    try {
      await fetch("/api/simulation/pause", { method: "POST" });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  const step = useCallback(async () => {
    try {
      const res = await fetch("/api/simulation/step", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        globalLastSig = getStateSignature(data);
        broadcast(data, "CONNECTED");
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const reset = useCallback(async (params = {}) => {
    try {
      const res = await fetch("/api/simulation/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (res.ok) {
        const data = await res.json();
        globalLastSig = getStateSignature(data);
        broadcast(data, "CONNECTED");
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const setSpeed = useCallback(async (speedValue) => {
    try {
      await fetch("/api/simulation/speed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speed: speedValue }),
      });
    } catch (e) {
      console.error(e);
    }
  }, []);

  const breakVehicle = useCallback(async (vehicleId = null) => {
    try {
      await fetch("/api/disruption/break", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vehicle_id: vehicleId }),
      });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  const repairVehicle = useCallback(async (vehicleId = null) => {
    try {
      const res = await fetch("/api/disruption/repair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vehicle_id: vehicleId }),
      });
      const data = await res.json();
      await fetchGlobalState();
      return data;
    } catch (e) {
      console.error(e);
      return { success: false, error: e.message };
    }
  }, []);

  const toggleCloud = useCallback(async (enabled = null) => {
    try {
      await fetch("/api/disruption/cloud", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  const injectTraffic = useCallback(async (u = null, v = null, level = "SEVERE") => {
    try {
      await fetch("/api/disruption/traffic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ u, v, level }),
      });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  const injectDemand = useCallback(async (zone = "North-East") => {
    try {
      await fetch("/api/disruption/demand", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zone }),
      });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  const injectCombined = useCallback(async () => {
    try {
      await fetch("/api/disruption/combined", { method: "POST" });
      await fetchGlobalState();
    } catch (e) {
      console.error(e);
    }
  }, []);

  // Task Allocation & Completion
  const allocateTask = useCallback(async (orderId, vehicleId) => {
    try {
      const res = await fetch("/api/task/allocate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId, vehicle_id: vehicleId }),
      });
      const data = await res.json();
      await fetchGlobalState();
      return data;
    } catch (e) {
      console.error("Task allocation error:", e);
      return { success: false, error: e.message };
    }
  }, []);

  const completeTask = useCallback(async (orderId, vehicleId = null) => {
    try {
      const res = await fetch("/api/task/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId, vehicle_id: vehicleId }),
      });
      const data = await res.json();
      await fetchGlobalState();
      return data;
    } catch (e) {
      console.error("Task completion error:", e);
      return { success: false, error: e.message };
    }
  }, []);

  return {
    state,
    connectionStatus,
    error,
    start,
    pause,
    step,
    reset,
    setSpeed,
    breakVehicle,
    repairVehicle,
    toggleCloud,
    injectTraffic,
    injectDemand,
    injectCombined,
    allocateTask,
    completeTask,
    refresh: fetchGlobalState,
  };
}

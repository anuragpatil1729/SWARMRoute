"use client";

import { useState, useEffect, useCallback, useRef } from "react";

export function useDashboardState() {
  const [state, setState] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("CONNECTING"); // CONNECTED, CONNECTING, OFFLINE
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);
  const pollingTimerRef = useRef(null);

  // Direct fetch fallback helper
  const fetchState = useCallback(async () => {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setState(data);
      setConnectionStatus("CONNECTED");
      setError(null);
    } catch (err) {
      setConnectionStatus("OFFLINE");
      setError(err.message);
    }
  }, []);

  // Connect to SSE stream
  useEffect(() => {
    let isMounted = true;

    function connectSSE() {
      if (typeof window === "undefined") return;

      try {
        const es = new EventSource("/api/stream");
        eventSourceRef.current = es;

        es.onopen = () => {
          if (isMounted) {
            setConnectionStatus("CONNECTED");
            setError(null);
          }
        };

        es.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            setState(data);
            setConnectionStatus("CONNECTED");
          } catch (e) {
            console.error("SSE parse error", e);
          }
        };

        es.onerror = () => {
          if (!isMounted) return;
          setConnectionStatus("OFFLINE");
          es.close();

          // Fallback to polling while offline
          if (!pollingTimerRef.current) {
            pollingTimerRef.current = setInterval(fetchState, 1500);
          }
          // Attempt SSE reconnection in 4 seconds
          setTimeout(() => {
            if (isMounted) {
              if (pollingTimerRef.current) {
                clearInterval(pollingTimerRef.current);
                pollingTimerRef.current = null;
              }
              connectSSE();
            }
          }, 4000);
        };
      } catch (err) {
        setConnectionStatus("OFFLINE");
        setError(err.message);
      }
    }

    // Initial fetch to get state immediately
    fetchState().then(() => {
      connectSSE();
    });

    return () => {
      isMounted = false;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, [fetchState]);

  // Simulation Control Actions
  const start = useCallback(async () => {
    try {
      await fetch("/api/simulation/start", { method: "POST" });
      await fetchState();
    } catch (e) {
      console.error(e);
    }
  }, [fetchState]);

  const pause = useCallback(async () => {
    try {
      await fetch("/api/simulation/pause", { method: "POST" });
      await fetchState();
    } catch (e) {
      console.error(e);
    }
  }, [fetchState]);

  const step = useCallback(async () => {
    try {
      const res = await fetch("/api/simulation/step", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setState(data);
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const reset = useCallback(
    async (params = {}) => {
      try {
        const res = await fetch("/api/simulation/reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
        });
        if (res.ok) {
          const data = await res.json();
          setState(data);
        }
      } catch (e) {
        console.error(e);
      }
    },
    []
  );

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

  // Disruption Injections
  const breakVehicle = useCallback(
    async (vehicleId = null) => {
      try {
        await fetch("/api/disruption/break", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ vehicle_id: vehicleId }),
        });
        await fetchState();
      } catch (e) {
        console.error(e);
      }
    },
    [fetchState]
  );

  const toggleCloud = useCallback(
    async (enabled = null) => {
      try {
        await fetch("/api/disruption/cloud", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
        await fetchState();
      } catch (e) {
        console.error(e);
      }
    },
    [fetchState]
  );

  const injectTraffic = useCallback(
    async (u = null, v = null, level = "SEVERE") => {
      try {
        await fetch("/api/disruption/traffic", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ u, v, level }),
        });
        await fetchState();
      } catch (e) {
        console.error(e);
      }
    },
    [fetchState]
  );

  const injectDemand = useCallback(
    async (zone = "North-East") => {
      try {
        await fetch("/api/disruption/demand", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ zone }),
        });
        await fetchState();
      } catch (e) {
        console.error(e);
      }
    },
    [fetchState]
  );

  const injectCombined = useCallback(async () => {
    try {
      await fetch("/api/disruption/combined", { method: "POST" });
      await fetchState();
    } catch (e) {
      console.error(e);
    }
  }, [fetchState]);

  // Task Allocation & Completion
  const allocateTask = useCallback(
    async (orderId, vehicleId) => {
      try {
        const res = await fetch("/api/task/allocate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ order_id: orderId, vehicle_id: vehicleId }),
        });
        const data = await res.json();
        await fetchState();
        return data;
      } catch (e) {
        console.error("Task allocation error:", e);
        return { success: false, error: e.message };
      }
    },
    [fetchState]
  );

  const completeTask = useCallback(
    async (orderId, vehicleId = null) => {
      try {
        const res = await fetch("/api/task/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ order_id: orderId, vehicle_id: vehicleId }),
        });
        const data = await res.json();
        await fetchState();
        return data;
      } catch (e) {
        console.error("Task completion error:", e);
        return { success: false, error: e.message };
      }
    },
    [fetchState]
  );

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
    toggleCloud,
    injectTraffic,
    injectDemand,
    injectCombined,
    allocateTask,
    completeTask,
    refresh: fetchState,
  };
}


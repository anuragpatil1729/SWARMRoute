"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import OpenStreetMap from "../../components/OpenStreetMap";
import Stat from "../../components/Stat";
import Section from "../../components/Section";
import { useDashboardState } from "../../lib/useDashboardState";
import { useAuth } from "../../lib/AuthContext";

export default function DeliveryPartnerCockpit() {
  const { user, profile, role } = useAuth();
  const {
    state,
    connectionStatus,
    completeTask,
    breakVehicle,
    repairVehicle,
    start,
    pause,
    step,
  } = useDashboardState();

  const [selectedPartnerId, setSelectedPartnerId] = useState(null);
  const [actionFeedback, setActionFeedback] = useState(null);
  const [loadingOrderId, setLoadingOrderId] = useState(null);
  const [isSosLoading, setIsSosLoading] = useState(false);

  // Sync selected partner with logged-in user's partner profile if available
  useEffect(() => {
    if (profile?.partner_id) {
      setSelectedPartnerId(profile.partner_id);
    } else if (!selectedPartnerId && state?.delivery_partners?.length > 0) {
      setSelectedPartnerId(state.delivery_partners[0].id);
    } else if (!selectedPartnerId && state?.vehicles?.length > 0) {
      setSelectedPartnerId(state.vehicles[0].id);
    }
  }, [profile, state]);

  const [requestingOrderId, setRequestingOrderId] = useState(null);
  const [activeTab, setActiveTab] = useState("available"); // "available" or "my_tasks"
  const [gpsActive, setGpsActive] = useState(false);
  const [gpsCoords, setGpsCoords] = useState(null);
  const [chatText, setChatText] = useState("");
  const [sendingChat, setSendingChat] = useState(false);
  const [recentMeshChats, setRecentMeshChats] = useState([]);

  useEffect(() => {
    fetch("/api/simulation/mesh/chat-history")
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setRecentMeshChats(data);
      })
      .catch(() => {});
  }, [state]);

  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">COCKPIT OFFLINE</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            Please make sure the SWARMRoute backend service is running at <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">http://127.0.0.1:8000</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8 max-w-md mx-auto">
          <div className="font-mono text-xs text-slate-400">Loading Telemetry</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO RIDER COCKPIT</h2>
          <p className="text-xs text-slate-500 mt-2">Synchronizing live GIS routes and delivery tasks...</p>
        </div>
      </div>
    );
  }

  const {
    simulation,
    vehicles = [],
    orders = [],
    map: mapData,
    traffic,
    mesh,
  } = state;

  // Dynamically load partner profiles from Supabase state or active fleet telemetry
  const partnerProfiles = (state.delivery_partners && state.delivery_partners.length > 0)
    ? state.delivery_partners
    : (vehicles.map((v) => ({
        id: v.id,
        name: v.partner_name || v.id,
        phone: v.partner_phone || "—",
        vehicle_model: v.vehicle_model || "Electric Fleet Vehicle",
        registration: v.registration || v.id,
        hub: v.hub || `${state?.simulation?.city || "Operations"} Hub`,
        city: v.city || state?.simulation?.city || "Operations",
        rating: v.rating ?? null,
        avatar: v.avatar || "🛵",
      })));

  const isDeliveryPartner = role === "partner";
  const partnerCity = profile?.city || user?.user_metadata?.city || (typeof window !== "undefined" ? localStorage.getItem("swarm_registered_city") : null) || state?.simulation?.city || "Operations";
  const partnerName = profile?.full_name || user?.user_metadata?.full_name || "Delivery Partner";
  const partnerVehicle = profile?.vehicle_model || user?.user_metadata?.vehicle_model || "Electric Fleet Vehicle";
  const partnerPlate = profile?.registration || user?.user_metadata?.registration || "MH-01-EV-2024";
  const partnerHub = profile?.hub || user?.user_metadata?.hub || `${partnerCity} Hub`;
  const partnerId = profile?.partner_id || profile?.vehicle_id || user?.user_metadata?.partner_id || (profile?.id ? `DP_${profile.id.slice(0, 6)}` : "PARTNER_01");

  const fallbackPartner = {
    id: partnerId,
    name: partnerName,
    phone: profile?.phone || user?.user_metadata?.phone || "—",
    vehicle_model: partnerVehicle,
    registration: partnerPlate,
    hub: partnerHub,
    city: partnerCity,
    avatar: "🛵",
    rating: profile?.rating ?? 5.0,
  };

  const currentPartner = isDeliveryPartner
    ? fallbackPartner
    : (partnerProfiles.find((p) => p.id === (selectedPartnerId || partnerProfiles[0]?.id)) || fallbackPartner);

  const activeId = currentPartner.id;
  const currentVehicle = vehicles.find((v) => 
    v.id === activeId || 
    (currentPartner.registration && v.registration === currentPartner.registration) ||
    (v.partner_name && currentPartner.name && v.partner_name.toLowerCase().includes(currentPartner.name.toLowerCase()))
  ) || (isDeliveryPartner && vehicles.length > 0 ? vehicles[0] : null);

  // Filter orders assigned to this rider (by partner ID, vehicle ID, registration, or partner name)
  const myOrders = orders.filter((o) => {
    if (!o.assigned_vehicle) return false;
    return (
      o.assigned_vehicle === activeId ||
      o.assigned_vehicle === currentPartner.id ||
      (currentPartner.registration && o.assigned_vehicle === currentPartner.registration) ||
      (currentVehicle && o.assigned_vehicle === currentVehicle.id) ||
      (currentPartner.name && o.assigned_partner && o.assigned_partner.toLowerCase().includes(currentPartner.name.toLowerCase()))
    );
  });
  const completedCount = myOrders.filter((o) => o.status === "DELIVERED").length;
  const pendingOrders = myOrders.filter((o) => o.status !== "DELIVERED");
  const isBroken = currentVehicle?.status === "BROKEN_DOWN";

  const handleCompleteOrder = async (orderId) => {
    setLoadingOrderId(orderId);
    const res = await completeTask(orderId, activeId);
    setLoadingOrderId(null);
    if (res && res.success) {
      setActionFeedback({ success: true, msg: `Order ${orderId} successfully delivered! Earnings credited.` });
    } else {
      setActionFeedback({ success: false, msg: res?.error || "Failed to complete delivery." });
    }
    setTimeout(() => setActionFeedback(null), 5000);
  };

  const handleSos = async () => {
    setIsSosLoading(true);
    const res = await breakVehicle(activeId);
    setIsSosLoading(false);
    setActionFeedback({
      success: false,
      msg: `🚨 EMERGENCY SOS BROADCASTED! P2P Swarm mesh initiated peer contract-net auction for pending parcels.`,
    });
    setTimeout(() => setActionFeedback(null), 8000);
  };

  const handleClearSos = async () => {
    setIsSosLoading(true);
    const res = await repairVehicle(activeId);
    setIsSosLoading(false);
    if (res && res.success) {
      setActionFeedback({
        success: true,
        msg: `✅ Vehicle repaired! SOS cleared and operational status restored to IDLE.`,
      });
    } else {
      setActionFeedback({
        success: false,
        msg: res?.error || "Could not clear SOS.",
      });
    }
    setTimeout(() => setActionFeedback(null), 5000);
  };

  const handleToggleGps = () => {
    if (typeof window === "undefined" || !navigator.geolocation) {
      setActionFeedback({ success: false, msg: "Geolocation not supported in this browser." });
      return;
    }
    if (gpsActive) {
      setGpsActive(false);
      setActionFeedback({ success: true, msg: "Switched back to fleet simulation route coordinates." });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setGpsActive(true);
        const { latitude, longitude, speed, heading, accuracy } = pos.coords;
        setGpsCoords({ lat: latitude, lon: longitude, accuracy });
        try {
          await fetch("/api/v1/driver/telemetry", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              vehicle_id: activeId,
              latitude,
              longitude,
              speed_kmh: speed ? speed * 3.6 : 0,
              heading: heading || 0,
              accuracy: accuracy || 5.0,
              fuel_level: 100.0,
              vehicle_condition: 1.0,
              internet_status: "ONLINE",
            }),
          });
          setActionFeedback({
            success: true,
            msg: `📍 Real Device GPS Synced: ${latitude.toFixed(4)}, ${longitude.toFixed(4)}`,
          });
        } catch (e) {
          setActionFeedback({ success: true, msg: `Device GPS captured (${latitude.toFixed(4)}, ${longitude.toFixed(4)})` });
        }
      },
      (err) => {
        setActionFeedback({
          success: false,
          msg: `Location permission needed: ${err.message}. Over local IP, enable location in browser settings.`,
        });
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const handleSendMeshChat = async (presetText) => {
    const text = typeof presetText === "string" ? presetText : chatText;
    if (!text || !text.trim()) return;
    setSendingChat(true);
    try {
      const res = await fetch("/api/simulation/mesh/send-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: activeId,
          receiver: "BROADCAST",
          message: text.trim(),
        }),
      });
      const data = await res.json();
      if (data.success) {
        setChatText("");
        setActionFeedback({
          success: true,
          msg: `📡 Mesh Packet broadcasted (${data.record?.hop_count || 1} hops · ${data.record?.latency_ms || 35}ms)!`,
        });
        const chRes = await fetch("/api/simulation/mesh/chat-history");
        const chData = await chRes.json();
        if (Array.isArray(chData)) setRecentMeshChats(chData);
      }
    } catch (e) {
      setActionFeedback({ success: false, msg: "Failed to transmit over mesh radio." });
    } finally {
      setSendingChat(false);
      setTimeout(() => setActionFeedback(null), 5000);
    }
  };

  const availableOrders = orders.filter((o) => !o.assigned_vehicle && o.status !== "DELIVERED");

  const handleRequestDelivery = async (orderId) => {
    setRequestingOrderId(orderId);
    try {
      const res = await fetch("/api/orders/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: orderId,
          partner_id: activeId,
          partner_name: currentPartner.name,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setActionFeedback({
          success: true,
          msg: `Delivery requested for Order ${orderId}! The Operations Manager will review and allocate it.`,
        });
      } else {
        setActionFeedback({ success: false, msg: data.error || "Failed to request delivery." });
      }
    } catch (e) {
      setActionFeedback({ success: false, msg: "Failed to connect to dispatch server." });
    } finally {
      setRequestingOrderId(null);
      setTimeout(() => setActionFeedback(null), 6000);
    }
  };

  return (
    <div className="space-y-6 w-full">
      {role === "manager" && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>🏢</span>
            <span><b>Manager Live Preview:</b> You are previewing the Delivery Partner Cockpit. You can test requesting deliveries and completing drop-offs just like a delivery rider.</span>
          </div>
          <Link href="/" className="underline font-bold text-amber-950">Manager Overview →</Link>
        </div>
      )}

      {/* 1. Header Banner with Profile Selector */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">{currentPartner.avatar || "🛵"}</span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-bold text-slate-900">
                    {currentPartner.name}
                  </h2>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                    Delivery Partner
                  </span>
                  <span className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full font-semibold">
                    ⭐ {currentPartner.rating || 4.9}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                    <span>Supabase Synced</span>
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {currentPartner.vehicle_model} · {currentPartner.registration} · {currentPartner.hub}
                </p>
              </div>
            </div>
          </div>

          {/* Quick Real Device GPS Button */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleToggleGps}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 border shadow-xs ${
                gpsActive
                  ? "bg-emerald-50 text-emerald-800 border-emerald-300 ring-1 ring-emerald-300"
                  : "bg-slate-50 hover:bg-slate-100 text-slate-700 border-slate-200"
              }`}
            >
              <span>📍</span>
              <span>{gpsActive ? `Live Device GPS Active (${gpsCoords?.lat?.toFixed(3)}, ${gpsCoords?.lon?.toFixed(3)})` : "Use Real Device GPS"}</span>
            </button>
          </div>

          {/* Switch Active Partner View - only for preview/simulation mode */}
          {!isDeliveryPartner && partnerProfiles.length > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Select Rider:</span>
              {partnerProfiles.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPartnerId(p.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    activeId === p.id
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  <span>{p.avatar || "🛵"}</span>
                  <span>{p.name.split(" ")[0]}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Action Feedback Banner */}
        {actionFeedback && (
          <div
            className={`mt-3 p-3 rounded-lg text-xs font-semibold border flex items-center justify-between ${
              actionFeedback.success
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-red-50 text-red-800 border-red-200"
            }`}
          >
            <span>{actionFeedback.msg}</span>
            <button onClick={() => setActionFeedback(null)} className="text-slate-400 hover:text-slate-700 font-bold ml-2">
              ✕
            </button>
          </div>
        )}

        {/* Rider KPI Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-4">
          <Stat
            label="Cockpit Status"
            value={isBroken ? "BREAKDOWN" : currentVehicle?.status || "IDLE"}
            help={isBroken ? "Emergency SOS Active" : "Operational in Swarm"}
          />
          <Stat
            label="Current Speed"
            value={`${Math.round(currentVehicle?.speed_kmh || 0)} km/h`}
            help={`${partnerCity} Urban Cruise`}
          />
          <Stat
            label="Cargo Load"
            value={`${currentVehicle?.current_load || 0} / ${currentVehicle?.max_weight || 100} kg`}
            help={`Rem: ${currentVehicle?.remaining_capacity || 0} kg`}
          />
          <Stat
            label="Fuel / Battery"
            value={`${Math.round(currentVehicle?.fuel_level || 100)}%`}
            help="EV Fast-Charge Ready"
          />
          <Stat
            label="Available Tasks"
            value={`${availableOrders.length} Open`}
            help="Open for claiming"
          />
          <Stat
            label="P2P Mesh Link"
            value={currentVehicle?.mesh_neighbors?.length > 0 ? "CONNECTED" : "STANDALONE"}
            help={`${currentVehicle?.mesh_neighbors?.length || 0} Peer Riders in RF Range`}
          />
        </div>
      </div>

      {/* 2. Main Cockpit View: Assigned Tasks List + Interactive Map */}
      <div className="grid grid-cols-1 lg:grid-cols-[440px_1fr] gap-6 items-start">
        {/* Left Column: Delivery Management Tabs */}
        <div className="space-y-4">
          {/* Sub Navigation Tabs */}
          <div className="bg-slate-100 p-1 rounded-xl flex gap-1 border border-slate-200">
            <button
              onClick={() => setActiveTab("available")}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                activeTab === "available"
                  ? "bg-white text-blue-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span>📋</span>
              <span>Available Deliveries</span>
              <span className="ml-1 px-1.5 py-0.2 bg-blue-100 text-blue-800 rounded-full text-[10px]">
                {availableOrders.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab("my_tasks")}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                activeTab === "my_tasks"
                  ? "bg-white text-emerald-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span>🚚</span>
              <span>My Allocated Tasks</span>
              <span className="ml-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-800 rounded-full text-[10px]">
                {pendingOrders.length}
              </span>
            </button>
          </div>

          {activeTab === "available" ? (
            /* Available Deliveries to Request */
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                    <span>📋</span>
                    <span>Available Customer Deliveries</span>
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Review and request delivery tasks. Operations Manager will allocate upon request.
                  </p>
                </div>
                <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-bold border border-blue-200">
                  {availableOrders.length} Open
                </span>
              </div>

              {pendingOrders.length > 0 && (
                <div 
                  onClick={() => setActiveTab("my_tasks")}
                  className="p-3 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 rounded-xl cursor-pointer transition flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🚚</span>
                    <div>
                      <div className="text-xs font-bold text-emerald-900">
                        {pendingOrders.length} Allocated Delivery Task{pendingOrders.length > 1 ? "s" : ""} Waiting!
                      </div>
                      <div className="text-[11px] text-emerald-700">
                        Tap here to view your delivery destinations.
                      </div>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-emerald-800 bg-emerald-200 px-2.5 py-1 rounded-lg">
                    View Tasks →
                  </span>
                </div>
              )}

              <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
                {availableOrders.length === 0 ? (
                  <div className="text-center py-8 border border-dashed border-slate-200 rounded-xl p-4">
                    <span className="text-2xl block mb-1">🎉</span>
                    <div className="text-xs font-bold text-slate-700">All Deliveries Allocated</div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      No unassigned deliveries at the moment. Place a new order in the customer portal to test.
                    </p>
                    <Link
                      href="/customer"
                      className="inline-block mt-3 px-3 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded border border-blue-200 transition-colors"
                    >
                      Open Customer Portal
                    </Link>
                  </div>
                ) : (
                  availableOrders.map((order, idx) => {
                    const isRequestedByMe = order.requested_by_id === activeId;
                    const isRequestedByOther = order.requested_by_id && !isRequestedByMe;
                    const isRequesting = requestingOrderId === order.id;

                    return (
                      <div
                        key={order.id}
                        className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50/20 shadow-xs transition-all space-y-2"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-900 font-mono text-xs">
                                {order.id}
                              </span>
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                                {order.demand || 1} kg
                              </span>
                              {order.priority === "HIGH" && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300">
                                  PRIORITY
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-800 font-semibold mt-1">
                              📍 {order.address || `Customer Node ${order.customer_id}`}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              Area: {order.area || order.city || "Maharashtra Hub"}
                            </div>
                          </div>
                        </div>

                        {/* Request Action */}
                        <div className="pt-2 border-t border-slate-200 flex items-center justify-between">
                          {isRequestedByMe ? (
                            <span className="text-xs font-semibold text-purple-700 bg-purple-50 border border-purple-200 px-2.5 py-1 rounded-lg flex items-center gap-1">
                              <span>⏳</span>
                              <span>Requested · Waiting for Admin</span>
                            </span>
                          ) : isRequestedByOther ? (
                            <span className="text-[11px] text-slate-500 italic">
                              Requested by {order.requested_by_name}
                            </span>
                          ) : (
                            <button
                              disabled={isRequesting}
                              onClick={() => handleRequestDelivery(order.id)}
                              className="w-full py-1.5 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-xs"
                            >
                              <span>{isRequesting ? "Requesting..." : "🙋 Request This Delivery"}</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          ) : (
            /* My Allocated Delivery Tasks */
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                    <span>My Allocated Delivery Tasks</span>
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    {pendingOrders.length} Pending Stops · {completedCount} Delivered
                  </p>
                </div>
                <span className="text-xs font-mono bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-bold border border-emerald-200">
                  {myOrders.length} Total
                </span>
              </div>

              {/* Emergency SOS Button for Rider */}
              {!isBroken ? (
                <button
                  disabled={isSosLoading}
                  onClick={handleSos}
                  className="w-full py-2 px-3 bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
                >
                  <span>🚨</span>
                  <span>{isSosLoading ? "Broadcasting..." : "Report Breakdown / Trigger Swarm Mesh SOS"}</span>
                </button>
              ) : (
                <div className="p-3 bg-red-50 border border-red-300 rounded-xl text-xs text-red-800 font-semibold flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span>⚠️</span>
                    <span>Vehicle is broken down. Swarm auction is re-allocating parcels to peer riders.</span>
                  </div>
                  <button
                    onClick={handleClearSos}
                    disabled={isSosLoading}
                    className="py-1.5 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-xs"
                  >
                    <span>🛠️</span>
                    <span>{isSosLoading ? "Repairing..." : "Vehicle Repaired — Clear SOS & Resume Service"}</span>
                  </button>
                </div>
              )}

              {/* Orders List Cards */}
              <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
                {myOrders.length === 0 ? (
                  <div className="text-center py-8 border border-dashed border-slate-200 rounded-xl p-4">
                    <span className="text-2xl block mb-1">📭</span>
                    <div className="text-xs font-bold text-slate-700">No Orders Allocated Yet</div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      Request deliveries from the Available Deliveries tab above, or wait for Admin allocation.
                    </p>
                    <button
                      onClick={() => setActiveTab("available")}
                      className="inline-block mt-3 px-3 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded border border-blue-200 transition-colors"
                    >
                      Browse Available Deliveries 📋
                    </button>
                  </div>
                ) : (
                  myOrders.map((order, idx) => {
                    const isDelivered = order.status === "DELIVERED";
                    const isLate = order.status === "LATE";
                    const isLoading = loadingOrderId === order.id;

                    return (
                      <div
                        key={order.id}
                        className={`p-3.5 rounded-xl border transition-all ${
                          isDelivered
                            ? "bg-emerald-50/50 border-emerald-200 opacity-80"
                            : isLate
                            ? "bg-red-50/60 border-red-200 shadow-sm"
                            : "bg-slate-50/70 border-slate-200 hover:border-blue-300 hover:bg-blue-50/20 shadow-sm"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded-full bg-slate-900 text-white text-[10px] font-mono font-bold flex items-center justify-center">
                              {idx + 1}
                            </span>
                            <span className="font-bold text-slate-900 font-mono text-xs">
                              {order.id}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                                isDelivered
                                  ? "bg-emerald-100 text-emerald-800"
                                  : isLate
                                  ? "bg-red-100 text-red-800 animate-pulse"
                                  : "bg-blue-100 text-blue-800"
                              }`}
                            >
                              {order.status}
                            </span>
                          </div>
                        </div>

                        <div className="text-xs text-slate-800 font-medium mb-1">
                          📍 {order.address || `Customer Node ${order.customer_id}`}
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-500 bg-white/60 p-2 rounded-lg border border-slate-100 mb-2.5">
                          <div>
                            <span className="text-slate-400">Demand:</span>{" "}
                            <span className="font-semibold text-slate-700">{order.demand} kg</span>
                          </div>
                          <div>
                            <span className="text-slate-400">Priority:</span>{" "}
                            <span className="font-semibold text-slate-700">{order.priority}</span>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2">
                          {!isDelivered ? (
                            <button
                              disabled={isLoading || isBroken}
                              onClick={() => handleCompleteOrder(order.id)}
                              className="w-full py-1.5 px-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-xs"
                            >
                              <span>{isLoading ? "Updating..." : "✅ Mark Delivered"}</span>
                            </button>
                          ) : (
                            <div className="w-full py-1 text-center text-xs font-bold text-emerald-700 bg-emerald-100/60 rounded-lg">
                              ✓ Successfully Delivered
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* P2P BLE Mesh Radio Intercom */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <span>📻</span>
                  <span>P2P BLE Mesh Radio Intercom</span>
                </h3>
                <p className="text-[11px] text-slate-500">
                  Transmit ad-hoc hopping radio messages directly to peer delivery drivers & hubs.
                </p>
              </div>
              <Link
                href="/network"
                className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
              >
                Full Mesh Cockpit →
              </Link>
            </div>

            {/* Quick Tactical Presets */}
            <div className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 block font-mono">
                Quick Tactical Radio Presets:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  "⚠️ Traffic jam ahead on highway",
                  "🌧️ Heavy rain / low visibility",
                  "📦 Arrived at delivery point",
                  "🔋 Fast EV charger available",
                  "🚨 Need backup assistance",
                ].map((preset, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSendMeshChat(preset)}
                    disabled={sendingChat}
                    className="px-2.5 py-1 text-[11px] rounded-lg bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 font-medium border border-slate-200 transition disabled:opacity-50"
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Mesh Message Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMeshChat();
              }}
              className="flex gap-2 pt-1"
            >
              <input
                type="text"
                value={chatText}
                onChange={(e) => setChatText(e.target.value)}
                placeholder="Type radio packet to broadcast over mesh..."
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
              />
              <button
                type="submit"
                disabled={sendingChat || !chatText.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition flex items-center gap-1 shadow-xs"
              >
                <span>{sendingChat ? "Transmitting..." : "📡 Send"}</span>
              </button>
            </form>

            {/* Recent Mesh Transmissions */}
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1 pt-1">
              <span className="text-[11px] font-mono text-slate-400 block uppercase">Recent Mesh Radio Packets:</span>
              {recentMeshChats.length === 0 ? (
                <p className="text-[11px] text-slate-400 text-center py-2 italic font-mono">
                  No mesh radio packets sent yet. Tap a preset above to transmit!
                </p>
              ) : (
                recentMeshChats.slice(0, 5).map((m, idx) => (
                  <div key={idx} className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                    <div className="flex items-center justify-between text-[10px] text-slate-500 mb-0.5 font-mono">
                      <span className="font-bold text-blue-700">{m.sender} ➔ {m.receiver}</span>
                      <span>{m.hop_count} hops · {m.latency_ms} ms</span>
                    </div>
                    <div className="text-slate-800 font-medium">{m.message}</div>
                    {m.route_taken && m.route_taken.length > 1 && (
                      <div className="text-[10px] text-emerald-700 font-mono mt-0.5">
                        Forwarding Path: {m.route_taken.join(" ➔ ")}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Interactive OpenStreetMap for Bengaluru */}
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>🗺️</span>
                  <span>Live Turn-by-Turn {partnerCity} GIS Navigation</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Tracking Rider {currentPartner.name} across {partnerCity} logistics corridors.
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded border border-slate-200">
                  {currentVehicle?.current_route?.length || 0} Total Waypoints
                </span>
              </div>
            </div>

            {/* Embedded OpenStreetMap */}
            <OpenStreetMap
              customers={state.map?.customers || []}
              depot={state.map?.depot || { x: 40, y: 50 }}
              routes={state.map?.active_routes || {}}
              recoveryRoutes={state.map?.recovery_routes || {}}
              vehicles={vehicles}
              trafficEdges={traffic?.affected_roads || []}
              selectedVehicleId={selectedPartnerId}
              onSelectVehicle={(vid) => setSelectedPartnerId(vid)}
              activeCity={partnerCity}
            />

            {/* Peer Swarm Mesh Status Bar */}
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-slate-700 font-semibold">
                  SWARM P2P RF MESH: ACTIVE (802.11p / LoRa)
                </span>
              </div>
              <div className="text-slate-500">
                Connected Peers: {currentVehicle?.mesh_neighbors?.join(", ") || "Searching for nearest delivery partner..."}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

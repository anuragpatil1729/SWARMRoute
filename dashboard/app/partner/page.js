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

  // If a Manager visits Partner Cockpit, guide them back to Manager Deck
  if (role === "manager") {
    return (
      <div className="py-16 text-center max-w-lg mx-auto">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8">
          <span className="text-3xl">🏢</span>
          <h2 className="text-lg font-bold text-slate-900 mt-2">Company Manager Account</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            You are logged in as a Company Manager. The Delivery Cockpit is reserved for registered delivery riders.
          </p>
          <Link
            href="/"
            className="inline-block mt-4 px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition shadow-xs"
          >
            Return to Manager Operational Overview →
          </Link>
        </div>
      </div>
    );
  }

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
        name: v.id,
        phone: "+91 98450 00000",
        vehicle_model: "Electric Fleet Vehicle",
        registration: v.id,
        hub: "Bengaluru Hub",
        city: "Bengaluru",
        rating: 4.9,
        avatar: "🛵",
      })));

  const activeId = selectedPartnerId || partnerProfiles[0]?.id || vehicles[0]?.id;
  const currentVehicle = vehicles.find((v) => v.id === activeId) || vehicles[0];
  const currentPartner = partnerProfiles.find((p) => p.id === activeId) || partnerProfiles[0] || {
    id: activeId || "PARTNER_01",
    name: profile?.full_name || "Delivery Partner",
    vehicle_model: "Electric Fleet Vehicle",
    registration: "KA-01-EQ-1024",
    hub: "Bengaluru Hub",
    avatar: "🛵",
    rating: 5.0,
  };

  // Filter orders assigned to this rider
  const myOrders = orders.filter((o) => o.assigned_vehicle === activeId);
  const completedCount = myOrders.filter((o) => o.status === "DELIVERED").length;
  const pendingOrders = myOrders.filter((o) => o.status !== "DELIVERED");
  const isBroken = currentVehicle?.status === "BROKEN_DOWN";

  // Calculate estimated total earnings for this shift (Base payout ₹80 + ₹2.5/kg)
  const shiftEarningsINR = myOrders.reduce((sum, o) => sum + (o.payout_inr || 120), 0);

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

  return (
    <div className="space-y-6 w-full">
      {/* 1. Header Banner with Profile Selector */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">{currentPartner.avatar || "🛵"}</span>
              <div>
                <div className="flex items-center gap-2">
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

          {/* Switch Active Partner View */}
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
            help="Bengaluru Urban Cruise"
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
            label="Shift Earnings"
            value={`₹${shiftEarningsINR}`}
            help={`${completedCount} delivered / ${myOrders.length} tasks`}
          />
          <Stat
            label="P2P Mesh Link"
            value={currentVehicle?.mesh_neighbors?.length > 0 ? "CONNECTED" : "STANDALONE"}
            help={`${currentVehicle?.mesh_neighbors?.length || 0} Peer Riders in RF Range`}
          />
        </div>
      </div>

      {/* 2. Main Cockpit View: Assigned Tasks List + Interactive Map */}
      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6 items-start">
        {/* Left Column: My Allocated Orders & Actions */}
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <span>📦</span>
                  <span>My Allocated Delivery Tasks</span>
                </h3>
                <p className="text-[11px] text-slate-500">
                  {pendingOrders.length} Pending Stops · {completedCount} Delivered
                </p>
              </div>
              <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-bold border border-blue-200">
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
              <div className="p-2.5 bg-red-100 border border-red-300 rounded-lg text-xs text-red-800 font-semibold flex items-center gap-2">
                <span>⚠</span>
                <span>Vehicle is broken down. Swarm auction is re-allocating parcels to peer riders.</span>
              </div>
            )}

            {/* Orders List Cards */}
            <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
              {myOrders.length === 0 ? (
                <div className="text-center py-8 border border-dashed border-slate-200 rounded-xl p-4">
                  <span className="text-2xl block mb-1">📭</span>
                  <div className="text-xs font-bold text-slate-700">No Orders Assigned Yet</div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Wait for the Company Manager to allocate delivery orders from the Admin Console.
                  </p>
                  <Link
                    href="/"
                    className="inline-block mt-3 px-3 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded border border-blue-200 transition-colors"
                  >
                    Go to Manager Console ⚡
                  </Link>
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
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                            isDelivered
                              ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                              : isLate
                              ? "bg-red-100 text-red-800 border-red-300"
                              : "bg-blue-100 text-blue-800 border-blue-300"
                          }`}
                        >
                          {order.status}
                        </span>
                      </div>

                      {/* Delivery Address & Landmark */}
                      <div className="text-xs text-slate-800 font-medium mb-1">
                        📍 {order.address || order.area || "Bengaluru Customer Destination"}
                      </div>

                      {/* Details row */}
                      <div className="grid grid-cols-3 gap-1 py-1.5 border-t border-b border-slate-200/60 text-[11px] font-mono text-slate-600 mb-2">
                        <div>
                          <span className="text-slate-400 block text-[9px]">DEMAND</span>
                          <span className="font-bold text-slate-800">{order.demand} kg</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[9px]">DEADLINE</span>
                          <span className="text-slate-800">{order.deadline}m</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[9px]">PAYOUT</span>
                          <span className="font-bold text-emerald-700">₹{order.payout_inr || 120}</span>
                        </div>
                      </div>

                      {/* Action buttons */}
                      {!isDelivered ? (
                        <div className="flex items-center gap-2">
                          <button
                            disabled={isLoading || isBroken}
                            onClick={() => handleCompleteOrder(order.id)}
                            className={`w-full py-1.5 px-3 rounded-lg text-xs font-bold shadow-sm transition-all flex items-center justify-center gap-1.5 ${
                              isLoading || isBroken
                                ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                                : "bg-emerald-600 hover:bg-emerald-500 text-white active:scale-95"
                            }`}
                          >
                            <span>✓</span>
                            <span>{isLoading ? "Delivering..." : "Complete Delivery & Earn Payout"}</span>
                          </button>
                        </div>
                      ) : (
                        <div className="text-center py-1 text-xs text-emerald-700 font-semibold bg-emerald-100/50 rounded-lg">
                          ✓ Delivery Completed · Payout Credited
                        </div>
                      )}
                    </div>
                  );
                })
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
                  <span>Live Turn-by-Turn Bengaluru GIS Navigation</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Tracking Rider {currentPartner.name} across Bengaluru logistics corridors.
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

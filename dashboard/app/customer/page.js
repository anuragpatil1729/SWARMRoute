"use client";

import { useState } from "react";
import Link from "next/link";
import { useDashboardState } from "../../lib/useDashboardState";

const MAHARASHTRA_HUBS = [
  { name: "BKC Freight Gateway", area: "Bandra-Kurla Complex", city: "Mumbai" },
  { name: "Hinjawadi Phase 1 Hub", area: "Hinjawadi", city: "Pune" },
  { name: "Andheri MIDC Cargo Terminal", area: "Andheri East", city: "Mumbai" },
  { name: "Thane Wagle Estate Hub", area: "Thane West", city: "Thane" },
  { name: "Vashi APMC Market Terminal", area: "Navi Mumbai", city: "Navi Mumbai" },
  { name: "Powai Supreme Business Park", area: "Powai", city: "Mumbai" },
  { name: "Bhosari MIDC Industrial Hub", area: "Pimpri-Chinchwad", city: "Pune" },
  { name: "Chakan Automotive Logistics Park", area: "Chakan", city: "Pune" },
  { name: "Lower Parel Commercial Center", area: "Lower Parel", city: "Mumbai" },
  { name: "Hadapsar Magarpatta City Hub", area: "Hadapsar", city: "Pune" },
];

export default function CustomerPortalPage() {
  const { state } = useDashboardState();
  const [customerName, setCustomerName] = useState("Anurag Patil");
  const [phone, setPhone] = useState("+91 98200 55410");
  const [pickupAddress, setPickupAddress] = useState(
    "BKC Freight Gateway, Bandra-Kurla Complex, Mumbai"
  );
  const [deliveryAddress, setDeliveryAddress] = useState(
    "Hinjawadi Phase 1 Hub, Hinjawadi, Pune"
  );
  const [demandWeight, setDemandWeight] = useState(15);
  const [priority, setPriority] = useState("EXPRESS");
  const [notes, setNotes] = useState("Handle with care, fragile logistics equipment");

  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [recentOrderId, setRecentOrderId] = useState(null);
  const [locationStatus, setLocationStatus] = useState("");

  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      setLocationStatus("Geolocation is not supported by your browser.");
      return;
    }
    setLocationStatus("Detecting current GPS coordinates...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        const locString = `Current Location (${latitude.toFixed(4)}, ${longitude.toFixed(4)}), Maharashtra`;
        setPickupAddress(locString);
        setLocationStatus(`GPS Locked: ${latitude.toFixed(4)}°N, ${longitude.toFixed(4)}°E`);
      },
      (error) => {
        setLocationStatus(`Location access denied: ${error.message}`);
      }
    );
  };

  const handlePlaceOrder = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);

    try {
      const payload = {
        customer_name: customerName,
        phone,
        pickup_address: pickupAddress,
        delivery_address: deliveryAddress,
        demand_weight: parseFloat(demandWeight),
        priority,
        deadline_mins: priority === "URGENT" ? 60 : priority === "EXPRESS" ? 120 : 240,
        city: "Maharashtra",
        notes,
      };

      const res = await fetch("/api/orders/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then((r) => r.json());

      setSubmitting(false);
      if (res && res.success) {
        setFeedback({
          success: true,
          msg: `Order ${res.order_id} created successfully! Live tracking is now active.`,
        });
        setRecentOrderId(res.order_id);
      } else {
        setFeedback({
          success: false,
          msg: res?.error || "Failed to submit order. Please check backend connection.",
        });
      }
    } catch (err) {
      setSubmitting(false);
      setFeedback({
        success: false,
        msg: "Network error submitting order to backend.",
      });
    }
  };

  // Find recent order in active state if exists
  const activeOrders = state?.orders || [];
  const trackedOrder = activeOrders.find((o) => o.id === recentOrderId) || (activeOrders.length > 0 ? activeOrders[activeOrders.length - 1] : null);

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-2xl font-bold text-slate-900">
                Customer Delivery Portal
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Dispatch parcels across the Mumbai – Pune Logistics Corridor with real-time AI autonomous route allocation.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/orders"
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 text-xs font-semibold hover:bg-slate-100 transition"
            >
              🏢 Manager Dispatch Deck →
            </Link>
            <Link
              href="/fleet"
              className="px-3.5 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-500 transition shadow-xs"
            >
              🚚 Live Fleet Registry →
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Order Placement Form */}
        <div className="lg:col-span-2 border border-slate-200 bg-white rounded-2xl shadow-sm p-6">
          <h3 className="text-base font-bold text-slate-900 mb-1">
            Book Parcel Dispatch
          </h3>
          <p className="text-xs text-slate-500 mb-5">
            Configure parcel weight, pickup terminal, and recipient destination across Maharashtra.
          </p>

          {feedback && (
            <div
              className={`mb-5 p-4 rounded-xl text-xs font-semibold border flex items-center justify-between ${
                feedback.success
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : "bg-red-50 text-red-800 border-red-200"
              }`}
            >
              <span>{feedback.msg}</span>
              <button
                onClick={() => setFeedback(null)}
                className="text-slate-400 hover:text-slate-600 font-bold ml-3"
              >
                ✕
              </button>
            </div>
          )}

          <form onSubmit={handlePlaceOrder} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Customer / Sender Name
                </label>
                <input
                  type="text"
                  required
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="e.g. Anurag Patil"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Contact Phone Number
                </label>
                <input
                  type="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="+91 98200 00000"
                />
              </div>
            </div>

            {/* Pickup Address */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-slate-700 font-semibold">
                  Pickup Hub / Origin Address
                </label>
                <button
                  type="button"
                  onClick={handleDetectLocation}
                  className="text-[11px] text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1"
                >
                  📍 Detect My GPS Location
                </button>
              </div>
              <input
                type="text"
                required
                value={pickupAddress}
                onChange={(e) => setPickupAddress(e.target.value)}
                className="w-full border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Origin freight depot"
              />
              {locationStatus && (
                <div className="text-[11px] text-blue-700 mt-1 font-mono">
                  {locationStatus}
                </div>
              )}
            </div>

            {/* Delivery Destination */}
            <div>
              <label className="block text-slate-700 font-semibold mb-1">
                Delivery Destination Address (Maharashtra)
              </label>
              <input
                type="text"
                required
                value={deliveryAddress}
                onChange={(e) => setDeliveryAddress(e.target.value)}
                className="w-full border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Destination commercial hub"
              />
            </div>

            {/* Quick Select Hubs */}
            <div>
              <span className="block text-[11px] text-slate-500 font-semibold mb-1.5 uppercase tracking-wider">
                Quick Select Delivery Destinations:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {MAHARASHTRA_HUBS.map((hub) => (
                  <button
                    key={hub.name}
                    type="button"
                    onClick={() =>
                      setDeliveryAddress(`${hub.name}, ${hub.area}, ${hub.city}`)
                    }
                    className="px-2.5 py-1 rounded-md text-[11px] bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 font-medium border border-slate-200 transition"
                  >
                    {hub.name} ({hub.city})
                  </button>
                ))}
              </div>
            </div>

            {/* Weight and Priority */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-slate-700 font-semibold">
                    Parcel Weight: <span className="font-mono text-blue-600">{demandWeight} kg</span>
                  </label>
                </div>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={demandWeight}
                  onChange={(e) => setDemandWeight(e.target.value)}
                  className="w-full accent-blue-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-400 font-mono mt-0.5">
                  <span>1 kg</span>
                  <span>50 kg</span>
                  <span>100 kg</span>
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Delivery Priority Tier
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  {["NORMAL", "EXPRESS", "URGENT"].map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPriority(p)}
                      className={`py-2 px-1 text-center rounded-lg text-xs font-bold transition border ${
                        priority === p
                          ? p === "URGENT"
                            ? "bg-red-600 text-white border-red-600"
                            : p === "EXPRESS"
                            ? "bg-blue-600 text-white border-blue-600"
                            : "bg-slate-800 text-white border-slate-800"
                          : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Special Instructions */}
            <div>
              <label className="block text-slate-700 font-semibold mb-1">
                Special Handling Instructions
              </label>
              <textarea
                rows="2"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Gate entry instructions, contact person, etc."
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className={`w-full py-3 px-4 rounded-xl font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2 ${
                submitting
                  ? "bg-slate-400 text-white cursor-not-allowed"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white active:scale-98 shadow-blue-500/20"
              }`}
            >
              <span>{submitting ? "Booking Parcel..." : "🚀 Place Delivery Order"}</span>
            </button>
          </form>
        </div>

        {/* Live Tracking & Status Card */}
        <div className="space-y-4">
          <div className="border border-blue-200 bg-gradient-to-br from-blue-950 via-slate-900 to-indigo-950 text-white rounded-2xl shadow-md p-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                Live Order Tracking
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                ACTIVE
              </span>
            </div>

            {trackedOrder ? (
              <div className="space-y-4">
                <div>
                  <div className="text-xs text-slate-400 font-mono">Order Tracking ID</div>
                  <div className="text-lg font-mono font-bold text-cyan-300">{trackedOrder.id}</div>
                </div>

                <div className="border-t border-slate-800 pt-3">
                  <div className="text-xs text-slate-400">Destination</div>
                  <div className="text-sm font-semibold text-slate-200 mt-0.5 leading-snug">
                    {trackedOrder.address || trackedOrder.area || "Maharashtra Hub"}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 border-t border-slate-800 pt-3 text-xs">
                  <div>
                    <div className="text-slate-400">Status</div>
                    <div className="font-mono font-bold text-emerald-400 mt-0.5">
                      {trackedOrder.status}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-400">Payload</div>
                    <div className="font-mono font-bold text-slate-200 mt-0.5">
                      {trackedOrder.demand} kg
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-800 pt-3">
                  <div className="text-xs text-slate-400">Assigned Partner Truck</div>
                  {trackedOrder.assigned_vehicle ? (
                    <div className="mt-1 bg-white/10 rounded-xl p-3 border border-white/10">
                      <div className="font-bold text-sm text-white flex items-center gap-2">
                        <span>🚚</span>
                        <span>{trackedOrder.assigned_partner || trackedOrder.assigned_vehicle}</span>
                      </div>
                      <div className="text-[11px] font-mono text-cyan-300 mt-0.5">
                        Vehicle ID: {trackedOrder.assigned_vehicle}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-1 bg-amber-500/10 border border-amber-500/30 rounded-xl p-2.5 text-xs text-amber-300">
                      ⏳ Pending Dispatch: Waiting for Manager / AI Auto-Allocation
                    </div>
                  )}
                </div>

                <div className="pt-2">
                  <Link
                    href="/routes"
                    className="block w-full py-2 text-center text-xs font-bold rounded-lg bg-white/10 hover:bg-white/20 text-cyan-200 border border-cyan-400/30 transition"
                  >
                    🗺️ View Live Route on Map →
                  </Link>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-slate-400 text-xs">
                No orders placed yet. Submit an order above to start tracking.
              </div>
            )}
          </div>

          {/* Quick FAQ / Guarantee */}
          <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-5 text-xs text-slate-600 space-y-2">
            <div className="font-bold text-slate-900 flex items-center gap-1.5">
              <span>🛡️</span> SWARMRoute Multi-Hop SLA
            </div>
            <p className="text-slate-500 leading-relaxed text-[11px]">
              Every parcel in the Maharashtra corridor is backed by peer-to-peer BLE mesh redundancy. Even in highway tunnels or cellular dead zones, your delivery partner stays synchronized with adjacent fleet nodes.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

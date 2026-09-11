"use client";

import { useState } from "react";
import Section from "../../components/Section";
import Stat from "../../components/Stat";
import { useDashboardState } from "../../lib/useDashboardState";
import { useAuth } from "../../lib/AuthContext";

export default function OrdersPage() {
  const { state, connectionStatus, allocateTask, completeTask } = useDashboardState();
  const { profile, user } = useAuth();
  const adminCity = profile?.city || user?.user_metadata?.city || (typeof window !== "undefined" ? localStorage.getItem("swarm_registered_city") : null) || state?.simulation?.city || "Operations";

  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState("ALL");

  // Allocation deck state
  const [allocOrderId, setAllocOrderId] = useState("");
  const [allocVehicleId, setAllocVehicleId] = useState("");
  const [allocFeedback, setAllocFeedback] = useState(null);
  const [allocLoading, setAllocLoading] = useState(false);

  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">ORDERS MONITORING OFFLINE</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            Please make sure the SWARMRoute backend is running at <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">http://127.0.0.1:8000</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8 max-w-md mx-auto">
          <div className="font-mono text-xs text-slate-400">Loading Orders</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO ORDER REGISTRY</h2>
          <p className="text-xs text-slate-500 mt-2">Streaming real-time parcel delivery states...</p>
        </div>
      </div>
    );
  }

  const { orders = [], vehicles = [], performance } = state;

  const filteredOrders = orders.filter((o) => {
    const matchesSearch =
      o.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (o.address && o.address.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (o.area && o.area.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (o.assigned_vehicle && o.assigned_vehicle.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = filterStatus === "ALL" || o.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  const pendingOrders = orders.filter((o) => o.status === "PENDING");
  const inTransitOrders = orders.filter((o) => o.status === "IN_TRANSIT" || o.status === "ASSIGNED");
  const deliveredOrders = orders.filter((o) => o.status === "DELIVERED");

  return (
    <div className="space-y-6 w-full">
      {/* Header Banner */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">
                Customer Delivery Orders Registry
              </h2>
              <span className="text-[11px] font-mono px-2.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
                {orders.length} Total Parcels
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Detailed stop windows, delivery deadlines, assigned partner trucks, and real-time transit status across {adminCity}.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap text-xs font-semibold">
            <span className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200">
              Delivered: {performance.delivered} / {performance.total_orders}
            </span>
            <span className="px-3 py-1.5 rounded-lg bg-blue-50 text-blue-800 border border-blue-200">
              Active: {inTransitOrders.length + pendingOrders.length}
            </span>
            {performance.late > 0 && (
              <span className="px-3 py-1.5 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
                Late: {performance.late}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <Stat label="Total Orders" value={orders.length} help="Active dataset manifest" />
        <Stat label="Delivered" value={performance.delivered} help={`${performance.success_rate}% success`} />
        <Stat label="On-Time Rate" value={`${performance.on_time_rate}%`} help={`${performance.on_time} on-time`} />
        <Stat label="In-Transit" value={inTransitOrders.length} help="Currently on road" />
        <Stat label="Pending Dispatch" value={pendingOrders.length} help="Awaiting truck loading" />
        <Stat label="Avg Delay" value={`${performance.average_delay_mins} min`} help="Across completed stops" />
      </div>

      {/* Task Allocation Console (Company Manager) */}
      <div className="border border-blue-200 bg-gradient-to-r from-blue-900 to-indigo-950 text-white rounded-xl shadow-md p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
          <div>
            <h3 className="text-sm font-bold tracking-tight uppercase font-mono flex items-center gap-2">
              <span className="text-cyan-400 text-base">🏢</span> Dispatch & Task Allocation Deck
            </h3>
            <p className="text-xs text-blue-200 mt-0.5">
              Select any pending customer parcel and assign it directly to a partner vehicle.
            </p>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-800/60 border border-blue-600 text-blue-200">
            Real-Time Vehicle Routing
          </span>
        </div>

        {allocFeedback && (
          <div
            className={`mb-4 p-3 rounded-lg text-xs font-semibold border flex items-center justify-between ${
              allocFeedback.success
                ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/40"
                : "bg-red-500/20 text-red-200 border-red-500/40"
            }`}
          >
            <span>{allocFeedback.msg}</span>
            <button onClick={() => setAllocFeedback(null)} className="text-white/60 hover:text-white font-bold ml-2">
              ✕
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div>
            <label className="block text-blue-200 font-semibold mb-1">
              Select Pending Order:
            </label>
            <select
              value={allocOrderId}
              onChange={(e) => setAllocOrderId(e.target.value)}
              className="w-full bg-blue-950/80 border border-blue-700 rounded-lg p-2.5 text-white font-mono text-xs focus:ring-2 focus:ring-blue-400 outline-none"
            >
              <option value="">-- Choose Order --</option>
              {orders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.id} ({o.demand}kg) · {o.area || `${adminCity} Hub`} [{o.status}]
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-blue-200 font-semibold mb-1">
              Select Delivery Partner:
            </label>
            <select
              value={allocVehicleId || (vehicles.length > 0 ? vehicles[0].id : "")}
              onChange={(e) => setAllocVehicleId(e.target.value)}
              className="w-full bg-blue-950/80 border border-blue-700 rounded-lg p-2.5 text-white font-mono text-xs focus:ring-2 focus:ring-blue-400 outline-none"
            >
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.partner_name || v.id} ({v.id}) · {v.vehicle_model} [Rem: {v.remaining_capacity}kg]
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              disabled={!allocOrderId || allocLoading}
              onClick={async () => {
                const targetVehicle = allocVehicleId || (vehicles.length > 0 ? vehicles[0].id : "");
                if (!allocOrderId || !targetVehicle) return;
                setAllocLoading(true);
                const res = await allocateTask(allocOrderId, targetVehicle);
                setAllocLoading(false);
                if (res && res.success) {
                  setAllocFeedback({ success: true, msg: res.message || "Task successfully allocated!" });
                } else {
                  setAllocFeedback({ success: false, msg: res?.error || "Allocation failed." });
                }
                setTimeout(() => setAllocFeedback(null), 5000);
              }}
              className={`w-full py-2.5 px-4 rounded-lg font-bold text-xs shadow-sm transition-all flex items-center justify-center gap-2 ${
                !allocOrderId || allocLoading
                  ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                  : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold active:scale-95"
              }`}
            >
              <span>{allocLoading ? "Allocating..." : "Dispatch Order to Partner"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-slate-500 uppercase font-mono">Filter:</span>
          {["ALL", "PENDING", "IN_TRANSIT", "DELIVERED", "REASSIGNED", "FAILED"].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                filterStatus === status
                  ? "bg-blue-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {status.replace("_", " ")}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Search order ID, landmark, area, vehicle..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full sm:w-72 px-3 py-1.5 rounded-lg border border-slate-200 text-xs placeholder-slate-400 focus:outline-none focus:border-blue-500 font-mono"
        />
      </div>

      {/* Detailed Orders Table */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
            Orders Registry ({filteredOrders.length})
          </h3>
          <span className="text-xs text-slate-400 font-mono">Live Simulation Synchronized</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-mono uppercase text-[11px]">
              <tr>
                <th className="py-3 px-4">Order ID</th>
                <th className="py-3 px-3">Destination / Area</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Assigned Partner</th>
                <th className="py-3 px-3">Demand (kg)</th>
                <th className="py-3 px-3">Priority</th>
                <th className="py-3 px-3">Time Window</th>
                <th className="py-3 px-3">ETA</th>
                <th className="py-3 px-4">Payout (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-[12px]">
              {filteredOrders.map((o) => {
                const isDelivered = o.status === "DELIVERED";
                const isInTransit = o.status === "IN_TRANSIT" || o.status === "ASSIGNED";
                const isPending = o.status === "PENDING";
                const isLate = o.delay > 0;
                return (
                  <tr key={o.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-900">
                      {o.id}
                    </td>
                    <td className="py-3 px-3 font-sans">
                      <div className="text-slate-800 font-medium">{o.address}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{o.area}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                          isDelivered
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : isInTransit
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : isPending
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-red-50 text-red-700 border border-red-200"
                        }`}
                      >
                        {o.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-700">
                      {o.assigned_vehicle ? (
                        <div>
                          <div className="font-semibold text-slate-800">{o.assigned_partner || o.assigned_vehicle}</div>
                          <div className="text-[10px] text-slate-400">{o.assigned_vehicle}</div>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-800 font-semibold">
                      {o.demand} kg
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          o.priority === "HIGH"
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {o.priority}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-600 text-[11px]">
                      {Math.round(o.ready_time)}m - {Math.round(o.deadline)}m
                      {isLate && (
                        <span className="text-red-600 block text-[10px] font-bold">
                          +{o.delay}m delay
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-700">
                      {isDelivered ? "Done" : `${o.eta} min`}
                    </td>
                    <td className="py-3 px-4 text-emerald-700 font-bold">
                      ₹{o.payout_inr || 120}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

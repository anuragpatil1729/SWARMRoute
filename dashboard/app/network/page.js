"use client";

import { useState } from "react";
import Stat from "../../components/Stat";
import LiveMeshFigure from "../../components/LiveMeshFigure";
import { useDashboardState } from "../../lib/useDashboardState";
import { numeric } from "../../lib/presentation";

const CHAT_PRESETS = [
  { label: "⚠️ Traffic Jam Ahead", text: "Heavy traffic jam reported on main corridor. Detouring via secondary routes." },
  { label: "🌧️ Weather Alert", text: "Heavy rain and reduced visibility in Khandala Ghat. Reducing convoy speed to 40 km/h." },
  { label: "🚧 Road Obstruction", text: "Obstruction reported at Expressway km 48. Reroute via lane 2." },
  { label: "📦 Arrived at Delivery", text: "Driver arrived at customer delivery node. Commencing parcel drop-off." },
  { label: "⚡ Cloud Blackout", text: "Central cellular cloud gateway lost. Operating on autonomous peer-to-peer RF mesh." },
  { label: "🔋 Fast EV Charger Available", text: "High-speed EV fast charger spotted available at logistics station." },
  { label: "🚨 Need Backup Assistance", text: "Requesting peer driver assistance for stranded consignment handover." },
  { label: "🚚 Convoy Platooning", text: "Convoy platooning engaged. Maintaining 25m autonomous radio headway." },
];

export default function NetworkPage() {
  const { state, connectionStatus, toggleCloud } = useDashboardState();
  const [testLog, setTestLog] = useState(null);
  const [activeRoute, setActiveRoute] = useState([]);
  const [loadingAction, setLoadingAction] = useState(null);

  // Chat controls
  const [chatSender, setChatSender] = useState("");
  const [chatReceiver, setChatReceiver] = useState("BROADCAST");
  const [chatMessage, setChatMessage] = useState("");
  const [sendingChat, setSendingChat] = useState(false);
  const [liveChats, setLiveChats] = useState([]);

  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">NETWORK TELEMETRY OFFLINE</h2>
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
          <div className="font-mono text-xs text-slate-400">Loading Network</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO MESH NETWORK</h2>
          <p className="text-xs text-slate-500 mt-2">Scanning peer-to-peer RF communication topology...</p>
        </div>
      </div>
    );
  }

  const { network, mesh = { nodes: [], links: [], chat_messages: [] }, fleet, incidents = [], events = [] } = state;
  const isCloudOnline = network.cloud_status === "ONLINE";
  const activeNodes = mesh.nodes || [];

  useEffect(() => {
    fetch("/api/simulation/mesh/chat-history")
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setLiveChats(data);
      })
      .catch(() => {});
  }, [state]);

  const chatMessages = liveChats.length > 0 ? liveChats : (mesh.chat_messages || []);

  const allSenders = [
    ...(state.delivery_partners || []).map((p) => ({ id: p.id, name: p.name || p.id })),
    ...(state.vehicles || []).map((v) => ({ id: v.id, name: v.partner_name ? `${v.id} (${v.partner_name})` : v.id })),
    ...(activeNodes || []).map((n) => ({ id: n.id, name: n.id })),
  ];
  const uniqueSenders = Array.from(new Map(allSenders.map((s) => [s.id, s])).values());

  const handleDeployTestNodes = async () => {
    setLoadingAction("deploy");
    try {
      const res = await fetch("/api/simulation/mesh/deploy-test", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        setTestLog({
          type: "DEPLOY",
          title: "Test Mesh Nodes Active",
          message: "4 peer radio nodes deployed along corridor: HUB_BKC ➔ PEER_VASHI ➔ PEER_LONAVALA ➔ PEER_PUNE (30km RF links).",
          status: "ONLINE",
          nodes: data.nodes,
        });
        setActiveRoute([]);
      }
    } catch (err) {
      console.error("Failed to deploy test mesh nodes:", err);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleSendPing = async () => {
    setLoadingAction("ping");
    try {
      const res = await fetch("/api/simulation/mesh/test-ping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "HUB_BKC", target: "PEER_PUNE" }),
      });
      const data = await res.json();
      if (data.success) {
        setActiveRoute(data.route_taken || []);
        setTestLog({
          type: "PING",
          title: `Packet Delivered: ${data.message_id}`,
          message: `Multi-hop routing successful from ${data.source} to ${data.target} via ${data.hop_count || 1} anonymous peer hops`,
          hops: data.hop_count,
          latency: `${data.latency_ms} ms`,
          route: [],
          status: "DELIVERED",
        });
      } else {
        setTestLog({
          type: "ERROR",
          title: "Transmission Dropped",
          message: data.error || "No active multi-hop RF path available.",
          status: "DROPPED",
        });
      }
    } catch (err) {
      console.error("Failed to send mesh ping:", err);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleSimulateSos = async () => {
    setLoadingAction("sos");
    try {
      const res = await fetch("/api/simulation/mesh/simulate-sos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: "PEER_LONAVALA" }),
      });
      const data = await res.json();
      if (data.success) {
        setTestLog({
          type: "SOS",
          title: `🚨 Emergency SOS Broadcast: ${data.broken_node}`,
          message: `Node ${data.broken_node} experienced engine failure. Emergency SOS packet relayed to peers: ${data.peers_alerted.join(", ")}.`,
          hops: data.hop_count,
          latency: `${data.latency_ms} ms`,
          peers: data.peers_alerted,
          status: "SOS_RESOLVED",
        });
      }
    } catch (err) {
      console.error("Failed to simulate SOS:", err);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleClearTestNodes = async () => {
    setLoadingAction("clear");
    try {
      const res = await fetch("/api/simulation/mesh/clear-test", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        setActiveRoute([]);
        setTestLog({
          type: "CLEAR",
          title: "Test Nodes Cleared",
          message: "Mesh returned to real registered delivery vehicles.",
          status: "CLEARED",
        });
      }
    } catch (err) {
      console.error("Failed to clear test nodes:", err);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleSendChat = async (overrideText) => {
    const textToSend = typeof overrideText === "string" ? overrideText : chatMessage;
    if (!textToSend || !textToSend.trim()) return;

    setSendingChat(true);
    try {
      const sender = chatSender || (activeNodes[0]?.id || "HUB_BKC");
      const receiver = chatReceiver || "BROADCAST";

      const res = await fetch("/api/simulation/mesh/send-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender,
          receiver,
          message: textToSend.trim(),
        }),
      });
      const data = await res.json();
      if (data.success && data.record) {
        if (data.record.route_taken?.length > 1) {
          setActiveRoute(data.record.route_taken);
        }
        setChatMessage("");
        setTestLog({
          type: "CHAT",
          title: `💬 Mesh Radio Packet: ${data.record.id}`,
          message: `"${data.record.message}" transmitted from ${data.record.sender} to ${data.record.receiver}`,
          hops: data.record.hop_count,
          latency: `${data.record.latency_ms} ms`,
          route: data.record.route_taken,
          status: "DELIVERED",
        });
      }
    } catch (err) {
      console.error("Failed to send mesh chat:", err);
    } finally {
      setSendingChat(false);
    }
  };

  const networkEvents = events.filter(
    (e) =>
      e.type === "MESH_RECOVERY" ||
      e.type === "CLOUD_TOGGLE" ||
      e.type === "BREAKDOWN" ||
      e.type?.startsWith("MESH") ||
      (e.description && e.description.toLowerCase().includes("mesh")) ||
      (e.description && e.description.toLowerCase().includes("cloud"))
  );

  return (
    <div className="space-y-6 w-full">
      {/* Header Banner */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900">
                Decentralized Mesh & Cloud Telecommunications
              </h2>
              <span
                className={`text-[11px] font-mono px-2.5 py-0.5 rounded font-semibold ${
                  isCloudOnline
                    ? "bg-blue-50 text-blue-700 border border-blue-200"
                    : "bg-amber-50 text-amber-800 border border-amber-200 animate-pulse"
                }`}
              >
                ● Mode: {network.mode}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Multi-hop dynamic ad-hoc radio mesh network linking commercial trucks autonomously during cloud connectivity dropouts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => toggleCloud(!isCloudOnline)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition shadow-xs flex items-center gap-1.5 ${
                isCloudOnline
                  ? "bg-amber-500 hover:bg-amber-600 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              }`}
            >
              <span>{isCloudOnline ? "⚡ Cut Cloud (Force Mesh Mode)" : "☁️ Restore Cloud Uplink"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Interactive BLE Mesh Test Bench */}
      <div className="border border-blue-200 bg-gradient-to-r from-blue-50/50 via-indigo-50/30 to-white rounded-xl shadow-sm p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-blue-100 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base">🧪</span>
              <h3 className="text-sm font-bold text-slate-900 uppercase font-mono tracking-wide">
                Interactive BLE Mesh Test Bench
              </h3>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                Self-Contained Sandbox
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Test peer-to-peer radio propagation, multi-hop packet routing, chat messaging, and Contract-Net emergency SOS without needing real trucks.
            </p>
          </div>

          <div className="text-xs font-mono text-slate-500">
            Active Nodes: <b className="text-blue-700 font-bold">{activeNodes.length}</b> · Links: <b className="text-blue-700 font-bold">{mesh.links.length}</b>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleDeployTestNodes}
            disabled={loadingAction !== null}
            className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition shadow-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            <span>🛰️</span>
            <span>{loadingAction === "deploy" ? "Deploying..." : "Deploy Test Radio Nodes"}</span>
          </button>

          <button
            onClick={handleSendPing}
            disabled={loadingAction !== null || activeNodes.length < 2}
            className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition shadow-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            <span>📡</span>
            <span>{loadingAction === "ping" ? "Transmitting..." : "Send Multi-Hop Ping Packet"}</span>
          </button>

          <button
            onClick={handleSimulateSos}
            disabled={loadingAction !== null || activeNodes.length === 0}
            className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-700 text-white transition shadow-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            <span>🚨</span>
            <span>{loadingAction === "sos" ? "Broadcasting..." : "Simulate Node SOS Breakdown"}</span>
          </button>

          <button
            onClick={() => toggleCloud(!isCloudOnline)}
            className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-amber-500 hover:bg-amber-600 text-white transition shadow-xs flex items-center gap-1.5"
          >
            <span>⚡</span>
            <span>{isCloudOnline ? "Cut Cloud (Mesh Only)" : "Restore Central Cloud"}</span>
          </button>

          {activeNodes.length > 0 && (
            <button
              onClick={handleClearTestNodes}
              disabled={loadingAction !== null}
              className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition border border-slate-200 flex items-center gap-1.5 ml-auto disabled:opacity-50"
            >
              <span>🧹</span>
              <span>Clear Test Nodes</span>
            </button>
          )}
        </div>

        {/* Live Packet Transmission Result Display */}
        {testLog && (
          <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  testLog.status === "DELIVERED"
                    ? "bg-emerald-100 text-emerald-800"
                    : testLog.status === "SOS_RESOLVED"
                    ? "bg-red-100 text-red-800"
                    : "bg-blue-100 text-blue-800"
                }`}>
                  {testLog.status}
                </span>
                <span className="font-bold text-slate-800">{testLog.title}</span>
              </div>
              <p className="text-slate-600 font-sans text-xs">{testLog.message}</p>
            </div>

            {testLog.route && (
              <div className="flex items-center gap-3 bg-slate-50 px-3 py-2 rounded border border-slate-200 shrink-0">
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase">Hops</span>
                  <span className="font-bold text-blue-700">{testLog.hops} hops</span>
                </div>
                <div className="border-l border-slate-200 pl-3">
                  <span className="text-[10px] text-slate-400 block uppercase">Latency</span>
                  <span className="font-bold text-emerald-700">{testLog.latency}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Network KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <Stat
          label="Cloud Status"
          value={network.cloud_status}
          help={isCloudOnline ? "Active 4G/5G Central Uplink" : "BLACKOUT (Mesh Fallback Active)"}
        />
        <Stat
          label="Mesh Status"
          value={network.mesh_status}
          help="Decentralized 802.11p RF Radio"
        />
        <Stat
          label="Connected Nodes"
          value={`${activeNodes.length} / ${Math.max(activeNodes.length, fleet.size)}`}
          help={`${mesh.links.length} dynamic RF peer links`}
        />
        <Stat
          label="Radio Range"
          value={numeric(mesh.transmission_range_km, " km")}
          help="Direct vehicle-to-vehicle RF radius"
        />
        <Stat
          label="Delivery rate"
          value={typeof network.messages_sent === "number" && network.messages_sent > 0 && typeof network.messages_delivered === "number" ? `${((network.messages_delivered / network.messages_sent) * 100).toFixed(0)}%` : "100%"}
          help="Empirical transmission success"
        />
        <Stat
          label="Messages Relayed"
          value={network.messages_sent || 0}
          help="Peer packets & SOS audits"
        />
      </div>

      {/* Mesh Graph & Link Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Topology Visualization */}
        <div className="lg:col-span-2 border border-slate-200 bg-white rounded-xl shadow-sm p-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
                Dynamic Mesh Topology Graph
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Real-time geometric proximity links based on 30 km RF radius
              </p>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
              {network.connected_components || (activeNodes.length > 0 ? 1 : 0)} Connected Subgraphs
            </span>
          </div>

          <div className="h-64 bg-slate-50 rounded-xl p-3 border border-slate-200 relative overflow-hidden">
            <LiveMeshFigure
              mesh={mesh}
              cloudStatus={network.cloud_status}
              activeRecovery={incidents[0]}
              activeRoute={activeRoute}
            />
          </div>

          <div className="flex items-center justify-between mt-3 text-xs text-slate-500 font-mono flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600" /> Active Peer
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Transmitting Path
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Broken Down Node
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 bg-slate-400" /> RF Link (≤30km)
              </span>
            </div>
            <span>Auto-Updated Every 500ms</span>
          </div>
        </div>

        {/* Link Matrix */}
        <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
          <div className="border-b border-slate-100 pb-3 mb-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
              Active Peer Links ({mesh.links.length})
            </h3>
            <p className="text-xs text-slate-400 font-mono mt-0.5">Direct point-to-point radios</p>
          </div>

          <div className="space-y-2 max-h-64 overflow-y-auto">
            {mesh.links.length > 0 ? (
              mesh.links.map((link, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between text-xs font-mono"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-800">{link.source}</span>
                    <span className="text-slate-400">⟷</span>
                    <span className="font-bold text-slate-800">{link.target}</span>
                  </div>
                  <span className="text-slate-500 text-[11px] font-semibold">{link.distance || "18.5"} km</span>
                </div>
              ))
            ) : (
              <div className="text-center py-12 text-xs text-slate-400 font-mono space-y-1">
                <div>No active links within transmission radius</div>
                <div className="text-[11px] text-slate-400">Click &quot;Deploy Test Radio Nodes&quot; above to simulate links</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Decentralized Mesh Radio Chat & Peer Comm Console */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg">💬</span>
              <h3 className="text-sm font-bold text-slate-900 uppercase font-mono tracking-wide">
                Decentralized Radio Mesh Chat &amp; Peer Comm Console
              </h3>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                Multi-Hop Radio Walkie-Talkie
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Send direct or broadcast radio chat packets hop-by-hop across trucks and dispatch depots even during total cellular blackout.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {chatMessages.length} Messages in Corridor Buffer
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Live Chat Stream (7 cols) */}
          <div className="lg:col-span-7 flex flex-col h-96 border border-slate-200 rounded-xl bg-slate-50/70 p-3 overflow-hidden">
            <div className="text-[11px] font-mono text-slate-400 font-bold uppercase tracking-wider pb-2 border-b border-slate-200 flex items-center justify-between">
              <span>Corridor Radio Frequency Transmission Log</span>
              <span className="text-emerald-600 font-semibold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                Listening
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 py-3 pr-1">
              {chatMessages.length > 0 ? (
                chatMessages.map((msg, idx) => {
                  const isBroadcast = msg.receiver === "BROADCAST";
                  const isDepot = msg.sender.includes("HUB");

                  return (
                    <div
                      key={msg.id || idx}
                      className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-2 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              isDepot
                                ? "bg-blue-100 text-blue-800"
                                : "bg-emerald-100 text-emerald-800"
                            }`}
                          >
                            {msg.sender}
                          </span>
                          <span className="text-slate-400">➔</span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              isBroadcast
                                ? "bg-purple-100 text-purple-800"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {isBroadcast ? "📢 BROADCAST" : msg.receiver}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 text-[10px] text-slate-400">
                          <span>{msg.timestamp}</span>
                          {msg.latency_ms && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold">
                              {msg.hop_count} hops · {msg.latency_ms} ms
                            </span>
                          )}
                        </div>
                      </div>

                      <p className="text-slate-800 font-sans text-xs leading-relaxed bg-slate-50/80 p-2.5 rounded-lg border border-slate-100">
                        {msg.message}
                      </p>

                      <div className="text-[10px] text-slate-400 flex items-center gap-1.5 pt-0.5 font-mono">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        <span>Anonymous End-to-End Relay ({msg.hop_count || 1} hops)</span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-slate-400 text-xs text-center space-y-1">
                  <span className="text-xl">📻</span>
                  <span>No mesh radio chat transmissions yet.</span>
                  <span className="text-[11px]">Send a test radio message using the console on the right!</span>
                </div>
              )}
            </div>
          </div>

          {/* Transmitter Control Panel (5 cols) */}
          <div className="lg:col-span-5 flex flex-col justify-between border border-slate-200 rounded-xl bg-white p-4 space-y-4">
            <div className="space-y-3">
              <div className="text-xs font-bold font-mono text-slate-800 uppercase tracking-wide border-b border-slate-100 pb-2">
                📡 RF Transmitter Controls
              </div>

              {/* Sender & Receiver Selectors */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Transmitter (From):
                  </label>
                  <select
                    value={chatSender || (uniqueSenders[0]?.id || "HUB_BKC")}
                    onChange={(e) => setChatSender(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 text-xs outline-none focus:ring-1 focus:ring-blue-500 font-sans"
                  >
                    {uniqueSenders.length > 0 ? (
                      uniqueSenders.map((n) => (
                        <option key={n.id} value={n.id}>
                          {n.name}
                        </option>
                      ))
                    ) : (
                      <>
                        <option value="HUB_BKC">HUB_BKC (Operations)</option>
                        <option value="PEER_VASHI">PEER_VASHI</option>
                        <option value="PEER_LONAVALA">PEER_LONAVALA</option>
                        <option value="PEER_PUNE">PEER_PUNE</option>
                      </>
                    )}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Receiver (To):
                  </label>
                  <select
                    value={chatReceiver}
                    onChange={(e) => setChatReceiver(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 text-xs outline-none focus:ring-1 focus:ring-blue-500 font-sans"
                  >
                    <option value="BROADCAST">📢 BROADCAST (All Swarm Peers)</option>
                    {uniqueSenders.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Tactical Quick Presets */}
              <div className="space-y-1.5 pt-1">
                <span className="text-[11px] font-semibold text-slate-500 block font-mono">
                  Quick Tactical Radio Presets:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {CHAT_PRESETS.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendChat(p.text)}
                      disabled={sendingChat}
                      className="px-2 py-1 text-[11px] rounded bg-slate-100 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 border border-slate-200 transition font-sans text-slate-700 disabled:opacity-50"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Message Input */}
              <div className="pt-2">
                <label className="block text-[11px] font-semibold text-slate-600 mb-1 font-mono">
                  Custom Radio Message:
                </label>
                <textarea
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendChat();
                    }
                  }}
                  rows={3}
                  placeholder="Type an ad-hoc RF radio transmission (Press Enter to transmit)..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs text-slate-800 outline-none focus:ring-1 focus:ring-blue-500 resize-none font-sans"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={() => handleSendChat()}
                disabled={sendingChat || !chatMessage.trim()}
                className="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition shadow-xs flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <span>📡</span>
                <span>{sendingChat ? "Transmitting Packet..." : "Transmit Over Mesh Network"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Connectivity Event Log */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="border-b border-slate-100 pb-3 mb-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
            Telecommunications Event Audit Log
          </h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Decentralized contract-net auctions, packet dispatches, and uplink switches
          </p>
        </div>

        <div className="space-y-2 max-h-56 overflow-y-auto font-mono text-xs">
          {networkEvents.length > 0 ? (
            networkEvents.map((ev, i) => (
              <div
                key={i}
                className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-3"
              >
                <span className="text-slate-400 text-[11px] whitespace-nowrap mt-0.5">
                  {ev.time_str || `${ev.timestamp}m`}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                  ev.type.includes("SOS") || ev.type.includes("BREAK")
                    ? "bg-red-100 text-red-800"
                    : ev.type.includes("CLOUD")
                    ? "bg-amber-100 text-amber-800"
                    : "bg-blue-100 text-blue-800"
                }`}>
                  {ev.type}
                </span>
                <span className="text-slate-700 flex-1">{ev.description}</span>
              </div>
            ))
          ) : (
            <div className="text-center py-6 text-xs text-slate-400 font-mono">
              Nominal mesh communications. No network disruption logged yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import Stat from "../../components/Stat";
import { useDashboardState } from "../../lib/useDashboardState";

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

  // Chat controls
  const [chatSender, setChatSender] = useState("");
  const [chatReceiver, setChatReceiver] = useState("BROADCAST");
  const [chatMessage, setChatMessage] = useState("");
  const [sendingChat, setSendingChat] = useState(false);
  const [liveChats, setLiveChats] = useState([]);

  useEffect(() => {
    fetch("/api/simulation/mesh/chat-history")
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setLiveChats(data);
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

  const chatMessages = liveChats.length > 0 ? liveChats : (mesh.chat_messages || []);

  const allSenders = [
    ...(state.delivery_partners || []).map((p) => ({ id: p.id, name: p.name || p.id })),
    ...(state.vehicles || []).map((v) => ({ id: v.id, name: v.partner_name ? `${v.id} (${v.partner_name})` : v.id })),
    ...(activeNodes || []).map((n) => ({ id: n.id, name: n.id })),
  ];
  const uniqueSenders = Array.from(new Map(allSenders.map((s) => [s.id, s])).values());


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
        setChatMessage("");
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


      {/* Network KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                  <span className="text-[11px]">Send a radio packet using the console on the right!</span>
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

import 'package:flutter/material.dart';
import '../../services/ble_mesh_service.dart';

class MeshCockpitScreen extends StatefulWidget {
  final BleMeshService meshService;
  final String driverId;
  final String deviceId;

  const MeshCockpitScreen({
    super.key,
    required this.meshService,
    required this.driverId,
    required this.deviceId,
  });

  @override
  State<MeshCockpitScreen> createState() => _MeshCockpitScreenState();
}

class _MeshCockpitScreenState extends State<MeshCockpitScreen> {
  @override
  void initState() {
    super.initState();
    widget.meshService.refreshMeshStatus();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.meshService,
      builder: (context, _) {
        final isRunning = widget.meshService.isMeshActive;
        final isGateway = widget.meshService.isInternetGateway;
        final peers = widget.meshService.discoveredPeers;
        final packets = widget.meshService.receivedPackets;
        final logs = widget.meshService.eventLogs;

        return Scaffold(
          appBar: AppBar(
            title: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('BLE Mesh Cockpit', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                Text('Physical Phone-to-Phone Mesh (A → B → C)', style: TextStyle(fontSize: 11, color: Colors.white70)),
              ],
            ),
            backgroundColor: const Color(0xFF0F172A),
            foregroundColor: Colors.white,
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'Refresh Status',
                onPressed: () => widget.meshService.refreshMeshStatus(),
              ),
            ],
          ),
          body: ListView(
            padding: const EdgeInsets.all(16.0),
            children: [
              // 1. Device Hardware Node Status Card
              Card(
                elevation: 2,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Icon(
                                isRunning ? Icons.bluetooth_connected : Icons.bluetooth_disabled,
                                color: isRunning ? Colors.blue : Colors.grey,
                                size: 26,
                              ),
                              const SizedBox(width: 8),
                              const Text('Smartphone Node', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                            ],
                          ),
                          Switch(
                            value: isRunning,
                            onChanged: (val) async {
                              if (val) {
                                await widget.meshService.startMesh(
                                  deviceId: widget.deviceId,
                                  driverId: widget.driverId,
                                );
                              } else {
                                await widget.meshService.stopMesh();
                              }
                            },
                          ),
                        ],
                      ),
                      const Divider(height: 20),
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('DEVICE ID', style: TextStyle(fontSize: 10, color: Colors.grey, fontWeight: FontWeight.bold)),
                                Text(widget.deviceId, style: const TextStyle(fontSize: 13, fontFamily: 'monospace', fontWeight: FontWeight.w600)),
                              ],
                            ),
                          ),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('AUTHENTICATED DRIVER', style: TextStyle(fontSize: 10, color: Colors.grey, fontWeight: FontWeight.bold)),
                                Text(widget.driverId, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 6,
                        children: [
                          _StatusChip(
                            label: isRunning ? 'Advertising: ON' : 'Advertising: OFF',
                            isActive: isRunning,
                            color: Colors.blue,
                          ),
                          _StatusChip(
                            label: isRunning ? 'Scanning: ON' : 'Scanning: OFF',
                            isActive: isRunning,
                            color: Colors.cyan,
                          ),
                          _StatusChip(
                            label: isGateway ? 'Internet Gateway: ACTIVE' : 'Internet: OFFLINE (Mesh Only)',
                            isActive: isGateway,
                            color: isGateway ? Colors.green : Colors.amber,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 2. Discovered Nearby Driver Phones
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Discovered Peers (${peers.length})', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                  if (isRunning)
                    const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              if (peers.isEmpty)
                Card(
                  color: Colors.grey.shade50,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  child: Padding(
                    padding: const EdgeInsets.all(20.0),
                    child: Center(
                      child: Text(
                        isRunning
                            ? 'Scanning for nearby SWARMRoute phones...\nEnsure Bluetooth is enabled on peer devices.'
                            : 'Mesh engine is inactive. Turn on switch above to scan.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                      ),
                    ),
                  ),
                )
              else
                ...peers.map((peer) => Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: Colors.blue.shade50,
                          child: Icon(Icons.phone_android, color: Colors.blue.shade700),
                        ),
                        title: Text(peer.peerId, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                        subtitle: Text(
                          'RSSI: ${peer.rssi} dBm  •  Addr: ${peer.address}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        trailing: ElevatedButton.icon(
                          icon: const Icon(Icons.send, size: 14),
                          label: const Text('Test Hop', style: TextStyle(fontSize: 12)),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            backgroundColor: Colors.indigo,
                            foregroundColor: Colors.white,
                          ),
                          onPressed: () async {
                            final ok = await widget.meshService.sendTestPing(peer.peerId);
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(ok ? 'Test packet sent to ${peer.peerId}' : 'Failed to send packet'),
                                  duration: const Duration(seconds: 2),
                                ),
                              );
                            }
                          },
                        ),
                      ),
                    )),
              const SizedBox(height: 16),

              // 3. Multi-Hop Test Actions
              Card(
                color: Colors.indigo.shade50,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('A → B → C Physical Relay Test', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Colors.indigo)),
                      const SizedBox(height: 6),
                      const Text(
                        'Broadcasts an emergency SOS packet with TTL=5 and Hop=0. Nearby peer forwards to next peer until reaching an internet-connected gateway.',
                        style: TextStyle(fontSize: 12, color: Colors.black87),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: ElevatedButton.icon(
                              icon: const Icon(Icons.warning_amber_rounded),
                              label: const Text('Broadcast Mesh Packet'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.red.shade700,
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(vertical: 12),
                              ),
                              onPressed: () async {
                                final ok = await widget.meshService.broadcastAssistanceRequest(
                                  orderId: 'TEST_ORDER_RELAY',
                                  lat: 19.0760,
                                  lon: 72.8777,
                                  reason: 'PHYSICAL_BLE_MULTI_HOP_TEST',
                                  remainingFuel: 25.0,
                                );
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text(ok ? 'Assistance request broadcasted over mesh' : 'Broadcast error')),
                                  );
                                }
                              },
                            ),
                          ),
                          if (isGateway && widget.meshService.queuedPacketCount > 0) ...[
                            const SizedBox(width: 8),
                            ElevatedButton.icon(
                              icon: const Icon(Icons.cloud_upload),
                              label: Text('Flush (${widget.meshService.queuedPacketCount})'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green.shade700,
                                foregroundColor: Colors.white,
                              ),
                              onPressed: () => widget.meshService.flushGatewayQueue(),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 4. Received / Forwarded Packets Log
              Text('Mesh Packets Ingested (${packets.length})', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              if (packets.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Center(
                      child: Text('No mesh packets received yet.', style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                    ),
                  ),
                )
              else
                ...packets.take(10).map((p) => Card(
                      margin: const EdgeInsets.only(bottom: 6),
                      child: ListTile(
                        dense: true,
                        leading: Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: p.messageType == 'ASSISTANCE_REQUEST' ? Colors.red.shade100 : Colors.blue.shade100,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Icon(
                            p.messageType == 'ASSISTANCE_REQUEST' ? Icons.sos : Icons.data_array,
                            color: p.messageType == 'ASSISTANCE_REQUEST' ? Colors.red.shade800 : Colors.blue.shade800,
                            size: 18,
                          ),
                        ),
                        title: Text('${p.messageType} (Hop ${p.hopCount}, TTL ${p.ttl})', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                        subtitle: Text(
                          'From: ${p.sourceDeviceId} • Msg: ${p.messageId.take(12)}...',
                          style: const TextStyle(fontSize: 11),
                        ),
                        trailing: Text(
                          DateTime.fromMillisecondsSinceEpoch((p.timestamp * 1000).toInt()).toIso8601String().substring(11, 19),
                          style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                        ),
                      ),
                    )),
              const SizedBox(height: 16),

              // 5. Structured BLE Event Log
              Text('Native BLE Structured Events (${logs.length})', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Card(
                color: const Color(0xFF0F172A),
                child: Container(
                  height: 160,
                  padding: const EdgeInsets.all(8.0),
                  child: logs.isEmpty
                      ? const Center(child: Text('Awaiting BLE operations...', style: TextStyle(color: Colors.white54, fontSize: 12)))
                      : ListView.builder(
                          itemCount: logs.length,
                          itemBuilder: (context, idx) {
                            final l = logs[idx];
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 2.0),
                              child: Text(
                                '[${l['time']}] ${l['event']} ${l['details']}',
                                style: const TextStyle(color: Colors.greenAccent, fontFamily: 'monospace', fontSize: 11),
                              ),
                            );
                          },
                        ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String label;
  final bool isActive;
  final MaterialColor color;

  const _StatusChip({required this.label, required this.isActive, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isActive ? color.shade50 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: isActive ? color.shade400 : Colors.grey.shade300),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: isActive ? color.shade800 : Colors.grey.shade700,
        ),
      ),
    );
  }
}

extension on String {
  String take(int n) {
    return length <= n ? this : substring(0, n);
  }
}

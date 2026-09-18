import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';
import '../models/ble_packet_model.dart';
import '../core/api_config.dart';

class BlePeer {
  final String peerId;
  final String address;
  final int rssi;

  BlePeer({required this.peerId, required this.address, required this.rssi});
}

class BleMeshService extends ChangeNotifier {
  static const MethodChannel _channel = MethodChannel('com.swarmroute/ble_mesh');

  bool isMeshActive = false;
  String? currentDeviceId;
  final List<BlePeer> discoveredPeers = [];
  final List<BlePacketModel> receivedPackets = [];

  BleMeshService() {
    _channel.setMethodCallHandler(_handleNativeCall);
  }

  Future<void> _handleNativeCall(MethodCall call) async {
    switch (call.method) {
      case 'onPeerDiscovered':
        final args = Map<String, dynamic>.from(call.arguments as Map);
        final peer = BlePeer(
          peerId: args['peer_id']?.toString() ?? 'PEER',
          address: args['address']?.toString() ?? '',
          rssi: (args['rssi'] as num?)?.toInt() ?? -80,
        );
        final idx = discoveredPeers.indexWhere((p) => p.peerId == peer.peerId);
        if (idx >= 0) {
          discoveredPeers[idx] = peer;
        } else {
          discoveredPeers.add(peer);
        }
        notifyListeners();
        break;

      case 'onPacketReceived':
        final rawJson = call.arguments?.toString() ?? '{}';
        try {
          final data = jsonDecode(rawJson) as Map<String, dynamic>;
          final packet = BlePacketModel.fromJson(data);
          receivedPackets.insert(0, packet);
          notifyListeners();
        } catch (e) {
          debugPrint('[BleMeshService] Packet decode error: $e');
        }
        break;
    }
  }

  Future<bool> startMesh(String deviceId) async {
    currentDeviceId = deviceId;
    try {
      final res = await _channel.invokeMethod<bool>('startMesh', {
        'deviceId': deviceId,
        'backendUrl': ApiConfig.baseUrl,
      });
      isMeshActive = res ?? false;
      notifyListeners();
      return isMeshActive;
    } catch (e) {
      debugPrint('[BleMeshService] Native startMesh error: $e');
      isMeshActive = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> stopMesh() async {
    try {
      await _channel.invokeMethod('stopMesh');
    } catch (_) {}
    isMeshActive = false;
    discoveredPeers.clear();
    notifyListeners();
  }

  Future<bool> broadcastAssistanceRequest({
    required String orderId,
    required double lat,
    required double lon,
    required String reason,
    required double remainingFuel,
  }) async {
    final packet = BlePacketModel(
      messageId: const Uuid().v4(),
      sourceDeviceId: currentDeviceId ?? 'STRANDED_DRIVER',
      destinationDeviceId: 'BROADCAST',
      messageType: 'ASSISTANCE_REQUEST',
      timestamp: DateTime.now().millisecondsSinceEpoch / 1000.0,
      ttl: 5,
      hopCount: 0,
      payload: {
        'order_id': orderId,
        'latitude': lat,
        'longitude': lon,
        'reason': reason,
        'fuel_remaining_liters': remainingFuel,
        'urgency': 'CRITICAL',
      },
    );

    try {
      final ok = await _channel.invokeMethod<bool>('broadcastPacket', {
        'packet': jsonEncode(packet.toJson()),
      });
      return ok ?? false;
    } catch (e) {
      debugPrint('[BleMeshService] Broadcast packet error: $e');
      return false;
    }
  }
}

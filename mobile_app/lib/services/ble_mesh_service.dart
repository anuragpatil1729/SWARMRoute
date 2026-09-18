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
  final int lastSeenMs;

  BlePeer({
    required this.peerId,
    required this.address,
    required this.rssi,
    required this.lastSeenMs,
  });
}

class BleMeshService extends ChangeNotifier {
  static const MethodChannel _channel = MethodChannel('com.swarmroute/ble_mesh');

  bool isMeshActive = false;
  bool isInternetGateway = false;
  String? currentDeviceId;
  String? currentDriverId;
  int queuedPacketCount = 0;

  final List<BlePeer> discoveredPeers = [];
  final List<BlePacketModel> receivedPackets = [];
  final List<Map<String, dynamic>> eventLogs = [];

  BleMeshService() {
    _channel.setMethodCallHandler(_handleNativeCall);
  }

  Future<void> _handleNativeCall(MethodCall call) async {
    switch (call.method) {
      case 'onPeersUpdated':
        final list = (call.arguments as List?) ?? [];
        discoveredPeers.clear();
        for (final item in list) {
          if (item is Map) {
            final m = Map<String, dynamic>.from(item);
            discoveredPeers.add(BlePeer(
              peerId: m['device_id']?.toString() ?? 'PEER',
              address: m['bluetooth_address']?.toString() ?? '',
              rssi: (m['rssi'] as num?)?.toInt() ?? -80,
              lastSeenMs: (m['last_seen_ms'] as num?)?.toInt() ?? DateTime.now().millisecondsSinceEpoch,
            ));
          }
        }
        notifyListeners();
        break;

      case 'onPacketReceived':
        final rawJson = call.arguments?.toString() ?? '{}';
        try {
          final data = jsonDecode(rawJson) as Map<String, dynamic>;
          final packet = BlePacketModel.fromJson(data);
          receivedPackets.insert(0, packet);
          if (receivedPackets.length > 100) {
            receivedPackets.removeLast();
          }
          notifyListeners();
        } catch (e) {
          debugPrint('[BleMeshService] Packet decode error: $e');
        }
        break;

      case 'onGatewayStateChanged':
        final args = Map<String, dynamic>.from(call.arguments as Map? ?? {});
        isInternetGateway = args['has_internet'] as bool? ?? false;
        notifyListeners();
        break;

      case 'onBleEvent':
        final args = Map<String, dynamic>.from(call.arguments as Map? ?? {});
        eventLogs.insert(0, {
          'event': args['event']?.toString() ?? 'UNKNOWN',
          'details': args['details'] ?? {},
          'time': DateTime.now().toIso8601String().substring(11, 19),
        });
        if (eventLogs.length > 100) {
          eventLogs.removeLast();
        }
        notifyListeners();
        break;
    }
  }

  Future<bool> startMesh({required String deviceId, required String driverId}) async {
    currentDeviceId = deviceId;
    currentDriverId = driverId;
    try {
      final res = await _channel.invokeMethod<bool>('startMesh', {
        'deviceId': deviceId,
        'driverId': driverId,
        'backendUrl': ApiConfig.baseUrl,
      });
      isMeshActive = res ?? false;
      await refreshMeshStatus();
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

  Future<Map<String, dynamic>> refreshMeshStatus() async {
    try {
      final res = await _channel.invokeMapMethod<String, dynamic>('getMeshStatus');
      if (res != null) {
        isInternetGateway = res['is_gateway'] as bool? ?? false;
        queuedPacketCount = (res['queue_size'] as num?)?.toInt() ?? 0;
        notifyListeners();
        return res;
      }
    } catch (e) {
      debugPrint('[BleMeshService] getMeshStatus error: $e');
    }
    return {};
  }

  Future<bool> broadcastAssistanceRequest({
    required String orderId,
    required double lat,
    required double lon,
    required String reason,
    required double remainingFuel,
  }) async {
    final packet = BlePacketModel(
      version: 1,
      messageId: const Uuid().v4(),
      sourceDeviceId: currentDeviceId ?? 'DEV_UNKNOWN',
      sourceDriverId: currentDriverId ?? 'DRIVER_UNKNOWN',
      destinationDeviceId: 'BROADCAST',
      messageType: 'ASSISTANCE_REQUEST',
      timestamp: DateTime.now().millisecondsSinceEpoch / 1000.0,
      ttl: 5,
      hopCount: 0,
      payload: {
        'order_id': orderId,
        'driver_id': currentDriverId,
        'latitude': lat,
        'longitude': lon,
        'reason': reason,
        'fuel_remaining_liters': remainingFuel,
        'urgency': 'CRITICAL',
      },
    );

    return broadcastPacket(packet);
  }

  Future<bool> sendTestPing(String targetDeviceId) async {
    final packet = BlePacketModel(
      version: 1,
      messageId: const Uuid().v4(),
      sourceDeviceId: currentDeviceId ?? 'DEV_UNKNOWN',
      sourceDriverId: currentDriverId ?? 'DRIVER_UNKNOWN',
      destinationDeviceId: targetDeviceId,
      messageType: 'HEARTBEAT',
      timestamp: DateTime.now().millisecondsSinceEpoch / 1000.0,
      ttl: 4,
      hopCount: 0,
      payload: {
        'ping_note': 'SWARMRoute Physical BLE Mesh Test Packet',
        'device_from': currentDeviceId,
      },
    );

    return broadcastPacket(packet);
  }

  Future<bool> broadcastPacket(BlePacketModel packet) async {
    try {
      final ok = await _channel.invokeMethod<bool>('broadcastPacket', {
        'packet': jsonEncode(packet.toJson()),
      });
      await refreshMeshStatus();
      return ok ?? false;
    } catch (e) {
      debugPrint('[BleMeshService] Broadcast packet error: $e');
      return false;
    }
  }

  Future<void> flushGatewayQueue() async {
    try {
      await _channel.invokeMethod('flushGatewayQueue');
      await refreshMeshStatus();
    } catch (e) {
      debugPrint('[BleMeshService] flushGatewayQueue error: $e');
    }
  }
}

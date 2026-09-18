class BlePacketModel {
  final int version;
  final String messageId;
  final String sourceDeviceId;
  final String? sourceDriverId;
  final String destinationDeviceId;
  final String messageType;
  final double timestamp;
  final int ttl;
  final int hopCount;
  final Map<String, dynamic> payload;
  final String? signature;
  final String? bridgeDeviceId;

  BlePacketModel({
    this.version = 1,
    required this.messageId,
    required this.sourceDeviceId,
    this.sourceDriverId,
    this.destinationDeviceId = 'BROADCAST',
    required this.messageType,
    required this.timestamp,
    this.ttl = 5,
    this.hopCount = 0,
    required this.payload,
    this.signature,
    this.bridgeDeviceId,
  });

  factory BlePacketModel.fromJson(Map<String, dynamic> json) {
    return BlePacketModel(
      version: (json['version'] as num?)?.toInt() ?? 1,
      messageId: json['message_id']?.toString() ?? '',
      sourceDeviceId: json['source_device_id']?.toString() ?? '',
      sourceDriverId: json['source_driver_id']?.toString(),
      destinationDeviceId: json['destination_device_id']?.toString() ?? 'BROADCAST',
      messageType: json['message_type']?.toString() ?? 'ASSISTANCE_REQUEST',
      timestamp: (json['timestamp'] as num?)?.toDouble() ?? 0.0,
      ttl: (json['ttl'] as num?)?.toInt() ?? 5,
      hopCount: (json['hop_count'] as num?)?.toInt() ?? 0,
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
      signature: json['signature']?.toString(),
      bridgeDeviceId: json['bridge_device_id']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'version': version,
      'message_id': messageId,
      'source_device_id': sourceDeviceId,
      if (sourceDriverId != null) 'source_driver_id': sourceDriverId,
      'destination_device_id': destinationDeviceId,
      'message_type': messageType,
      'timestamp': timestamp,
      'ttl': ttl,
      'hop_count': hopCount,
      'payload': payload,
      if (signature != null) 'signature': signature,
      if (bridgeDeviceId != null) 'bridge_device_id': bridgeDeviceId,
    };
  }
}


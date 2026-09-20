class VehicleModel {
  final String vehicleId;
  final String manufacturer;
  final String modelName;
  final int modelYear;
  final String engineType;
  final String fuelType;
  final double fuelCapacity;
  final double fuelRemaining;
  final double vehicleCondition;
  final double currentLoad;
  final double maxLoad;

  VehicleModel({
    required this.vehicleId,
    required this.manufacturer,
    required this.modelName,
    required this.modelYear,
    required this.engineType,
    required this.fuelType,
    required this.fuelCapacity,
    required this.fuelRemaining,
    required this.vehicleCondition,
    required this.currentLoad,
    required this.maxLoad,
  });

  factory VehicleModel.fromJson(Map<String, dynamic> json) {
    return VehicleModel(
      vehicleId: json['vehicle_id']?.toString() ?? '',
      manufacturer: json['manufacturer']?.toString() ?? 'Tata Motors',
      modelName: json['model_name']?.toString() ?? 'Ace EV',
      modelYear: (json['model_year'] as num?)?.toInt() ?? 2024,
      engineType: json['engine_type']?.toString() ?? 'Electric Drive',
      fuelType: json['fuel_type']?.toString() ?? 'ELECTRIC',
      fuelCapacity: (json['fuel_capacity'] as num?)?.toDouble() ?? 30.0,
      fuelRemaining: (json['fuel_remaining'] as num?)?.toDouble() ?? 80.0,
      vehicleCondition: (json['vehicle_condition'] as num?)?.toDouble() ?? 0.98,
      currentLoad: (json['current_load'] as num?)?.toDouble() ?? 0.0,
      maxLoad: (json['max_load'] as num?)?.toDouble() ?? 500.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'vehicle_id': vehicleId,
      'manufacturer': manufacturer,
      'model_name': modelName,
      'model_year': modelYear,
      'engine_type': engineType,
      'fuel_type': fuelType,
      'fuel_capacity': fuelCapacity,
      'fuel_remaining': fuelRemaining,
      'vehicle_condition': vehicleCondition,
      'current_load': currentLoad,
      'max_load': maxLoad,
    };
  }
}

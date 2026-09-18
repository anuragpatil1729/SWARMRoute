/// Global API Configuration for SWARMRoute Flutter client.
/// Connects to the single authoritative SWARMRoute backend.
class ApiConfig {
  static const String defaultLocalUrl = 'http://10.0.2.2:8000';
  static const String defaultDesktopUrl = 'http://127.0.0.1:8000';
  
  static String baseUrl = const bool.fromEnvironment('dart.vm.product')
      ? 'http://10.0.2.2:8000'
      : defaultDesktopUrl;

  static void setBaseUrl(String url) {
    baseUrl = url.replaceAll(RegExp(r'/+$'), '');
  }

  // Endpoints
  static String get orders => '$baseUrl/api/v1/orders';
  static String trackOrder(String id) => '$baseUrl/api/v1/orders/$id/track';
  static String customerOrders(String customerId) => '$baseUrl/api/v1/customer/orders?customer_id=$customerId';
  static String get liveFleet => '$baseUrl/api/v1/fleet/live';
  static String get dispatchRecommend => '$baseUrl/api/v1/dispatch/recommend';
  static String get dispatchAllocate => '$baseUrl/api/v1/dispatch/allocate';
  static String get driverTelemetry => '$baseUrl/api/v1/driver/telemetry';
  static String updateOrderStatus(String id) => '$baseUrl/api/v1/driver/orders/$id/status';
  static String get routeIntelligence => '$baseUrl/api/v1/route/intelligence';
  static String get meshRelay => '$baseUrl/api/v1/mesh/relay';
}

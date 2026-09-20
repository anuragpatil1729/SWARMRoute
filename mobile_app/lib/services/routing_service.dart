import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

class RouteResult {
  final List<LatLng> points;
  final double distanceKm;
  final double durationMins;
  final String provider;
  final String trafficStatus;
  final bool isAvailable;
  final String? fallbackWarning;

  RouteResult({
    required this.points,
    required this.distanceKm,
    required this.durationMins,
    required this.provider,
    required this.trafficStatus,
    required this.isAvailable,
    this.fallbackWarning,
  });
}

class RoutingService {
  final String osrmBaseUrl;

  RoutingService({this.osrmBaseUrl = 'https://router.project-osrm.org'});

  Future<RouteResult> getRoadRoute(LatLng origin, LatLng destination) async {
    final url = '$osrmBaseUrl/route/v1/driving/'
        '${origin.longitude},${origin.latitude};${destination.longitude},${destination.latitude}'
        '?overview=full&geometries=geojson';

    try {
      final res = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (data['code'] == 'Ok' && (data['routes'] as List).isNotEmpty) {
          final r = data['routes'][0];
          final rawCoords = r['geometry']['coordinates'] as List;
          final latLngList = rawCoords.map((c) => LatLng(c[1] as double, c[0] as double)).toList();

          return RouteResult(
            points: latLngList,
            distanceKm: ((r['distance'] as num).toDouble() / 1000.0),
            durationMins: ((r['duration'] as num).toDouble() / 60.0),
            provider: 'OpenStreetMap / OSRM',
            trafficStatus: 'TRAFFIC DATA UNAVAILABLE',
            isAvailable: true,
          );
        }
      }
    } catch (_) {
      // Fallback
    }

    // Honest Fallback: Never display straight-line as a road!
    final dist = const Distance().as(LengthUnit.Kilometer, origin, destination);
    return RouteResult(
      points: [origin, destination],
      distanceKm: dist,
      durationMins: (dist / 30.0) * 60.0,
      provider: 'ROUTING UNAVAILABLE',
      trafficStatus: 'TRAFFIC DATA UNAVAILABLE',
      isAvailable: false,
      fallbackWarning: 'Straight-line distance is an estimated heuristic only, not a road navigation route.',
    );
  }
}

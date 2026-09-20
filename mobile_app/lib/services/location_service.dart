import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

enum LocationState {
  granted,
  denied,
  permanentlyDenied,
  gpsDisabled,
  unavailable,
}

class LocationData {
  final double latitude;
  final double longitude;
  final double speedKmh;
  final double heading;
  final double accuracy;
  final DateTime timestamp;

  LocationData({
    required this.latitude,
    required this.longitude,
    required this.speedKmh,
    required this.heading,
    required this.accuracy,
    required this.timestamp,
  });
}

class LocationService extends ChangeNotifier {
  LocationState state = LocationState.unavailable;
  LocationData? currentLocation;
  StreamSubscription<Position>? _positionStream;

  Future<LocationState> requestPermissions() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      state = LocationState.gpsDisabled;
      notifyListeners();
      return state;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        state = LocationState.denied;
        notifyListeners();
        return state;
      }
    }

    if (permission == LocationPermission.deniedForever) {
      state = LocationState.permanentlyDenied;
      notifyListeners();
      return state;
    }

    state = LocationState.granted;
    notifyListeners();
    _startPositionTracking();
    return state;
  }

  void _startPositionTracking() {
    _positionStream?.cancel();
    // Reasonable sampling interval: filter distance >= 5 meters
    const locationSettings = LocationSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: 5,
    );

    _positionStream = Geolocator.getPositionStream(locationSettings: locationSettings).listen(
      (Position pos) {
        currentLocation = LocationData(
          latitude: pos.latitude,
          longitude: pos.longitude,
          speedKmh: (pos.speed * 3.6).clamp(0.0, 150.0), // m/s to km/h
          heading: pos.heading,
          accuracy: pos.accuracy,
          timestamp: pos.timestamp,
        );
        notifyListeners();
      },
      onError: (err) {
        debugPrint('[LocationService] GPS error: $err');
      },
    );
  }

  @override
  void dispose() {
    _positionStream?.cancel();
    super.dispose();
  }
}

//
//  Coordinate.swift
//  LocationSpoofer
//
//  Data models for coordinates, locations, and routes
//

import Foundation
import MapKit

// MARK: - Coordinate
struct Coordinate: Codable, Equatable, Hashable {
    let latitude: Double
    let longitude: Double

    var clLocation: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    init(latitude: Double, longitude: Double) {
        self.latitude = latitude
        self.longitude = longitude
    }

    init(from clCoordinate: CLLocationCoordinate2D) {
        self.latitude = clCoordinate.latitude
        self.longitude = clCoordinate.longitude
    }

    /// Calculate distance to another coordinate in meters
    func distance(to other: Coordinate) -> Double {
        let location1 = CLLocation(latitude: latitude, longitude: longitude)
        let location2 = CLLocation(latitude: other.latitude, longitude: other.longitude)
        return location1.distance(from: location2)
    }

    /// Calculate bearing to another coordinate in degrees
    func bearing(to other: Coordinate) -> Double {
        let lat1 = latitude * .pi / 180
        let lat2 = other.latitude * .pi / 180
        let dLon = (other.longitude - longitude) * .pi / 180

        let y = sin(dLon) * cos(lat2)
        let x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLon)

        var bearing = atan2(y, x) * 180 / .pi
        if bearing < 0 {
            bearing += 360
        }
        return bearing
    }

    /// Get a coordinate at a given distance and bearing from this coordinate
    func coordinate(at distance: Double, bearing: Double) -> Coordinate {
        let earthRadius = 6371000.0 // meters
        let bearingRad = bearing * .pi / 180
        let lat1 = latitude * .pi / 180
        let lon1 = longitude * .pi / 180

        let lat2 = asin(sin(lat1) * cos(distance / earthRadius) +
                       cos(lat1) * sin(distance / earthRadius) * cos(bearingRad))

        let lon2 = lon1 + atan2(sin(bearingRad) * sin(distance / earthRadius) * cos(lat1),
                                cos(distance / earthRadius) - sin(lat1) * sin(lat2))

        return Coordinate(
            latitude: lat2 * 180 / .pi,
            longitude: lon2 * 180 / .pi
        )
    }
}

// MARK: - Preset Location
struct PresetLocation: Identifiable, Codable {
    let id: UUID
    let name: String
    let coordinate: Coordinate
    let emoji: String

    init(name: String, latitude: Double, longitude: Double, emoji: String = "📍") {
        self.id = UUID()
        self.name = name
        self.coordinate = Coordinate(latitude: latitude, longitude: longitude)
        self.emoji = emoji
    }

    static let all: [PresetLocation] = [
        PresetLocation(name: "Riyadh", latitude: 24.7136, longitude: 46.6753, emoji: "🇸🇦"),
        PresetLocation(name: "London", latitude: 51.5074, longitude: -0.1278, emoji: "🇬🇧"),
        PresetLocation(name: "New York", latitude: 40.7128, longitude: -74.0060, emoji: "🇺🇸"),
        PresetLocation(name: "Paris", latitude: 48.8566, longitude: 2.3522, emoji: "🇫🇷"),
        PresetLocation(name: "Dubai", latitude: 25.2048, longitude: 55.2708, emoji: "🇦🇪"),
        PresetLocation(name: "Tokyo", latitude: 35.6762, longitude: 139.6503, emoji: "🇯🇵"),
        PresetLocation(name: "Sydney", latitude: -33.8688, longitude: 151.2093, emoji: "🇦🇺"),
        PresetLocation(name: "Singapore", latitude: 1.3521, longitude: 103.8198, emoji: "🇸🇬"),
        PresetLocation(name: "Hong Kong", latitude: 22.3193, longitude: 114.1694, emoji: "🇭🇰"),
        PresetLocation(name: "Mumbai", latitude: 19.0760, longitude: 72.8777, emoji: "🇮🇳"),
    ]
}

// MARK: - Route
struct Route: Identifiable, Codable {
    let id: UUID
    var name: String
    var waypoints: [Coordinate]
    var isLoop: Bool

    init(name: String, waypoints: [Coordinate], isLoop: Bool = false) {
        self.id = UUID()
        self.name = name
        self.waypoints = waypoints
        self.isLoop = isLoop
    }

    /// Calculate total distance of the route in meters
    var totalDistance: Double {
        guard waypoints.count > 1 else { return 0 }
        var total = 0.0
        for i in 0..<waypoints.count - 1 {
            total += waypoints[i].distance(to: waypoints[i + 1])
        }
        if isLoop, let first = waypoints.first, let last = waypoints.last {
            total += last.distance(to: first)
        }
        return total
    }

    /// Interpolate points along the route for smooth movement
    /// - Parameter pointsPerKm: Number of points per kilometer
    /// - Returns: Array of interpolated coordinates
    func interpolate(pointsPerKm: Double = 10) -> [Coordinate] {
        guard waypoints.count > 1 else { return waypoints }

        var points: [Coordinate] = []
        var allWaypoints = waypoints

        if isLoop, let first = waypoints.first {
            allWaypoints.append(first)
        }

        for i in 0..<allWaypoints.count - 1 {
            let start = allWaypoints[i]
            let end = allWaypoints[i + 1]
            let distance = start.distance(to: end)
            let numPoints = max(2, Int(distance / 1000 * pointsPerKm))

            for j in 0..<numPoints {
                let fraction = Double(j) / Double(numPoints)
                let lat = start.latitude + (end.latitude - start.latitude) * fraction
                let lon = start.longitude + (end.longitude - start.longitude) * fraction
                points.append(Coordinate(latitude: lat, longitude: lon))
            }
        }

        if let last = allWaypoints.last {
            points.append(last)
        }

        return points
    }

    // Preset routes
    static let presets: [Route] = [
        Route(
            name: "Riyadh City Tour",
            waypoints: [
                Coordinate(latitude: 24.7136, longitude: 46.6753),
                Coordinate(latitude: 24.7255, longitude: 46.6823),
                Coordinate(latitude: 24.7350, longitude: 46.6900),
                Coordinate(latitude: 24.7200, longitude: 46.7000),
            ],
            isLoop: true
        ),
        Route(
            name: "London Walk",
            waypoints: [
                Coordinate(latitude: 51.5014, longitude: -0.1419), // Buckingham Palace
                Coordinate(latitude: 51.5007, longitude: -0.1246), // Big Ben
                Coordinate(latitude: 51.5080, longitude: -0.0759), // Tower Bridge
            ],
            isLoop: false
        ),
    ]
}

// MARK: - Speed Preset
enum SpeedPreset: String, CaseIterable, Identifiable {
    case walking = "Walking"
    case jogging = "Jogging"
    case cycling = "Cycling"
    case cityDriving = "City Driving"
    case highway = "Highway"

    var id: String { rawValue }

    var speedKmh: Double {
        switch self {
        case .walking: return 5
        case .jogging: return 10
        case .cycling: return 20
        case .cityDriving: return 40
        case .highway: return 100
        }
    }

    var icon: String {
        switch self {
        case .walking: return "figure.walk"
        case .jogging: return "figure.run"
        case .cycling: return "bicycle"
        case .cityDriving: return "car"
        case .highway: return "car.2"
        }
    }
}

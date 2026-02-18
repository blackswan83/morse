//
//  RouteSimulationView.swift
//  LocationSpoofer
//
//  Route drawing and simulation controls (Phase 2 features)
//

import SwiftUI

struct RouteSimulationView: View {
    @Binding var routeWaypoints: [Coordinate]
    @Binding var isDrawingRoute: Bool
    @Binding var currentRoute: Route?
    @ObservedObject var locationManager: LocationManager

    @State private var selectedSpeed: SpeedPreset = .walking
    @State private var customSpeed: Double = 5.0
    @State private var isLooping = false
    @State private var showingRouteList = false
    @State private var routeName = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Route Simulation", systemImage: "point.topleft.down.to.point.bottomright.curvepath.fill")
                    .font(.headline)

                Spacer()

                Button {
                    showingRouteList = true
                } label: {
                    Image(systemName: "list.bullet")
                }
                .buttonStyle(.borderless)
                .help("Saved routes")
            }

            // Drawing mode toggle
            Toggle(isOn: $isDrawingRoute) {
                Label("Draw route on map", systemImage: "pencil.and.outline")
            }
            .toggleStyle(.switch)
            .onChange(of: isDrawingRoute) { _, newValue in
                if !newValue && routeWaypoints.isEmpty {
                    currentRoute = nil
                }
            }

            if !routeWaypoints.isEmpty {
                // Route info
                RouteInfoCard(waypoints: routeWaypoints, isLooping: isLooping)

                // Speed selection
                SpeedSelectionView(
                    selectedSpeed: $selectedSpeed,
                    customSpeed: $customSpeed
                )

                // Loop toggle
                Toggle(isOn: $isLooping) {
                    Label("Loop continuously", systemImage: "repeat")
                }
                .toggleStyle(.switch)

                // Control buttons
                HStack(spacing: 12) {
                    if locationManager.isSimulatingRoute {
                        // Pause/Stop buttons when running
                        Button {
                            locationManager.pauseRouteSimulation()
                        } label: {
                            Image(systemName: locationManager.isRoutePaused ? "play.fill" : "pause.fill")
                            Text(locationManager.isRoutePaused ? "Resume" : "Pause")
                        }
                        .buttonStyle(.bordered)

                        Button(role: .destructive) {
                            locationManager.stopRouteSimulation()
                        } label: {
                            Image(systemName: "stop.fill")
                            Text("Stop")
                        }
                        .buttonStyle(.bordered)
                        .tint(.red)
                    } else {
                        // Start button when not running
                        Button {
                            let route = Route(
                                name: routeName.isEmpty ? "Custom Route" : routeName,
                                waypoints: routeWaypoints,
                                isLoop: isLooping
                            )
                            Task {
                                await locationManager.startRouteSimulation(
                                    route: route,
                                    speedKmh: selectedSpeed == .walking && customSpeed != 5.0 ? customSpeed : selectedSpeed.speedKmh
                                )
                            }
                        } label: {
                            HStack {
                                Image(systemName: "play.fill")
                                Text("Start Simulation")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(routeWaypoints.count < 2)

                        Button(role: .destructive) {
                            routeWaypoints = []
                            currentRoute = nil
                        } label: {
                            Image(systemName: "trash")
                        }
                        .buttonStyle(.bordered)
                        .tint(.red)
                    }
                }

                // Progress indicator when running
                if locationManager.isSimulatingRoute {
                    RouteProgressView(
                        progress: locationManager.routeProgress,
                        currentPointIndex: locationManager.currentRoutePointIndex,
                        totalPoints: locationManager.totalRoutePoints,
                        estimatedTimeRemaining: locationManager.estimatedTimeRemaining
                    )
                }
            } else {
                // Empty state
                VStack(spacing: 8) {
                    Image(systemName: "point.topleft.down.to.point.bottomright.curvepath")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)

                    Text("No route defined")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text("Enable drawing mode and click on the map to add waypoints")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding()
            }
        }
        .sheet(isPresented: $showingRouteList) {
            RouteListSheet(
                routeWaypoints: $routeWaypoints,
                currentRoute: $currentRoute,
                isLooping: $isLooping
            )
        }
    }
}

// MARK: - Route Info Card
struct RouteInfoCard: View {
    let waypoints: [Coordinate]
    let isLooping: Bool

    private var totalDistance: Double {
        guard waypoints.count > 1 else { return 0 }
        var total = 0.0
        for i in 0..<waypoints.count - 1 {
            total += waypoints[i].distance(to: waypoints[i + 1])
        }
        if isLooping, let first = waypoints.first, let last = waypoints.last {
            total += last.distance(to: first)
        }
        return total
    }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("\(waypoints.count) waypoints")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Text(formatDistance(totalDistance))
                    .font(.subheadline.bold())
            }

            Spacer()

            if isLooping {
                Label("Loop", systemImage: "repeat")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.accentColor.opacity(0.2))
                    .cornerRadius(4)
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(8)
    }

    private func formatDistance(_ meters: Double) -> String {
        if meters >= 1000 {
            return String(format: "%.2f km", meters / 1000)
        } else {
            return String(format: "%.0f m", meters)
        }
    }
}

// MARK: - Speed Selection
struct SpeedSelectionView: View {
    @Binding var selectedSpeed: SpeedPreset
    @Binding var customSpeed: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Movement Speed")
                .font(.caption)
                .foregroundColor(.secondary)

            // Speed presets
            HStack(spacing: 8) {
                ForEach(SpeedPreset.allCases) { preset in
                    SpeedPresetButton(
                        preset: preset,
                        isSelected: selectedSpeed == preset
                    ) {
                        selectedSpeed = preset
                        customSpeed = preset.speedKmh
                    }
                }
            }

            // Custom speed slider
            HStack {
                Text("\(Int(customSpeed)) km/h")
                    .font(.caption.monospacedDigit())
                    .frame(width: 60, alignment: .leading)

                Slider(value: $customSpeed, in: 1...150, step: 1)
                    .onChange(of: customSpeed) { _, _ in
                        // Deselect preset if custom value doesn't match
                        if customSpeed != selectedSpeed.speedKmh {
                            // Keep visual selection but use custom speed
                        }
                    }
            }
        }
    }
}

struct SpeedPresetButton: View {
    let preset: SpeedPreset
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: preset.icon)
                    .font(.title3)
                Text("\(Int(preset.speedKmh))")
                    .font(.caption2)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(isSelected ? Color.accentColor.opacity(0.2) : Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.accentColor : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .help("\(preset.rawValue): \(Int(preset.speedKmh)) km/h")
    }
}

// MARK: - Route Progress
struct RouteProgressView: View {
    let progress: Double
    let currentPointIndex: Int
    let totalPoints: Int
    let estimatedTimeRemaining: TimeInterval

    var body: some View {
        VStack(spacing: 8) {
            ProgressView(value: progress, total: 1.0)
                .progressViewStyle(.linear)

            HStack {
                Text("Point \(currentPointIndex + 1) of \(totalPoints)")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Spacer()

                Text(formatTime(estimatedTimeRemaining))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(8)
    }

    private func formatTime(_ seconds: TimeInterval) -> String {
        if seconds < 60 {
            return "\(Int(seconds))s remaining"
        } else if seconds < 3600 {
            return "\(Int(seconds / 60))m remaining"
        } else {
            let hours = Int(seconds / 3600)
            let minutes = Int((seconds.truncatingRemainder(dividingBy: 3600)) / 60)
            return "\(hours)h \(minutes)m remaining"
        }
    }
}

// MARK: - Route List Sheet
struct RouteListSheet: View {
    @Binding var routeWaypoints: [Coordinate]
    @Binding var currentRoute: Route?
    @Binding var isLooping: Bool
    @Environment(\.dismiss) private var dismiss

    @State private var savedRoutes: [Route] = []

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Saved Routes")
                    .font(.headline)

                Spacer()

                Button("Done") {
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()

            Divider()

            if savedRoutes.isEmpty && Route.presets.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "map")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                    Text("No saved routes")
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List {
                    Section("Preset Routes") {
                        ForEach(Route.presets) { route in
                            RouteRowView(route: route) {
                                loadRoute(route)
                            }
                        }
                    }

                    if !savedRoutes.isEmpty {
                        Section("Custom Routes") {
                            ForEach(savedRoutes) { route in
                                RouteRowView(route: route) {
                                    loadRoute(route)
                                }
                            }
                            .onDelete(perform: deleteRoutes)
                        }
                    }
                }
            }
        }
        .frame(width: 400, height: 500)
        .onAppear {
            loadSavedRoutes()
        }
    }

    private func loadRoute(_ route: Route) {
        routeWaypoints = route.waypoints
        currentRoute = route
        isLooping = route.isLoop
        dismiss()
    }

    private func deleteRoutes(at offsets: IndexSet) {
        savedRoutes.remove(atOffsets: offsets)
        saveSavedRoutes()
    }

    private func loadSavedRoutes() {
        if let data = UserDefaults.standard.data(forKey: "savedRoutes"),
           let routes = try? JSONDecoder().decode([Route].self, from: data) {
            savedRoutes = routes
        }
    }

    private func saveSavedRoutes() {
        if let data = try? JSONEncoder().encode(savedRoutes) {
            UserDefaults.standard.set(data, forKey: "savedRoutes")
        }
    }
}

struct RouteRowView: View {
    let route: Route
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(route.name)
                        .font(.headline)

                    Text("\(route.waypoints.count) points • \(formatDistance(route.totalDistance))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                if route.isLoop {
                    Image(systemName: "repeat")
                        .foregroundColor(.secondary)
                }

                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
            }
        }
        .buttonStyle(.plain)
    }

    private func formatDistance(_ meters: Double) -> String {
        if meters >= 1000 {
            return String(format: "%.2f km", meters / 1000)
        } else {
            return String(format: "%.0f m", meters)
        }
    }
}

#Preview {
    RouteSimulationView(
        routeWaypoints: .constant([]),
        isDrawingRoute: .constant(false),
        currentRoute: .constant(nil),
        locationManager: LocationManager()
    )
    .frame(width: 300)
    .padding()
}

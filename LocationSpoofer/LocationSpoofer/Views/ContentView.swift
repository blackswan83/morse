//
//  ContentView.swift
//  LocationSpoofer
//
//  Main application view with map, controls, and status panels
//

import SwiftUI
import MapKit

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var locationManager = LocationManager()
    @StateObject private var deviceManager = DeviceManager()
    @StateObject private var tunnelManager = TunnelManager()

    @State private var selectedCoordinate: Coordinate?
    @State private var searchText = ""
    @State private var showingRouteEditor = false
    @State private var currentRoute: Route?
    @State private var routeWaypoints: [Coordinate] = []
    @State private var isDrawingRoute = false
    @State private var showingOnboarding = false

    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    var body: some View {
        HSplitView {
            // Left Panel - Map
            VStack(spacing: 0) {
                // Search Bar
                SearchBarView(searchText: $searchText, onSearch: searchLocation)
                    .padding()

                // Map
                MapViewRepresentable(
                    selectedCoordinate: $selectedCoordinate,
                    routeWaypoints: $routeWaypoints,
                    isDrawingRoute: $isDrawingRoute,
                    isSpoofingActive: appState.isSpoofingActive
                )
                .overlay(alignment: .topTrailing) {
                    MapOverlayButtons(
                        isDrawingRoute: $isDrawingRoute,
                        routeWaypoints: $routeWaypoints
                    )
                    .padding()
                }
            }
            .frame(minWidth: 500)

            // Right Panel - Controls
            VStack(spacing: 0) {
                // Device Status
                DeviceStatusView(
                    deviceManager: deviceManager,
                    tunnelManager: tunnelManager
                )
                .padding()

                Divider()

                ScrollView {
                    VStack(spacing: 16) {
                        // Current Location Info
                        if let coord = selectedCoordinate {
                            CurrentLocationCard(coordinate: coord)
                        }

                        // Action Buttons
                        ActionButtonsView(
                            selectedCoordinate: selectedCoordinate,
                            locationManager: locationManager,
                            deviceManager: deviceManager,
                            tunnelManager: tunnelManager
                        )

                        Divider()

                        // Quick Locations
                        QuickLocationsView(selectedCoordinate: $selectedCoordinate)

                        Divider()

                        // Route Simulation
                        RouteSimulationView(
                            routeWaypoints: $routeWaypoints,
                            isDrawingRoute: $isDrawingRoute,
                            currentRoute: $currentRoute,
                            locationManager: locationManager
                        )
                    }
                    .padding()
                }
            }
            .frame(width: 320)
            .background(Color(nsColor: .controlBackgroundColor))
        }
        .toolbar {
            ToolbarItem(placement: .navigation) {
                HStack {
                    Image(systemName: "location.circle.fill")
                        .foregroundColor(.accentColor)
                        .font(.title2)
                    Text("Location Spoofer")
                        .font(.headline)
                }
            }

            ToolbarItem(placement: .automatic) {
                Button {
                    showingOnboarding = true
                } label: {
                    Image(systemName: "questionmark.circle")
                }
                .help("Setup Guide")
            }
        }
        .onAppear {
            // Load last used location
            selectedCoordinate = appState.lastUsedLocation

            // Start checking device connection
            deviceManager.startMonitoring()

            // Set up notification handlers
            setupNotificationHandlers()

            // Show onboarding on first launch
            if !hasCompletedOnboarding {
                // Delay slightly so the window is ready
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    showingOnboarding = true
                }
            }
        }
        .sheet(isPresented: $showingOnboarding) {
            OnboardingView(
                isPresented: $showingOnboarding,
                deviceManager: deviceManager,
                tunnelManager: tunnelManager
            )
        }
        .onChange(of: locationManager.isSpoofing) { _, newValue in
            appState.isSpoofingActive = newValue
        }
        .onChange(of: deviceManager.isConnected) { _, newValue in
            appState.deviceConnected = newValue
        }
        .onChange(of: tunnelManager.isRunning) { _, newValue in
            appState.tunnelRunning = newValue
        }
        .alert("Error", isPresented: .constant(locationManager.lastError != nil)) {
            Button("OK") {
                locationManager.lastError = nil
            }
        } message: {
            if let error = locationManager.lastError {
                Text(error)
            }
        }
    }

    private func searchLocation() {
        guard !searchText.isEmpty else { return }

        let searchRequest = MKLocalSearch.Request()
        searchRequest.naturalLanguageQuery = searchText

        let search = MKLocalSearch(request: searchRequest)
        search.start { response, error in
            guard let response = response,
                  let item = response.mapItems.first else {
                return
            }

            let coord = Coordinate(from: item.placemark.coordinate)
            selectedCoordinate = coord
            appState.saveLastLocation(coord)
        }
    }

    private func setupNotificationHandlers() {
        NotificationCenter.default.addObserver(
            forName: .setLocation,
            object: nil,
            queue: .main
        ) { _ in
            if let coord = selectedCoordinate {
                Task {
                    await locationManager.setLocation(coord, tunnelManager: tunnelManager)
                }
            }
        }

        NotificationCenter.default.addObserver(
            forName: .clearLocation,
            object: nil,
            queue: .main
        ) { _ in
            Task {
                await locationManager.clearLocation(tunnelManager: tunnelManager)
            }
        }

        NotificationCenter.default.addObserver(
            forName: .selectPresetLocation,
            object: nil,
            queue: .main
        ) { notification in
            if let location = notification.object as? PresetLocation {
                selectedCoordinate = location.coordinate
                appState.saveLastLocation(location.coordinate)
            }
        }
    }
}

// MARK: - Search Bar
struct SearchBarView: View {
    @Binding var searchText: String
    let onSearch: () -> Void

    var body: some View {
        HStack {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.secondary)

            TextField("Search location...", text: $searchText)
                .textFieldStyle(.plain)
                .onSubmit(onSearch)

            if !searchText.isEmpty {
                Button {
                    searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }

            Button("Search", action: onSearch)
                .buttonStyle(.borderedProminent)
                .disabled(searchText.isEmpty)
        }
        .padding(10)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(8)
    }
}

// MARK: - Current Location Card
struct CurrentLocationCard: View {
    let coordinate: Coordinate

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Selected Location", systemImage: "mappin.circle.fill")
                .font(.headline)
                .foregroundColor(.accentColor)

            HStack {
                VStack(alignment: .leading) {
                    Text("Latitude")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(String(format: "%.6f", coordinate.latitude))
                        .font(.system(.body, design: .monospaced))
                }

                Spacer()

                VStack(alignment: .trailing) {
                    Text("Longitude")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(String(format: "%.6f", coordinate.longitude))
                        .font(.system(.body, design: .monospaced))
                }
            }

            Button {
                let pasteboard = NSPasteboard.general
                pasteboard.clearContents()
                pasteboard.setString("\(coordinate.latitude), \(coordinate.longitude)", forType: .string)
            } label: {
                Label("Copy Coordinates", systemImage: "doc.on.doc")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - Map Overlay Buttons
struct MapOverlayButtons: View {
    @Binding var isDrawingRoute: Bool
    @Binding var routeWaypoints: [Coordinate]

    var body: some View {
        VStack(spacing: 8) {
            Button {
                isDrawingRoute.toggle()
                if !isDrawingRoute {
                    routeWaypoints = []
                }
            } label: {
                Image(systemName: isDrawingRoute ? "pencil.slash" : "pencil.and.outline")
                    .font(.title2)
                    .frame(width: 40, height: 40)
            }
            .buttonStyle(.bordered)
            .help(isDrawingRoute ? "Stop drawing route" : "Draw route on map")

            if isDrawingRoute && !routeWaypoints.isEmpty {
                Button {
                    routeWaypoints = []
                } label: {
                    Image(systemName: "trash")
                        .font(.title2)
                        .frame(width: 40, height: 40)
                }
                .buttonStyle(.bordered)
                .tint(.red)
                .help("Clear route")

                Text("\(routeWaypoints.count) pts")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(.ultraThinMaterial)
                    .cornerRadius(4)
            }
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}

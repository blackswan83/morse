//
//  LocationSpooferApp.swift
//  LocationSpoofer
//
//  iPhone Location Spoofer - Mac App (Option A: SwiftUI + Python Backend)
//  Simulates GPS locations on connected iPhones using pymobiledevice3
//

import SwiftUI

@main
struct LocationSpooferApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .frame(minWidth: 900, minHeight: 600)
        }
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {}

            CommandMenu("Location") {
                Button("Set to Current Pin") {
                    NotificationCenter.default.post(name: .setLocation, object: nil)
                }
                .keyboardShortcut("l", modifiers: .command)

                Button("Clear Location") {
                    NotificationCenter.default.post(name: .clearLocation, object: nil)
                }
                .keyboardShortcut("k", modifiers: .command)

                Divider()

                Menu("Quick Locations") {
                    ForEach(PresetLocation.all) { location in
                        Button(location.name) {
                            NotificationCenter.default.post(
                                name: .selectPresetLocation,
                                object: location
                            )
                        }
                    }
                }
            }

            CommandMenu("Simulation") {
                Button("Start Route") {
                    NotificationCenter.default.post(name: .startRoute, object: nil)
                }
                .keyboardShortcut("r", modifiers: .command)

                Button("Stop Route") {
                    NotificationCenter.default.post(name: .stopRoute, object: nil)
                }
                .keyboardShortcut(".", modifiers: .command)
            }
        }

        Settings {
            SettingsView()
                .environmentObject(appState)
        }

        MenuBarExtra("Location Spoofer", systemImage: appState.isSpoofingActive ? "location.fill" : "location") {
            MenuBarView()
                .environmentObject(appState)
        }
    }
}

// MARK: - Notification Names
extension Notification.Name {
    static let setLocation = Notification.Name("setLocation")
    static let clearLocation = Notification.Name("clearLocation")
    static let selectPresetLocation = Notification.Name("selectPresetLocation")
    static let startRoute = Notification.Name("startRoute")
    static let stopRoute = Notification.Name("stopRoute")
}

// MARK: - App State
class AppState: ObservableObject {
    @Published var isSpoofingActive: Bool = false
    @Published var isRouteRunning: Bool = false
    @Published var currentLocation: Coordinate?
    @Published var lastError: String?
    @Published var deviceConnected: Bool = false
    @Published var tunnelRunning: Bool = false

    @AppStorage("lastLatitude") var lastLatitude: Double = 24.7136
    @AppStorage("lastLongitude") var lastLongitude: Double = 46.6753
    @AppStorage("defaultSpeed") var defaultSpeed: Double = 5.0
    @AppStorage("updateInterval") var updateInterval: Double = 2.0

    var lastUsedLocation: Coordinate {
        Coordinate(latitude: lastLatitude, longitude: lastLongitude)
    }

    func saveLastLocation(_ coord: Coordinate) {
        lastLatitude = coord.latitude
        lastLongitude = coord.longitude
    }
}

//
//  MenuBarView.swift
//  LocationSpoofer
//
//  Menu bar quick access for location spoofing
//

import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Status Header
            HStack {
                Circle()
                    .fill(appState.isSpoofingActive ? Color.green : Color.gray)
                    .frame(width: 8, height: 8)

                Text(appState.isSpoofingActive ? "Spoofing Active" : "Spoofing Inactive")
                    .font(.headline)

                Spacer()
            }
            .padding(.horizontal)
            .padding(.vertical, 10)

            if let coord = appState.currentLocation {
                Text("\(String(format: "%.4f", coord.latitude)), \(String(format: "%.4f", coord.longitude))")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.horizontal)
                    .padding(.bottom, 8)
            }

            Divider()

            // Quick Locations
            ForEach(PresetLocation.all.prefix(6)) { location in
                Button {
                    selectLocation(location)
                } label: {
                    HStack {
                        Text(location.emoji)
                        Text(location.name)
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                .padding(.horizontal)
                .padding(.vertical, 6)
            }

            Divider()

            // Actions
            Button {
                NotificationCenter.default.post(name: .clearLocation, object: nil)
            } label: {
                HStack {
                    Image(systemName: "location.slash")
                    Text("Clear Location")
                    Spacer()
                }
            }
            .buttonStyle(.plain)
            .padding(.horizontal)
            .padding(.vertical, 6)
            .disabled(!appState.isSpoofingActive)

            Divider()

            // Open Main Window
            Button {
                NSApp.activate(ignoringOtherApps: true)
                if let window = NSApp.windows.first(where: { $0.title.contains("Location") || $0.isKeyWindow }) {
                    window.makeKeyAndOrderFront(nil)
                } else {
                    // Open new window if none exists
                    NSApp.windows.first?.makeKeyAndOrderFront(nil)
                }
            } label: {
                HStack {
                    Image(systemName: "macwindow")
                    Text("Open Location Spoofer")
                    Spacer()
                }
            }
            .buttonStyle(.plain)
            .padding(.horizontal)
            .padding(.vertical, 6)

            Button {
                NSApplication.shared.terminate(nil)
            } label: {
                HStack {
                    Image(systemName: "power")
                    Text("Quit")
                    Spacer()
                }
            }
            .buttonStyle(.plain)
            .padding(.horizontal)
            .padding(.vertical, 6)
        }
        .frame(width: 200)
    }

    private func selectLocation(_ location: PresetLocation) {
        appState.saveLastLocation(location.coordinate)
        appState.currentLocation = location.coordinate
        NotificationCenter.default.post(
            name: .selectPresetLocation,
            object: location
        )
        // Trigger location set
        NotificationCenter.default.post(name: .setLocation, object: nil)
    }
}

#Preview {
    MenuBarView()
        .environmentObject(AppState())
}

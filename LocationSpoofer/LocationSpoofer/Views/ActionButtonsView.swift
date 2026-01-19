//
//  ActionButtonsView.swift
//  LocationSpoofer
//
//  Set and Clear location action buttons
//

import SwiftUI

struct ActionButtonsView: View {
    let selectedCoordinate: Coordinate?
    @ObservedObject var locationManager: LocationManager
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager

    private var canSetLocation: Bool {
        selectedCoordinate != nil && deviceManager.isConnected && tunnelManager.isRunning
    }

    var body: some View {
        VStack(spacing: 12) {
            // Set Location Button
            Button {
                guard let coord = selectedCoordinate else { return }
                Task {
                    await locationManager.setLocation(coord, tunnelManager: tunnelManager)
                }
            } label: {
                HStack {
                    if locationManager.isSettingLocation {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "location.fill")
                    }
                    Text("Set Location")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!canSetLocation || locationManager.isSettingLocation)
            .help(setLocationTooltip)

            // Clear Location Button
            Button(role: .destructive) {
                Task {
                    await locationManager.clearLocation(tunnelManager: tunnelManager)
                }
            } label: {
                HStack {
                    if locationManager.isClearingLocation {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "location.slash")
                    }
                    Text("Reset to Real GPS")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .tint(.red)
            .controlSize(.large)
            .disabled(!deviceManager.isConnected || !tunnelManager.isRunning || locationManager.isClearingLocation)

            // Status indicator
            if locationManager.isSpoofing {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Location spoofing active")
                        .font(.caption)
                        .foregroundColor(.green)

                    if let coord = locationManager.currentSpoofedLocation {
                        Text("(\(String(format: "%.4f", coord.latitude)), \(String(format: "%.4f", coord.longitude)))")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 8)
                .padding(.horizontal, 12)
                .background(Color.green.opacity(0.1))
                .cornerRadius(8)
            }
        }
    }

    private var setLocationTooltip: String {
        if selectedCoordinate == nil {
            return "Click on the map to select a location"
        } else if !deviceManager.isConnected {
            return "Connect an iPhone to continue"
        } else if !tunnelManager.isRunning {
            return "Start the tunnel service to continue"
        }
        return "Set the spoofed GPS location on your iPhone"
    }
}

#Preview {
    ActionButtonsView(
        selectedCoordinate: Coordinate(latitude: 24.7136, longitude: 46.6753),
        locationManager: LocationManager(),
        deviceManager: DeviceManager(),
        tunnelManager: TunnelManager()
    )
    .frame(width: 300)
    .padding()
}

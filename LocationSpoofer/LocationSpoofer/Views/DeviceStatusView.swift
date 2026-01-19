//
//  DeviceStatusView.swift
//  LocationSpoofer
//
//  Shows iPhone connection status and tunnel status
//

import SwiftUI

struct DeviceStatusView: View {
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager

    var body: some View {
        VStack(spacing: 12) {
            // Device Connection Status
            HStack {
                Circle()
                    .fill(deviceManager.isConnected ? Color.green : Color.red)
                    .frame(width: 10, height: 10)

                VStack(alignment: .leading, spacing: 2) {
                    Text(deviceManager.isConnected ? "iPhone Connected" : "No iPhone Detected")
                        .font(.headline)

                    if let deviceInfo = deviceManager.deviceInfo {
                        Text(deviceInfo)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("Connect iPhone via USB cable")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()

                if deviceManager.isChecking {
                    ProgressView()
                        .scaleEffect(0.7)
                } else {
                    Button {
                        deviceManager.checkConnection()
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .buttonStyle(.borderless)
                    .help("Refresh device status")
                }
            }

            Divider()

            // Tunnel Status
            HStack {
                Circle()
                    .fill(tunnelManager.isRunning ? Color.green : Color.orange)
                    .frame(width: 10, height: 10)

                VStack(alignment: .leading, spacing: 2) {
                    Text(tunnelManager.isRunning ? "Tunnel Active" : "Tunnel Not Running")
                        .font(.headline)

                    Text(tunnelManager.statusMessage)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }

                Spacer()

                if tunnelManager.isStarting {
                    ProgressView()
                        .scaleEffect(0.7)
                } else if tunnelManager.isRunning {
                    Button {
                        Task {
                            await tunnelManager.stopTunnel()
                        }
                    } label: {
                        Text("Stop")
                            .foregroundColor(.red)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                } else {
                    Button {
                        Task {
                            await tunnelManager.startTunnel()
                        }
                    } label: {
                        Text("Start")
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                }
            }

            // Requirements Warning
            if !deviceManager.isConnected || !tunnelManager.isRunning {
                RequirementsWarningView(
                    deviceConnected: deviceManager.isConnected,
                    tunnelRunning: tunnelManager.isRunning
                )
            }
        }
        .padding()
        .background(Color(nsColor: .windowBackgroundColor))
        .cornerRadius(12)
    }
}

struct RequirementsWarningView: View {
    let deviceConnected: Bool
    let tunnelRunning: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Requirements", systemImage: "exclamationmark.triangle.fill")
                .font(.caption)
                .foregroundColor(.orange)

            VStack(alignment: .leading, spacing: 4) {
                RequirementRow(
                    met: deviceConnected,
                    text: "iPhone connected via USB"
                )

                RequirementRow(
                    met: tunnelRunning,
                    text: "Tunnel service running (requires admin)"
                )

                RequirementRow(
                    met: true, // We assume this is met if device is connected
                    text: "Developer Mode enabled on iPhone"
                )
            }
        }
        .padding()
        .background(Color.orange.opacity(0.1))
        .cornerRadius(8)
    }
}

struct RequirementRow: View {
    let met: Bool
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: met ? "checkmark.circle.fill" : "circle")
                .foregroundColor(met ? .green : .secondary)
                .font(.caption)

            Text(text)
                .font(.caption)
                .foregroundColor(met ? .primary : .secondary)
        }
    }
}

#Preview {
    DeviceStatusView(
        deviceManager: DeviceManager(),
        tunnelManager: TunnelManager()
    )
    .frame(width: 300)
    .padding()
}

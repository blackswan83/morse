//
//  DeviceStatusView.swift
//  LocationSpoofer
//
//  Shows iPhone connection status, trust state, Developer Mode, and tunnel status
//

import SwiftUI

struct DeviceStatusView: View {
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager

    private var statusColor: Color {
        switch deviceManager.deviceState {
        case .disconnected:
            return .red
        case .connected:
            return .orange
        case .paired:
            return .yellow
        case .developerReady:
            return tunnelManager.isRunning ? .green : .blue
        case .error:
            return .red
        }
    }

    var body: some View {
        VStack(spacing: 12) {
            // Device Connection Status
            HStack {
                Circle()
                    .fill(statusColor)
                    .frame(width: 10, height: 10)

                VStack(alignment: .leading, spacing: 2) {
                    Text(deviceStatusTitle)
                        .font(.headline)

                    Text(deviceStatusSubtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
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

            // Tunnel Status (only show if device is ready)
            if deviceManager.deviceState == .developerReady || deviceManager.isPaired {
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

                Divider()
            }

            // Setup Steps - show what's needed
            SetupStepsView(
                deviceState: deviceManager.deviceState,
                isPaired: deviceManager.isPaired,
                isDeveloperModeEnabled: deviceManager.isDeveloperModeEnabled,
                tunnelRunning: tunnelManager.isRunning
            )
        }
        .padding()
        .background(Color(nsColor: .windowBackgroundColor))
        .cornerRadius(12)
    }

    private var deviceStatusTitle: String {
        switch deviceManager.deviceState {
        case .disconnected:
            return "No iPhone Detected"
        case .connected:
            return "iPhone Needs Trust"
        case .paired:
            return deviceManager.isDeveloperModeEnabled ? "iPhone Paired" : "Developer Mode Required"
        case .developerReady:
            return "iPhone Ready"
        case .error(let msg):
            return "Error: \(msg)"
        }
    }

    private var deviceStatusSubtitle: String {
        if let info = deviceManager.deviceInfo {
            var subtitle = info
            if let ios = deviceManager.iosVersion {
                subtitle += " (iOS \(ios))"
            }
            return subtitle
        }

        switch deviceManager.deviceState {
        case .disconnected:
            return "Connect iPhone via USB cable"
        case .connected:
            return "Tap 'Trust' on your iPhone"
        case .paired:
            return deviceManager.isDeveloperModeEnabled ? "Ready" : "Enable Developer Mode in Settings"
        case .developerReady:
            return tunnelManager.isRunning ? "Ready for location spoofing" : "Start tunnel to continue"
        case .error:
            return "Check connection and try again"
        }
    }
}

struct SetupStepsView: View {
    let deviceState: DeviceState
    let isPaired: Bool
    let isDeveloperModeEnabled: Bool
    let tunnelRunning: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Setup Checklist", systemImage: "checklist")
                .font(.caption)
                .foregroundColor(.secondary)

            VStack(alignment: .leading, spacing: 6) {
                // Step 1: Connect iPhone
                SetupStepRow(
                    step: 1,
                    title: "Connect iPhone via USB",
                    isComplete: deviceState != .disconnected,
                    isCurrent: deviceState == .disconnected,
                    instruction: "Use a Lightning or USB-C cable"
                )

                // Step 2: Trust Computer
                SetupStepRow(
                    step: 2,
                    title: "Trust this Mac",
                    isComplete: isPaired,
                    isCurrent: deviceState == .connected,
                    instruction: "Tap 'Trust' on iPhone and enter passcode"
                )

                // Step 3: Enable Developer Mode
                SetupStepRow(
                    step: 3,
                    title: "Enable Developer Mode",
                    isComplete: isDeveloperModeEnabled,
                    isCurrent: isPaired && !isDeveloperModeEnabled,
                    instruction: "Settings → Privacy & Security → Developer Mode → ON"
                )

                // Step 4: Start Tunnel
                SetupStepRow(
                    step: 4,
                    title: "Start Tunnel Service",
                    isComplete: tunnelRunning,
                    isCurrent: isDeveloperModeEnabled && !tunnelRunning,
                    instruction: "Click 'Start' above (requires admin password)"
                )
            }

            // All done message
            if deviceState.isReady && tunnelRunning {
                HStack {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundColor(.green)
                    Text("All set! You can now spoof your location.")
                        .font(.caption)
                        .foregroundColor(.green)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(8)
    }
}

struct SetupStepRow: View {
    let step: Int
    let title: String
    let isComplete: Bool
    let isCurrent: Bool
    let instruction: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            // Step indicator
            ZStack {
                Circle()
                    .fill(isComplete ? Color.green : (isCurrent ? Color.accentColor : Color.secondary.opacity(0.3)))
                    .frame(width: 20, height: 20)

                if isComplete {
                    Image(systemName: "checkmark")
                        .font(.caption2.bold())
                        .foregroundColor(.white)
                } else {
                    Text("\(step)")
                        .font(.caption2.bold())
                        .foregroundColor(isCurrent ? .white : .secondary)
                }
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption)
                    .fontWeight(isCurrent ? .semibold : .regular)
                    .foregroundColor(isComplete ? .secondary : (isCurrent ? .primary : .secondary))

                if isCurrent {
                    Text(instruction)
                        .font(.caption2)
                        .foregroundColor(.accentColor)
                }
            }

            Spacer()
        }
    }
}

#Preview {
    DeviceStatusView(
        deviceManager: DeviceManager(),
        tunnelManager: TunnelManager()
    )
    .frame(width: 320)
    .padding()
}

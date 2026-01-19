//
//  OnboardingView.swift
//  LocationSpoofer
//
//  First-launch tutorial that guides users through setup
//

import SwiftUI

struct OnboardingView: View {
    @Binding var isPresented: Bool
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager

    @State private var currentStep = 0
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    private let totalSteps = 5

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Setup Guide")
                    .font(.title2.bold())

                Spacer()

                Button("Skip") {
                    completeOnboarding()
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
            }
            .padding()

            Divider()

            // Progress indicator
            HStack(spacing: 8) {
                ForEach(0..<totalSteps, id: \.self) { step in
                    Capsule()
                        .fill(step <= currentStep ? Color.accentColor : Color.secondary.opacity(0.3))
                        .frame(height: 4)
                }
            }
            .padding(.horizontal)
            .padding(.top)

            // Content
            TabView(selection: $currentStep) {
                WelcomeStep()
                    .tag(0)

                RequirementsStep()
                    .tag(1)

                ConnectStep(deviceManager: deviceManager)
                    .tag(2)

                DeveloperModeStep(deviceManager: deviceManager)
                    .tag(3)

                TunnelStep(tunnelManager: tunnelManager, deviceManager: deviceManager)
                    .tag(4)
            }
            .tabViewStyle(.automatic)

            Divider()

            // Navigation
            HStack {
                if currentStep > 0 {
                    Button {
                        withAnimation {
                            currentStep -= 1
                        }
                    } label: {
                        HStack {
                            Image(systemName: "chevron.left")
                            Text("Back")
                        }
                    }
                    .buttonStyle(.bordered)
                }

                Spacer()

                if currentStep < totalSteps - 1 {
                    Button {
                        withAnimation {
                            currentStep += 1
                        }
                    } label: {
                        HStack {
                            Text(currentStep == 0 ? "Get Started" : "Next")
                            Image(systemName: "chevron.right")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    Button {
                        completeOnboarding()
                    } label: {
                        HStack {
                            Text("Finish Setup")
                            Image(systemName: "checkmark")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!isSetupComplete)
                }
            }
            .padding()
        }
        .frame(width: 600, height: 500)
    }

    private var isSetupComplete: Bool {
        deviceManager.deviceState.isReady && tunnelManager.isRunning
    }

    private func completeOnboarding() {
        hasCompletedOnboarding = true
        isPresented = false
    }
}

// MARK: - Step 0: Welcome
struct WelcomeStep: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "location.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.accentColor)

            Text("Welcome to Location Spoofer")
                .font(.title.bold())

            Text("This app lets you simulate GPS locations on your iPhone.\nPerfect for privacy when sharing location.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal, 40)

            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(icon: "map", text: "Click anywhere on the map to set location")
                FeatureRow(icon: "point.topleft.down.to.point.bottomright.curvepath", text: "Simulate movement along routes")
                FeatureRow(icon: "star", text: "Quick access to preset cities")
            }
            .padding(.horizontal, 60)

            Spacer()
        }
        .padding()
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(.accentColor)
                .frame(width: 24)
            Text(text)
                .font(.callout)
        }
    }
}

// MARK: - Step 1: Requirements
struct RequirementsStep: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "checklist")
                .font(.system(size: 60))
                .foregroundColor(.orange)

            Text("What You'll Need")
                .font(.title.bold())

            VStack(alignment: .leading, spacing: 16) {
                RequirementItem(
                    icon: "iphone",
                    title: "iPhone with iOS 16+",
                    description: "Older iOS versions may work but aren't fully supported"
                )

                RequirementItem(
                    icon: "cable.connector",
                    title: "USB Cable",
                    description: "Lightning or USB-C cable to connect iPhone to Mac"
                )

                RequirementItem(
                    icon: "hammer",
                    title: "Developer Mode (iOS 16+)",
                    description: "A setting you'll enable on your iPhone"
                )

                RequirementItem(
                    icon: "terminal",
                    title: "Python & pymobiledevice3",
                    description: "Already installed? Great! If not, we'll help you set it up."
                )
            }
            .padding(.horizontal, 40)

            Spacer()
        }
        .padding()
    }
}

struct RequirementItem: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.accentColor)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Step 2: Connect iPhone
struct ConnectStep: View {
    @ObservedObject var deviceManager: DeviceManager

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            ZStack {
                Image(systemName: "iphone")
                    .font(.system(size: 60))
                    .foregroundColor(.secondary)

                if deviceManager.isConnected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.green)
                        .offset(x: 30, y: -30)
                }
            }

            Text("Connect Your iPhone")
                .font(.title.bold())

            // Status
            StatusCard(
                isComplete: deviceManager.isConnected,
                title: deviceManager.isConnected ? "iPhone Connected" : "Waiting for iPhone...",
                subtitle: deviceManager.deviceInfo ?? "Connect via USB cable"
            )

            // Instructions
            VStack(alignment: .leading, spacing: 12) {
                InstructionRow(number: 1, text: "Connect iPhone to Mac using USB cable")

                InstructionRow(number: 2, text: "If prompted on iPhone, tap \"Trust\"")

                InstructionRow(number: 3, text: "Enter your iPhone passcode to confirm")
            }
            .padding(.horizontal, 60)

            if !deviceManager.isPaired && deviceManager.isConnected {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text("Tap \"Trust\" on your iPhone now")
                        .font(.callout)
                        .foregroundColor(.orange)
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)
            }

            if deviceManager.isChecking {
                ProgressView("Checking connection...")
            }

            Button {
                deviceManager.checkConnection()
            } label: {
                Label("Refresh Status", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.bordered)

            Spacer()
        }
        .padding()
        .onAppear {
            deviceManager.checkConnection()
        }
    }
}

// MARK: - Step 3: Developer Mode
struct DeveloperModeStep: View {
    @ObservedObject var deviceManager: DeviceManager
    @State private var showXcodeHelp = false

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            ZStack {
                Image(systemName: "hammer.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.orange)

                if deviceManager.isDeveloperModeEnabled {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.green)
                        .offset(x: 35, y: -30)
                }
            }

            Text("Enable Developer Mode")
                .font(.title.bold())

            // Status
            StatusCard(
                isComplete: deviceManager.isDeveloperModeEnabled,
                title: deviceManager.isDeveloperModeEnabled ? "Developer Mode Enabled" : "Developer Mode Required",
                subtitle: deviceManager.isDeveloperModeEnabled ? "Your iPhone is ready" : "Follow the steps below"
            )

            // Instructions
            VStack(alignment: .leading, spacing: 12) {
                Text("On your iPhone:")
                    .font(.headline)

                InstructionRow(number: 1, text: "Open Settings")
                InstructionRow(number: 2, text: "Go to Privacy & Security")
                InstructionRow(number: 3, text: "Scroll down and tap Developer Mode")
                InstructionRow(number: 4, text: "Toggle ON and restart when prompted")
            }
            .padding(.horizontal, 40)

            // Help for missing Developer Mode option
            Button {
                showXcodeHelp.toggle()
            } label: {
                Label("Don't see Developer Mode option?", systemImage: "questionmark.circle")
            }
            .buttonStyle(.plain)
            .foregroundColor(.accentColor)

            if showXcodeHelp {
                VStack(alignment: .leading, spacing: 8) {
                    Text("If Developer Mode doesn't appear:")
                        .font(.caption.bold())

                    Text("1. Install Xcode from the App Store (free)")
                        .font(.caption)
                    Text("2. Open Xcode and go to Window → Devices")
                        .font(.caption)
                    Text("3. Select your iPhone - this registers it")
                        .font(.caption)
                    Text("4. Now Developer Mode should appear in Settings")
                        .font(.caption)

                    Text("\nAlternatively, pymobiledevice3 may enable it automatically when you run certain commands.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(8)
                .padding(.horizontal, 40)
            }

            Button {
                deviceManager.checkConnection()
            } label: {
                Label("Check Status", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.bordered)

            Spacer()
        }
        .padding()
    }
}

// MARK: - Step 4: Start Tunnel
struct TunnelStep: View {
    @ObservedObject var tunnelManager: TunnelManager
    @ObservedObject var deviceManager: DeviceManager

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            ZStack {
                Image(systemName: "network")
                    .font(.system(size: 60))
                    .foregroundColor(.blue)

                if tunnelManager.isRunning {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.green)
                        .offset(x: 35, y: -30)
                }
            }

            Text("Start Tunnel Service")
                .font(.title.bold())

            Text("The tunnel allows communication with your iPhone's developer services.\nThis requires your Mac administrator password.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal, 40)

            // Status
            StatusCard(
                isComplete: tunnelManager.isRunning,
                title: tunnelManager.isRunning ? "Tunnel Active" : "Tunnel Not Running",
                subtitle: tunnelManager.statusMessage
            )

            if !deviceManager.deviceState.isReady && !deviceManager.isDeveloperModeEnabled {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text("Complete the previous steps first")
                        .font(.callout)
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)
            }

            if tunnelManager.isStarting {
                ProgressView("Starting tunnel...")
            } else if tunnelManager.isRunning {
                HStack {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundColor(.green)
                    Text("You're all set! Click \"Finish Setup\" to start spoofing.")
                        .foregroundColor(.green)
                }
                .padding()
                .background(Color.green.opacity(0.1))
                .cornerRadius(8)
            } else {
                Button {
                    Task {
                        await tunnelManager.startTunnel()
                    }
                } label: {
                    Label("Start Tunnel", systemImage: "play.fill")
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!deviceManager.isPaired)
            }

            Spacer()
        }
        .padding()
    }
}

// MARK: - Helper Views
struct StatusCard: View {
    let isComplete: Bool
    let title: String
    let subtitle: String

    var body: some View {
        HStack {
            Circle()
                .fill(isComplete ? Color.green : Color.orange)
                .frame(width: 12, height: 12)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            if isComplete {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
            }
        }
        .padding()
        .background(isComplete ? Color.green.opacity(0.1) : Color.orange.opacity(0.1))
        .cornerRadius(8)
        .padding(.horizontal, 40)
    }
}

struct InstructionRow: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                Circle()
                    .fill(Color.accentColor)
                    .frame(width: 24, height: 24)
                Text("\(number)")
                    .font(.caption.bold())
                    .foregroundColor(.white)
            }

            Text(text)
                .font(.callout)
        }
    }
}

#Preview {
    OnboardingView(
        isPresented: .constant(true),
        deviceManager: DeviceManager(),
        tunnelManager: TunnelManager()
    )
}

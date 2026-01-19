//
//  OnboardingView.swift
//  LocationSpoofer
//
//  First-launch tutorial that guides users through setup with automatic installation
//

import SwiftUI

struct OnboardingView: View {
    @Binding var isPresented: Bool
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager
    @StateObject private var setupManager = AutoSetupManager()

    @State private var currentStep = 0
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    private let totalSteps = 6

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

                AutoSetupStep(setupManager: setupManager)
                    .tag(1)

                ConnectStep(deviceManager: deviceManager)
                    .tag(2)

                DeveloperModeStep(deviceManager: deviceManager, setupManager: setupManager)
                    .tag(3)

                TunnelStep(tunnelManager: tunnelManager, deviceManager: deviceManager)
                    .tag(4)

                ReadyStep(deviceManager: deviceManager, tunnelManager: tunnelManager)
                    .tag(5)
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
                }
            }
            .padding()
        }
        .frame(width: 650, height: 550)
        .onAppear {
            Task {
                await setupManager.checkAllDependencies()
            }
        }
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
                FeatureRow(icon: "wand.and.stars", text: "Automatic setup - we'll install everything for you!")
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

// MARK: - Step 1: Auto Setup (Dependencies)
struct AutoSetupStep: View {
    @ObservedObject var setupManager: AutoSetupManager

    var allInstalled: Bool {
        setupManager.pythonInstalled && setupManager.pymobiledeviceInstalled
    }

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: allInstalled ? "checkmark.circle.fill" : "shippingbox.fill")
                .font(.system(size: 60))
                .foregroundColor(allInstalled ? .green : .blue)

            Text(allInstalled ? "Dependencies Installed" : "Install Dependencies")
                .font(.title.bold())

            Text(allInstalled
                 ? "All required software is already installed!"
                 : "We'll automatically install the required software.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal, 40)

            // Status cards
            VStack(spacing: 12) {
                DependencyRow(
                    name: "Homebrew",
                    description: "Package manager for macOS",
                    isInstalled: setupManager.homebrewInstalled
                )

                DependencyRow(
                    name: "Python 3",
                    description: "Required for pymobiledevice3",
                    isInstalled: setupManager.pythonInstalled
                )

                DependencyRow(
                    name: "pymobiledevice3",
                    description: "iPhone communication library",
                    isInstalled: setupManager.pymobiledeviceInstalled
                )

                DependencyRow(
                    name: "libimobiledevice",
                    description: "USB device detection",
                    isInstalled: setupManager.libimobiledeviceInstalled
                )
            }
            .padding(.horizontal, 40)

            if !allInstalled {
                if setupManager.isSettingUp {
                    VStack(spacing: 8) {
                        ProgressView(value: setupManager.progress)
                            .padding(.horizontal, 60)

                        Text(setupManager.currentStep)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } else {
                    Button {
                        Task {
                            await setupManager.installAllDependencies()
                        }
                    } label: {
                        Label("Install All Dependencies", systemImage: "arrow.down.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }

                if setupManager.hasError {
                    Text(setupManager.errorMessage)
                        .font(.caption)
                        .foregroundColor(.red)
                        .padding()
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(8)
                }
            }

            // Logs (collapsible)
            if !setupManager.logs.isEmpty {
                DisclosureGroup("Installation Log") {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(setupManager.logs.indices, id: \.self) { index in
                                Text(setupManager.logs[index])
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundColor(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(height: 100)
                    .padding(8)
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(6)
                }
                .padding(.horizontal, 40)
            }

            Spacer()
        }
        .padding()
    }
}

struct DependencyRow: View {
    let name: String
    let description: String
    let isInstalled: Bool

    var body: some View {
        HStack {
            Image(systemName: isInstalled ? "checkmark.circle.fill" : "circle")
                .foregroundColor(isInstalled ? .green : .secondary)

            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.headline)
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Text(isInstalled ? "Installed" : "Required")
                .font(.caption)
                .foregroundColor(isInstalled ? .green : .orange)
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(8)
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
    @ObservedObject var setupManager: AutoSetupManager
    @State private var showManualInstructions = false
    @State private var isTriggering = false

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
                subtitle: deviceManager.isDeveloperModeEnabled ? "Your iPhone is ready" : "We can try to enable this automatically"
            )

            if !deviceManager.isDeveloperModeEnabled {
                // Auto-trigger button
                if isTriggering {
                    ProgressView("Triggering Developer Mode...")
                } else {
                    Button {
                        isTriggering = true
                        Task {
                            _ = await setupManager.triggerDeveloperMode()
                            deviceManager.checkConnection()
                            isTriggering = false
                        }
                    } label: {
                        Label("Auto-Enable Developer Mode", systemImage: "wand.and.stars")
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(!deviceManager.isPaired)
                }

                Text("This will attempt to trigger Developer Mode on your iPhone.\nYou may need to confirm on your device.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)

                Divider()
                    .padding(.horizontal, 60)

                // Manual instructions toggle
                Button {
                    showManualInstructions.toggle()
                } label: {
                    Label(
                        showManualInstructions ? "Hide Manual Instructions" : "Show Manual Instructions",
                        systemImage: showManualInstructions ? "chevron.up" : "chevron.down"
                    )
                }
                .buttonStyle(.plain)
                .foregroundColor(.accentColor)

                if showManualInstructions {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("On your iPhone:")
                            .font(.headline)

                        InstructionRow(number: 1, text: "Open Settings")
                        InstructionRow(number: 2, text: "Go to Privacy & Security")
                        InstructionRow(number: 3, text: "Scroll down and tap Developer Mode")
                        InstructionRow(number: 4, text: "Toggle ON and restart when prompted")

                        Divider()

                        Text("Don't see Developer Mode?")
                            .font(.caption.bold())
                        Text("Install Xcode (free) and connect your iPhone once via Window → Devices")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(8)
                    .padding(.horizontal, 40)
                }
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
                    Text("Tunnel is running!")
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

// MARK: - Step 5: Ready
struct ReadyStep: View {
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager

    var isReady: Bool {
        deviceManager.deviceState.isReady && tunnelManager.isRunning
    }

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            if isReady {
                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 80))
                    .foregroundColor(.green)

                Text("You're All Set!")
                    .font(.title.bold())

                Text("Location Spoofer is ready to use.\nClick anywhere on the map to set your iPhone's location.")
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 40)

                VStack(alignment: .leading, spacing: 12) {
                    FeatureRow(icon: "hand.tap", text: "Click on map to place a pin")
                    FeatureRow(icon: "location.fill", text: "Click \"Set Location\" to apply")
                    FeatureRow(icon: "star.fill", text: "Use quick buttons for preset cities")
                    FeatureRow(icon: "questionmark.circle", text: "Click ? anytime to reopen this guide")
                }
                .padding(.horizontal, 60)
            } else {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 80))
                    .foregroundColor(.orange)

                Text("Almost There!")
                    .font(.title.bold())

                Text("Please complete the previous steps before finishing setup.")
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)

                VStack(alignment: .leading, spacing: 8) {
                    ChecklistRow(text: "Dependencies installed", isComplete: true)
                    ChecklistRow(text: "iPhone connected", isComplete: deviceManager.isConnected)
                    ChecklistRow(text: "iPhone trusted", isComplete: deviceManager.isPaired)
                    ChecklistRow(text: "Developer Mode enabled", isComplete: deviceManager.isDeveloperModeEnabled)
                    ChecklistRow(text: "Tunnel running", isComplete: tunnelManager.isRunning)
                }
                .padding()
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(8)
            }

            Spacer()
        }
        .padding()
    }
}

struct ChecklistRow: View {
    let text: String
    let isComplete: Bool

    var body: some View {
        HStack {
            Image(systemName: isComplete ? "checkmark.circle.fill" : "circle")
                .foregroundColor(isComplete ? .green : .secondary)
            Text(text)
                .foregroundColor(isComplete ? .primary : .secondary)
        }
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

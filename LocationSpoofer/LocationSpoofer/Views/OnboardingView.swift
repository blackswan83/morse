//
//  OnboardingView.swift
//  LocationSpoofer
//
//  Polished first-launch tutorial with illustrations and mock UI
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
    private let stepTitles = ["Welcome", "Install", "Connect", "Developer", "Tunnel", "Ready"]

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

            // Progress indicator
            StepProgressIndicator(
                currentStep: currentStep,
                totalSteps: totalSteps,
                stepTitles: stepTitles
            )
            .padding(.bottom, 8)

            Divider()

            // Content
            TabView(selection: $currentStep) {
                WelcomeStepPolished()
                    .tag(0)

                AutoSetupStepPolished(setupManager: setupManager)
                    .tag(1)

                ConnectStepPolished(deviceManager: deviceManager)
                    .tag(2)

                DeveloperModeStepPolished(deviceManager: deviceManager, setupManager: setupManager)
                    .tag(3)

                TunnelStepPolished(tunnelManager: tunnelManager, deviceManager: deviceManager)
                    .tag(4)

                ReadyStepPolished(deviceManager: deviceManager, tunnelManager: tunnelManager)
                    .tag(5)
            }
            .tabViewStyle(.automatic)

            Divider()

            // Navigation
            HStack {
                if currentStep > 0 {
                    Button {
                        withAnimation(.spring(response: 0.4)) {
                            currentStep -= 1
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                            Text("Back")
                        }
                    }
                    .buttonStyle(.bordered)
                }

                Spacer()

                if currentStep < totalSteps - 1 {
                    Button {
                        withAnimation(.spring(response: 0.4)) {
                            currentStep += 1
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Text(currentStep == 0 ? "Get Started" : "Continue")
                            Image(systemName: "chevron.right")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                } else {
                    Button {
                        completeOnboarding()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "checkmark.circle.fill")
                            Text("Start Using App")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }
            }
            .padding()
        }
        .frame(width: 700, height: 600)
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

// MARK: - Step 0: Welcome (Polished)
struct WelcomeStepPolished: View {
    @State private var isAnimating = false

    var body: some View {
        HStack(spacing: 40) {
            // Left side - Illustration
            ZStack {
                // Animated background
                Circle()
                    .fill(Color.accentColor.opacity(0.1))
                    .frame(width: 200, height: 200)
                    .scaleEffect(isAnimating ? 1.1 : 1)
                    .animation(.easeInOut(duration: 2).repeatForever(autoreverses: true), value: isAnimating)

                // Location pin with pulse
                ZStack {
                    Circle()
                        .stroke(Color.accentColor.opacity(0.3), lineWidth: 2)
                        .frame(width: 100, height: 100)
                        .scaleEffect(isAnimating ? 1.5 : 1)
                        .opacity(isAnimating ? 0 : 1)
                        .animation(.easeOut(duration: 1.5).repeatForever(autoreverses: false), value: isAnimating)

                    Image(systemName: "location.circle.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [.blue, .purple],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                }
            }
            .frame(width: 250)

            // Right side - Content
            VStack(alignment: .leading, spacing: 20) {
                Text("Welcome to\nLocation Spoofer")
                    .font(.largeTitle.bold())
                    .foregroundStyle(
                        LinearGradient(
                            colors: [.primary, .primary.opacity(0.7)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )

                Text("Simulate GPS locations on your iPhone with ease. Perfect for privacy when sharing your location.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                VStack(alignment: .leading, spacing: 16) {
                    FeatureRowPolished(
                        icon: "map.fill",
                        color: .blue,
                        title: "Interactive Map",
                        description: "Click anywhere to set your location"
                    )

                    FeatureRowPolished(
                        icon: "point.topleft.down.to.point.bottomright.curvepath.fill",
                        color: .green,
                        title: "Route Simulation",
                        description: "Simulate movement along custom paths"
                    )

                    FeatureRowPolished(
                        icon: "wand.and.stars",
                        color: .purple,
                        title: "Automatic Setup",
                        description: "We'll install everything for you"
                    )
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(40)
        .onAppear {
            isAnimating = true
        }
    }
}

struct FeatureRowPolished: View {
    let icon: String
    let color: Color
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(color.opacity(0.15))
                    .frame(width: 36, height: 36)

                Image(systemName: icon)
                    .font(.system(size: 16))
                    .foregroundColor(color)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Step 1: Auto Setup (Polished)
struct AutoSetupStepPolished: View {
    @ObservedObject var setupManager: AutoSetupManager

    var allInstalled: Bool {
        setupManager.pythonInstalled && setupManager.pymobiledeviceInstalled
    }

    var body: some View {
        HStack(spacing: 40) {
            // Left - Status
            VStack(spacing: 20) {
                ZStack {
                    Circle()
                        .fill(allInstalled ? Color.green.opacity(0.15) : Color.blue.opacity(0.15))
                        .frame(width: 120, height: 120)

                    Image(systemName: allInstalled ? "checkmark.seal.fill" : "shippingbox.fill")
                        .font(.system(size: 50))
                        .foregroundColor(allInstalled ? .green : .blue)
                }

                Text(allInstalled ? "All Set!" : "Install Required Tools")
                    .font(.title2.bold())

                if !allInstalled {
                    if setupManager.isSettingUp {
                        VStack(spacing: 8) {
                            ProgressView(value: setupManager.progress)
                                .frame(width: 200)

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
                            Label("Install All", systemImage: "arrow.down.circle.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                    }
                }
            }
            .frame(width: 280)

            // Right - Dependency list
            VStack(alignment: .leading, spacing: 16) {
                Text("Required Components")
                    .font(.headline)
                    .foregroundColor(.secondary)

                DependencyCardPolished(
                    name: "Homebrew",
                    description: "macOS package manager",
                    icon: "cup.and.saucer.fill",
                    isInstalled: setupManager.homebrewInstalled
                )

                DependencyCardPolished(
                    name: "Python 3",
                    description: "Programming language runtime",
                    icon: "chevron.left.forwardslash.chevron.right",
                    isInstalled: setupManager.pythonInstalled
                )

                DependencyCardPolished(
                    name: "pymobiledevice3",
                    description: "iPhone communication library",
                    icon: "iphone.and.arrow.forward",
                    isInstalled: setupManager.pymobiledeviceInstalled
                )

                DependencyCardPolished(
                    name: "libimobiledevice",
                    description: "USB device detection",
                    icon: "cable.connector",
                    isInstalled: setupManager.libimobiledeviceInstalled
                )

                if setupManager.hasError {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Text(setupManager.errorMessage)
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
                }
            }
            .frame(maxWidth: .infinity)
        }
        .padding(40)
    }
}

struct DependencyCardPolished: View {
    let name: String
    let description: String
    let icon: String
    let isInstalled: Bool

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(isInstalled ? Color.green.opacity(0.15) : Color.secondary.opacity(0.1))
                    .frame(width: 40, height: 40)

                Image(systemName: icon)
                    .font(.system(size: 16))
                    .foregroundColor(isInstalled ? .green : .secondary)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.subheadline.weight(.medium))
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Image(systemName: isInstalled ? "checkmark.circle.fill" : "circle.dashed")
                .font(.title3)
                .foregroundColor(isInstalled ? .green : .secondary.opacity(0.5))
        }
        .padding(12)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(10)
    }
}

// MARK: - Step 2: Connect iPhone (Polished)
struct ConnectStepPolished: View {
    @ObservedObject var deviceManager: DeviceManager

    var body: some View {
        HStack(spacing: 20) {
            // Left - Illustration
            VStack {
                CableConnectionIllustration(isConnected: deviceManager.isConnected)
                    .frame(height: 150)

                if deviceManager.isConnected && !deviceManager.isPaired {
                    TrustDialogIllustration()
                        .scaleEffect(0.8)
                        .frame(height: 250)
                }
            }
            .frame(width: 320)

            // Right - Instructions
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Circle()
                        .fill(deviceManager.isConnected ? Color.green : Color.orange)
                        .frame(width: 12, height: 12)

                    Text(deviceManager.isConnected ? "iPhone Detected" : "Waiting for iPhone...")
                        .font(.title2.bold())
                }

                if let info = deviceManager.deviceInfo {
                    Text(info)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                Divider()

                VStack(alignment: .leading, spacing: 16) {
                    StepInstruction(
                        number: 1,
                        title: "Connect via USB",
                        description: "Use a Lightning or USB-C cable",
                        isComplete: deviceManager.isConnected
                    )

                    StepInstruction(
                        number: 2,
                        title: "Tap \"Trust\" on iPhone",
                        description: "When the dialog appears, tap Trust",
                        isComplete: deviceManager.isPaired,
                        isCurrent: deviceManager.isConnected && !deviceManager.isPaired
                    )

                    StepInstruction(
                        number: 3,
                        title: "Enter Passcode",
                        description: "Confirm with your iPhone passcode",
                        isComplete: deviceManager.isPaired
                    )
                }

                Spacer()

                Button {
                    deviceManager.checkConnection()
                } label: {
                    Label("Refresh Status", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(40)
        .onAppear {
            deviceManager.checkConnection()
        }
    }
}

struct StepInstruction: View {
    let number: Int
    let title: String
    let description: String
    var isComplete: Bool = false
    var isCurrent: Bool = false

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                Circle()
                    .fill(isComplete ? Color.green : (isCurrent ? Color.accentColor : Color.secondary.opacity(0.2)))
                    .frame(width: 28, height: 28)

                if isComplete {
                    Image(systemName: "checkmark")
                        .font(.caption.bold())
                        .foregroundColor(.white)
                } else {
                    Text("\(number)")
                        .font(.caption.bold())
                        .foregroundColor(isCurrent ? .white : .secondary)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(isComplete ? .secondary : .primary)

                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .opacity(isComplete ? 0.6 : 1)
    }
}

// MARK: - Step 3: Developer Mode (Polished)
struct DeveloperModeStepPolished: View {
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var setupManager: AutoSetupManager
    @State private var isTriggering = false

    var body: some View {
        HStack(spacing: 20) {
            // Left - iOS Mock
            iOSSettingsMock(highlightDeveloperMode: !deviceManager.isDeveloperModeEnabled)
                .scaleEffect(0.85)
                .frame(width: 200)

            // Right - Instructions
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Circle()
                        .fill(deviceManager.isDeveloperModeEnabled ? Color.green : Color.orange)
                        .frame(width: 12, height: 12)

                    Text(deviceManager.isDeveloperModeEnabled ? "Developer Mode Enabled" : "Enable Developer Mode")
                        .font(.title2.bold())
                }

                Text("Developer Mode allows the Mac to access advanced features on your iPhone for location simulation.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Divider()

                if !deviceManager.isDeveloperModeEnabled {
                    // Auto-enable button
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Option 1: Automatic")
                            .font(.headline)

                        if isTriggering {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.8)
                                Text("Attempting to enable...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
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
                            .disabled(!deviceManager.isPaired)
                        }

                        Divider()
                            .padding(.vertical, 8)

                        Text("Option 2: Manual")
                            .font(.headline)

                        VStack(alignment: .leading, spacing: 8) {
                            ManualStep(text: "Open Settings on iPhone")
                            ManualStep(text: "Go to Privacy & Security")
                            ManualStep(text: "Scroll down to Developer Mode")
                            ManualStep(text: "Toggle it ON and restart")
                        }
                    }
                } else {
                    HStack {
                        Image(systemName: "checkmark.seal.fill")
                            .font(.largeTitle)
                            .foregroundColor(.green)
                        Text("Developer Mode is enabled!\nYou're ready for the next step.")
                            .font(.subheadline)
                    }
                    .padding()
                    .background(Color.green.opacity(0.1))
                    .cornerRadius(12)
                }

                Spacer()

                Button {
                    deviceManager.checkConnection()
                } label: {
                    Label("Check Status", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(40)
    }
}

struct ManualStep: View {
    let text: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.accentColor)
            Text(text)
                .font(.caption)
        }
    }
}

// MARK: - Step 4: Tunnel (Polished)
struct TunnelStepPolished: View {
    @ObservedObject var tunnelManager: TunnelManager
    @ObservedObject var deviceManager: DeviceManager

    var body: some View {
        HStack(spacing: 40) {
            // Left - Illustration
            TunnelIllustration(isActive: tunnelManager.isRunning)
                .frame(width: 250)

            // Right - Content
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Circle()
                        .fill(tunnelManager.isRunning ? Color.green : Color.orange)
                        .frame(width: 12, height: 12)

                    Text(tunnelManager.isRunning ? "Tunnel Active" : "Start Tunnel Service")
                        .font(.title2.bold())
                }

                Text("The tunnel creates a secure connection between your Mac and iPhone, allowing location data to be sent.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Divider()

                VStack(alignment: .leading, spacing: 12) {
                    InfoRow(icon: "lock.shield", text: "Requires administrator password")
                    InfoRow(icon: "bolt.fill", text: "Runs in the background")
                    InfoRow(icon: "arrow.triangle.2.circlepath", text: "Auto-restarts if disconnected")
                }

                Spacer()

                if tunnelManager.isStarting {
                    HStack {
                        ProgressView()
                            .scaleEffect(0.8)
                        Text("Starting tunnel...")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                } else if tunnelManager.isRunning {
                    HStack {
                        Image(systemName: "checkmark.seal.fill")
                            .font(.title)
                            .foregroundColor(.green)

                        VStack(alignment: .leading) {
                            Text("Tunnel is running!")
                                .font(.headline)
                                .foregroundColor(.green)
                            Text(tunnelManager.statusMessage)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .background(Color.green.opacity(0.1))
                    .cornerRadius(12)
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

                    if !deviceManager.isPaired {
                        Text("Complete previous steps first")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(40)
    }
}

struct InfoRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundColor(.accentColor)
                .frame(width: 20)

            Text(text)
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Step 5: Ready (Polished)
struct ReadyStepPolished: View {
    @ObservedObject var deviceManager: DeviceManager
    @ObservedObject var tunnelManager: TunnelManager

    var isReady: Bool {
        deviceManager.deviceState.isReady && tunnelManager.isRunning
    }

    var body: some View {
        VStack(spacing: 30) {
            if isReady {
                SuccessCelebration()
                    .frame(height: 150)

                Text("You're All Set!")
                    .font(.largeTitle.bold())

                Text("Location Spoofer is ready to use.\nClick anywhere on the map to simulate your iPhone's location.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)

                // Quick tips
                HStack(spacing: 20) {
                    QuickTipCard(
                        icon: "hand.tap.fill",
                        title: "Click Map",
                        description: "Place a pin"
                    )

                    QuickTipCard(
                        icon: "location.fill",
                        title: "Set Location",
                        description: "Apply to iPhone"
                    )

                    QuickTipCard(
                        icon: "star.fill",
                        title: "Quick Cities",
                        description: "Preset locations"
                    )

                    QuickTipCard(
                        icon: "questionmark.circle.fill",
                        title: "Help",
                        description: "Reopen guide"
                    )
                }
                .padding(.top, 20)
            } else {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.orange)

                Text("Almost There!")
                    .font(.title.bold())

                Text("Complete the remaining steps to finish setup.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                // Checklist
                VStack(alignment: .leading, spacing: 12) {
                    ChecklistItemPolished(text: "Dependencies installed", isComplete: true)
                    ChecklistItemPolished(text: "iPhone connected", isComplete: deviceManager.isConnected)
                    ChecklistItemPolished(text: "Computer trusted", isComplete: deviceManager.isPaired)
                    ChecklistItemPolished(text: "Developer Mode enabled", isComplete: deviceManager.isDeveloperModeEnabled)
                    ChecklistItemPolished(text: "Tunnel running", isComplete: tunnelManager.isRunning)
                }
                .padding()
                .background(Color(nsColor: .controlBackgroundColor))
                .cornerRadius(12)
            }
        }
        .padding(40)
    }
}

struct QuickTipCard: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.accentColor.opacity(0.1))
                    .frame(width: 50, height: 50)

                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(.accentColor)
            }

            Text(title)
                .font(.caption.weight(.semibold))

            Text(description)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .frame(width: 100)
    }
}

struct ChecklistItemPolished: View {
    let text: String
    let isComplete: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: isComplete ? "checkmark.circle.fill" : "circle")
                .font(.title3)
                .foregroundColor(isComplete ? .green : .secondary.opacity(0.5))

            Text(text)
                .font(.subheadline)
                .foregroundColor(isComplete ? .primary : .secondary)

            Spacer()
        }
    }
}

// MARK: - Preview
#Preview {
    OnboardingView(
        isPresented: .constant(true),
        deviceManager: DeviceManager(),
        tunnelManager: TunnelManager()
    )
}

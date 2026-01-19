//
//  OnboardingIllustrations.swift
//  LocationSpoofer
//
//  Stylish illustrations and mock UI for onboarding
//

import SwiftUI

// MARK: - Cable Connection Illustration
struct CableConnectionIllustration: View {
    @State private var isAnimating = false
    let isConnected: Bool

    var body: some View {
        ZStack {
            // Background glow when connected
            if isConnected {
                Circle()
                    .fill(Color.green.opacity(0.2))
                    .frame(width: 200, height: 200)
                    .blur(radius: 30)
            }

            HStack(spacing: isConnected ? 0 : 30) {
                // Mac
                MacIllustration()

                // Cable
                CableIllustration(isConnected: isConnected)
                    .offset(x: isConnected ? 0 : -20)

                // iPhone
                iPhoneIllustration(isConnected: isConnected)
            }
        }
        .animation(.spring(response: 0.6, dampingFraction: 0.7), value: isConnected)
    }
}

struct MacIllustration: View {
    var body: some View {
        ZStack {
            // Screen
            RoundedRectangle(cornerRadius: 8)
                .fill(LinearGradient(
                    colors: [Color(white: 0.15), Color(white: 0.1)],
                    startPoint: .top,
                    endPoint: .bottom
                ))
                .frame(width: 80, height: 55)

            // Screen content
            RoundedRectangle(cornerRadius: 4)
                .fill(LinearGradient(
                    colors: [Color.blue.opacity(0.3), Color.purple.opacity(0.3)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ))
                .frame(width: 70, height: 45)

            // Location icon on screen
            Image(systemName: "location.circle.fill")
                .font(.title2)
                .foregroundColor(.white.opacity(0.8))

            // Stand
            VStack(spacing: 0) {
                Spacer()
                Rectangle()
                    .fill(Color(white: 0.2))
                    .frame(width: 20, height: 15)
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(white: 0.25))
                    .frame(width: 40, height: 4)
            }
            .offset(y: 35)
        }
        .frame(width: 80, height: 90)
    }
}

struct CableIllustration: View {
    let isConnected: Bool

    var body: some View {
        ZStack {
            // Cable wire
            Path { path in
                path.move(to: CGPoint(x: 0, y: 20))
                path.addCurve(
                    to: CGPoint(x: 60, y: 20),
                    control1: CGPoint(x: 20, y: isConnected ? 20 : 35),
                    control2: CGPoint(x: 40, y: isConnected ? 20 : 5)
                )
            }
            .stroke(Color.white.opacity(0.6), lineWidth: 3)

            // USB-C connector (Mac side)
            RoundedRectangle(cornerRadius: 2)
                .fill(Color(white: 0.4))
                .frame(width: 12, height: 6)
                .position(x: 0, y: 20)

            // Lightning/USB-C connector (iPhone side)
            RoundedRectangle(cornerRadius: 1)
                .fill(Color(white: 0.4))
                .frame(width: 8, height: 4)
                .position(x: 60, y: 20)
        }
        .frame(width: 60, height: 40)
    }
}

struct iPhoneIllustration: View {
    let isConnected: Bool

    var body: some View {
        ZStack {
            // iPhone body
            RoundedRectangle(cornerRadius: 12)
                .fill(LinearGradient(
                    colors: [Color(white: 0.2), Color(white: 0.15)],
                    startPoint: .top,
                    endPoint: .bottom
                ))
                .frame(width: 45, height: 90)

            // Screen
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.black)
                .frame(width: 40, height: 80)

            // Dynamic Island
            Capsule()
                .fill(Color.black)
                .frame(width: 20, height: 6)
                .offset(y: -32)

            // Screen content
            VStack(spacing: 4) {
                if isConnected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.green)
                    Text("Connected")
                        .font(.system(size: 6, weight: .medium))
                        .foregroundColor(.white)
                } else {
                    Image(systemName: "cable.connector")
                        .font(.title3)
                        .foregroundColor(.white.opacity(0.5))
                    Text("Connect")
                        .font(.system(size: 6))
                        .foregroundColor(.white.opacity(0.5))
                }
            }

            // Side button
            RoundedRectangle(cornerRadius: 1)
                .fill(Color(white: 0.3))
                .frame(width: 2, height: 15)
                .offset(x: 23, y: -10)
        }
        .frame(width: 45, height: 90)
    }
}

// MARK: - Trust Dialog Illustration
struct TrustDialogIllustration: View {
    @State private var showingDialog = false

    var body: some View {
        ZStack {
            // iPhone
            ZStack {
                RoundedRectangle(cornerRadius: 20)
                    .fill(Color(white: 0.1))
                    .frame(width: 140, height: 280)

                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.black)
                    .frame(width: 130, height: 265)

                // Trust dialog
                VStack(spacing: 0) {
                    // Dialog
                    VStack(spacing: 12) {
                        Image(systemName: "desktopcomputer")
                            .font(.largeTitle)
                            .foregroundColor(.blue)

                        Text("Trust This Computer?")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(.white)

                        Text("Your settings and data will be accessible from this computer when connected.")
                            .font(.system(size: 8))
                            .foregroundColor(.gray)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 8)

                        Divider()
                            .background(Color.gray.opacity(0.3))

                        // Buttons
                        HStack(spacing: 0) {
                            Button {} label: {
                                Text("Don't Trust")
                                    .font(.system(size: 10))
                                    .foregroundColor(.blue)
                                    .frame(maxWidth: .infinity)
                            }

                            Divider()
                                .frame(height: 30)
                                .background(Color.gray.opacity(0.3))

                            Button {} label: {
                                Text("Trust")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundColor(.blue)
                                    .frame(maxWidth: .infinity)
                            }
                        }
                    }
                    .padding(12)
                    .background(Color(white: 0.2))
                    .cornerRadius(12)
                    .frame(width: 110)
                }

                // Dynamic Island
                Capsule()
                    .fill(Color.black)
                    .frame(width: 35, height: 10)
                    .offset(y: -120)
            }

            // Tap indicator
            Circle()
                .stroke(Color.green, lineWidth: 2)
                .frame(width: 30, height: 30)
                .offset(x: 25, y: 50)
                .opacity(showingDialog ? 1 : 0.3)
                .scaleEffect(showingDialog ? 1.2 : 1)
                .animation(.easeInOut(duration: 1).repeatForever(autoreverses: true), value: showingDialog)

            Text("Tap here")
                .font(.caption2)
                .foregroundColor(.green)
                .offset(x: 60, y: 50)
        }
        .onAppear {
            showingDialog = true
        }
    }
}

// MARK: - iOS Settings Mock
struct iOSSettingsMock: View {
    let highlightDeveloperMode: Bool

    var body: some View {
        ZStack {
            // iPhone frame
            RoundedRectangle(cornerRadius: 24)
                .fill(Color(white: 0.1))
                .frame(width: 180, height: 360)

            RoundedRectangle(cornerRadius: 20)
                .fill(Color.black)
                .frame(width: 170, height: 345)

            VStack(spacing: 0) {
                // Status bar
                HStack {
                    Text("9:41")
                        .font(.system(size: 10, weight: .semibold))
                    Spacer()
                    HStack(spacing: 3) {
                        Image(systemName: "cellularbars")
                        Image(systemName: "wifi")
                        Image(systemName: "battery.100")
                    }
                    .font(.system(size: 9))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 12)
                .padding(.top, 8)

                // Navigation bar
                HStack {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.blue)
                    Spacer()
                    Text("Privacy & Security")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(.white)
                    Spacer()
                    Color.clear.frame(width: 20)
                }
                .padding(.horizontal, 8)
                .padding(.top, 8)

                // Settings list
                ScrollView {
                    VStack(spacing: 1) {
                        SettingsRowMock(icon: "location.fill", iconColor: .blue, title: "Location Services")
                        SettingsRowMock(icon: "hand.raised.fill", iconColor: .blue, title: "Tracking")
                        SettingsRowMock(icon: "mic.fill", iconColor: .orange, title: "Microphone")
                        SettingsRowMock(icon: "camera.fill", iconColor: .gray, title: "Camera")

                        // Spacer section
                        Color.clear.frame(height: 20)

                        // Developer Mode - highlighted
                        SettingsRowMock(
                            icon: "hammer.fill",
                            iconColor: .orange,
                            title: "Developer Mode",
                            isHighlighted: highlightDeveloperMode,
                            hasToggle: true
                        )
                    }
                    .padding(.top, 12)
                }

                Spacer()

                // Home indicator
                Capsule()
                    .fill(Color.white.opacity(0.5))
                    .frame(width: 40, height: 4)
                    .padding(.bottom, 8)
            }
            .frame(width: 160, height: 330)

            // Dynamic Island
            Capsule()
                .fill(Color.black)
                .frame(width: 45, height: 12)
                .offset(y: -160)

            // Highlight arrow
            if highlightDeveloperMode {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.right")
                        .font(.caption)
                    Text("Enable this")
                        .font(.caption2)
                }
                .foregroundColor(.green)
                .padding(6)
                .background(Color.green.opacity(0.2))
                .cornerRadius(6)
                .offset(x: -80, y: 80)
            }
        }
    }
}

struct SettingsRowMock: View {
    let icon: String
    let iconColor: Color
    let title: String
    var isHighlighted: Bool = false
    var hasToggle: Bool = false

    @State private var isOn = false

    var body: some View {
        HStack(spacing: 8) {
            // Icon
            ZStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(iconColor)
                    .frame(width: 20, height: 20)
                Image(systemName: icon)
                    .font(.system(size: 10))
                    .foregroundColor(.white)
            }

            Text(title)
                .font(.system(size: 10))
                .foregroundColor(.white)

            Spacer()

            if hasToggle {
                Toggle("", isOn: $isOn)
                    .labelsHidden()
                    .scaleEffect(0.6)
            } else {
                Image(systemName: "chevron.right")
                    .font(.system(size: 8))
                    .foregroundColor(.gray)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(isHighlighted ? Color.green.opacity(0.2) : Color(white: 0.15))
        .overlay(
            RoundedRectangle(cornerRadius: 0)
                .stroke(isHighlighted ? Color.green : Color.clear, lineWidth: 1)
        )
    }
}

// MARK: - Tunnel Illustration
struct TunnelIllustration: View {
    @State private var isAnimating = false
    let isActive: Bool

    var body: some View {
        ZStack {
            // Background
            Circle()
                .fill(isActive ? Color.green.opacity(0.1) : Color.blue.opacity(0.1))
                .frame(width: 150, height: 150)

            // Tunnel visualization
            ZStack {
                // Outer ring
                Circle()
                    .stroke(
                        isActive ? Color.green.opacity(0.3) : Color.blue.opacity(0.3),
                        lineWidth: 3
                    )
                    .frame(width: 120, height: 120)

                // Middle ring
                Circle()
                    .stroke(
                        isActive ? Color.green.opacity(0.5) : Color.blue.opacity(0.5),
                        lineWidth: 2
                    )
                    .frame(width: 80, height: 80)

                // Inner ring
                Circle()
                    .stroke(
                        isActive ? Color.green : Color.blue,
                        lineWidth: 2
                    )
                    .frame(width: 40, height: 40)

                // Data packets (animated)
                ForEach(0..<6, id: \.self) { i in
                    Circle()
                        .fill(isActive ? Color.green : Color.blue)
                        .frame(width: 6, height: 6)
                        .offset(y: isAnimating ? -60 : 0)
                        .rotationEffect(.degrees(Double(i) * 60))
                        .opacity(isAnimating ? 0 : 1)
                        .animation(
                            .easeOut(duration: 1.5)
                            .repeatForever(autoreverses: false)
                            .delay(Double(i) * 0.2),
                            value: isAnimating
                        )
                }

                // Center icon
                Image(systemName: isActive ? "lock.open.fill" : "lock.fill")
                    .font(.title2)
                    .foregroundColor(isActive ? .green : .blue)
            }

            // Mac and iPhone icons
            Image(systemName: "desktopcomputer")
                .font(.title3)
                .foregroundColor(.secondary)
                .offset(x: -80)

            Image(systemName: "iphone")
                .font(.title3)
                .foregroundColor(.secondary)
                .offset(x: 80)

            // Connection line
            Path { path in
                path.move(to: CGPoint(x: -60, y: 0))
                path.addLine(to: CGPoint(x: 60, y: 0))
            }
            .stroke(
                isActive ? Color.green.opacity(0.5) : Color.gray.opacity(0.3),
                style: StrokeStyle(lineWidth: 2, dash: [5, 3])
            )
            .offset(y: 0)
        }
        .frame(width: 200, height: 150)
        .onAppear {
            if isActive {
                isAnimating = true
            }
        }
        .onChange(of: isActive) { _, newValue in
            isAnimating = newValue
        }
    }
}

// MARK: - Success Celebration
struct SuccessCelebration: View {
    @State private var isAnimating = false

    var body: some View {
        ZStack {
            // Confetti-like particles
            ForEach(0..<12, id: \.self) { i in
                Circle()
                    .fill([Color.green, Color.blue, Color.purple, Color.orange][i % 4])
                    .frame(width: 8, height: 8)
                    .offset(
                        x: isAnimating ? CGFloat.random(in: -100...100) : 0,
                        y: isAnimating ? CGFloat.random(in: -100...100) : 0
                    )
                    .opacity(isAnimating ? 0 : 1)
                    .animation(
                        .easeOut(duration: 1)
                        .delay(Double(i) * 0.05),
                        value: isAnimating
                    )
            }

            // Main checkmark
            ZStack {
                Circle()
                    .fill(Color.green)
                    .frame(width: 100, height: 100)
                    .scaleEffect(isAnimating ? 1 : 0.5)

                Image(systemName: "checkmark")
                    .font(.system(size: 50, weight: .bold))
                    .foregroundColor(.white)
                    .scaleEffect(isAnimating ? 1 : 0)
            }
            .animation(.spring(response: 0.5, dampingFraction: 0.6), value: isAnimating)
        }
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                isAnimating = true
            }
        }
    }
}

// MARK: - Step Progress Indicator
struct StepProgressIndicator: View {
    let currentStep: Int
    let totalSteps: Int
    let stepTitles: [String]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(0..<totalSteps, id: \.self) { step in
                HStack(spacing: 0) {
                    // Step circle
                    ZStack {
                        Circle()
                            .fill(step <= currentStep ? Color.accentColor : Color.secondary.opacity(0.3))
                            .frame(width: 28, height: 28)

                        if step < currentStep {
                            Image(systemName: "checkmark")
                                .font(.caption.bold())
                                .foregroundColor(.white)
                        } else {
                            Text("\(step + 1)")
                                .font(.caption.bold())
                                .foregroundColor(step == currentStep ? .white : .secondary)
                        }
                    }

                    // Connector line (except for last step)
                    if step < totalSteps - 1 {
                        Rectangle()
                            .fill(step < currentStep ? Color.accentColor : Color.secondary.opacity(0.3))
                            .frame(height: 2)
                            .frame(maxWidth: .infinity)
                    }
                }
            }
        }
        .padding(.horizontal)
    }
}

// MARK: - Previews
#Preview("Cable Connection") {
    VStack(spacing: 40) {
        CableConnectionIllustration(isConnected: false)
        CableConnectionIllustration(isConnected: true)
    }
    .padding()
    .background(Color(white: 0.05))
}

#Preview("Trust Dialog") {
    TrustDialogIllustration()
        .padding()
        .background(Color(white: 0.05))
}

#Preview("iOS Settings") {
    iOSSettingsMock(highlightDeveloperMode: true)
        .padding()
        .background(Color(white: 0.05))
}

#Preview("Tunnel") {
    VStack(spacing: 40) {
        TunnelIllustration(isActive: false)
        TunnelIllustration(isActive: true)
    }
    .padding()
    .background(Color(white: 0.05))
}

#Preview("Success") {
    SuccessCelebration()
        .frame(width: 300, height: 300)
        .background(Color(white: 0.05))
}

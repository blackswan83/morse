//
//  SettingsView.swift
//  LocationSpoofer
//
//  Application settings and preferences
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @AppStorage("pythonPath") private var pythonPath = "/usr/bin/python3"
    @AppStorage("autoStartTunnel") private var autoStartTunnel = false
    @AppStorage("showMenuBarIcon") private var showMenuBarIcon = true
    @AppStorage("notifyOnLocationChange") private var notifyOnLocationChange = true

    var body: some View {
        TabView {
            GeneralSettingsView(
                autoStartTunnel: $autoStartTunnel,
                showMenuBarIcon: $showMenuBarIcon,
                notifyOnLocationChange: $notifyOnLocationChange
            )
            .tabItem {
                Label("General", systemImage: "gear")
            }

            PythonSettingsView(pythonPath: $pythonPath)
                .tabItem {
                    Label("Python", systemImage: "chevron.left.forwardslash.chevron.right")
                }

            SimulationSettingsView()
                .tabItem {
                    Label("Simulation", systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                }

            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }
        }
        .frame(width: 450, height: 300)
    }
}

// MARK: - General Settings
struct GeneralSettingsView: View {
    @Binding var autoStartTunnel: Bool
    @Binding var showMenuBarIcon: Bool
    @Binding var notifyOnLocationChange: Bool

    var body: some View {
        Form {
            Section {
                Toggle("Auto-start tunnel on launch", isOn: $autoStartTunnel)
                    .help("Automatically start the pymobiledevice3 tunnel when the app launches")

                Toggle("Show menu bar icon", isOn: $showMenuBarIcon)
                    .help("Display a quick-access icon in the menu bar")

                Toggle("Notify on location change", isOn: $notifyOnLocationChange)
                    .help("Show a notification when the spoofed location changes")
            } header: {
                Text("Behavior")
            }

            Section {
                HStack {
                    Text("Last used location")
                    Spacer()
                    Button("Clear") {
                        UserDefaults.standard.removeObject(forKey: "lastLatitude")
                        UserDefaults.standard.removeObject(forKey: "lastLongitude")
                    }
                    .buttonStyle(.bordered)
                }

                HStack {
                    Text("Saved locations")
                    Spacer()
                    Button("Clear All") {
                        UserDefaults.standard.removeObject(forKey: "customLocations")
                    }
                    .buttonStyle(.bordered)
                }

                HStack {
                    Text("Saved routes")
                    Spacer()
                    Button("Clear All") {
                        UserDefaults.standard.removeObject(forKey: "savedRoutes")
                    }
                    .buttonStyle(.bordered)
                }
            } header: {
                Text("Data")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Python Settings
struct PythonSettingsView: View {
    @Binding var pythonPath: String
    @State private var pythonVersion = ""
    @State private var pymobiledeviceVersion = ""
    @State private var isChecking = false
    @State private var errorMessage: String?

    var body: some View {
        Form {
            Section {
                HStack {
                    TextField("Python Path", text: $pythonPath)
                        .textFieldStyle(.roundedBorder)

                    Button("Browse...") {
                        let panel = NSOpenPanel()
                        panel.allowsMultipleSelection = false
                        panel.canChooseDirectories = false
                        panel.canChooseFiles = true
                        panel.directoryURL = URL(fileURLWithPath: "/usr/bin")

                        if panel.runModal() == .OK {
                            pythonPath = panel.url?.path ?? pythonPath
                        }
                    }
                }

                Button("Check Installation") {
                    checkInstallation()
                }
                .disabled(isChecking)

                if isChecking {
                    HStack {
                        ProgressView()
                            .scaleEffect(0.7)
                        Text("Checking...")
                    }
                }

                if !pythonVersion.isEmpty {
                    LabeledContent("Python Version", value: pythonVersion)
                }

                if !pymobiledeviceVersion.isEmpty {
                    LabeledContent("pymobiledevice3", value: pymobiledeviceVersion)
                }

                if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red)
                        .font(.caption)
                }
            } header: {
                Text("Python Configuration")
            }

            Section {
                Text("pymobiledevice3 is required for location spoofing.")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Text("Install with: pip3 install pymobiledevice3")
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)

                Button("Copy Install Command") {
                    let pasteboard = NSPasteboard.general
                    pasteboard.clearContents()
                    pasteboard.setString("pip3 install pymobiledevice3", forType: .string)
                }
                .buttonStyle(.bordered)
            } header: {
                Text("Installation")
            }
        }
        .formStyle(.grouped)
        .padding()
        .onAppear {
            checkInstallation()
        }
    }

    private func checkInstallation() {
        isChecking = true
        errorMessage = nil
        pythonVersion = ""
        pymobiledeviceVersion = ""

        Task {
            // Check Python version
            let pythonCheck = await runCommand(pythonPath, arguments: ["--version"])
            if let version = pythonCheck {
                await MainActor.run {
                    pythonVersion = version.trimmingCharacters(in: .whitespacesAndNewlines)
                }
            } else {
                await MainActor.run {
                    errorMessage = "Python not found at specified path"
                    isChecking = false
                }
                return
            }

            // Check pymobiledevice3
            let pmd3Check = await runCommand(pythonPath, arguments: ["-m", "pymobiledevice3", "--version"])
            await MainActor.run {
                if let version = pmd3Check {
                    pymobiledeviceVersion = version.trimmingCharacters(in: .whitespacesAndNewlines)
                } else {
                    pymobiledeviceVersion = "Not installed"
                    errorMessage = "pymobiledevice3 not found. Install with: pip3 install pymobiledevice3"
                }
                isChecking = false
            }
        }
    }

    private func runCommand(_ command: String, arguments: [String]) async -> String? {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: command)
        process.arguments = arguments

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        do {
            try process.run()
            process.waitUntilExit()

            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return String(data: data, encoding: .utf8)
        } catch {
            return nil
        }
    }
}

// MARK: - Simulation Settings
struct SimulationSettingsView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        Form {
            Section {
                HStack {
                    Text("Default Speed")
                    Spacer()
                    Picker("", selection: Binding(
                        get: { SpeedPreset.allCases.first { $0.speedKmh == appState.defaultSpeed } ?? .walking },
                        set: { appState.defaultSpeed = $0.speedKmh }
                    )) {
                        ForEach(SpeedPreset.allCases) { preset in
                            Text("\(preset.rawValue) (\(Int(preset.speedKmh)) km/h)")
                                .tag(preset)
                        }
                    }
                    .frame(width: 200)
                }

                HStack {
                    Text("Update Interval")
                    Spacer()
                    Picker("", selection: $appState.updateInterval) {
                        Text("1 second").tag(1.0)
                        Text("2 seconds").tag(2.0)
                        Text("3 seconds").tag(3.0)
                        Text("5 seconds").tag(5.0)
                    }
                    .frame(width: 150)
                }
            } header: {
                Text("Route Simulation")
            }

            Section {
                Text("Movement is interpolated between waypoints based on speed.")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Text("Lower update intervals provide smoother movement but use more resources.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } header: {
                Text("Notes")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - About View
struct AboutView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "location.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(.accentColor)

            Text("Location Spoofer")
                .font(.title)
                .bold()

            Text("Version 1.0.0")
                .foregroundColor(.secondary)

            Text("Simulate GPS locations on your iPhone")
                .font(.caption)
                .foregroundColor(.secondary)

            Divider()
                .frame(width: 200)

            VStack(spacing: 8) {
                Text("Requirements:")
                    .font(.caption)
                    .bold()

                Text("• macOS 13.0+")
                Text("• Python 3.x")
                Text("• pymobiledevice3")
                Text("• iPhone with Developer Mode enabled")
            }
            .font(.caption)
            .foregroundColor(.secondary)

            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview {
    SettingsView()
        .environmentObject(AppState())
}

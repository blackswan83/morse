//
//  DeviceManager.swift
//  LocationSpoofer
//
//  Monitors iPhone connection status, trust state, and Developer Mode via pymobiledevice3
//

import Foundation
import Combine

/// Device connection and readiness state
enum DeviceState: Equatable {
    case disconnected
    case connected          // USB connected but not trusted
    case paired             // Trusted but Developer Mode status unknown
    case developerReady     // Fully ready for location spoofing
    case error(String)

    var description: String {
        switch self {
        case .disconnected:
            return "No iPhone detected"
        case .connected:
            return "iPhone connected - Trust required"
        case .paired:
            return "iPhone paired - Checking Developer Mode..."
        case .developerReady:
            return "Ready for location spoofing"
        case .error(let msg):
            return "Error: \(msg)"
        }
    }

    var isReady: Bool {
        self == .developerReady
    }
}

@MainActor
class DeviceManager: ObservableObject {
    @Published var isConnected = false
    @Published var isChecking = false
    @Published var deviceInfo: String?
    @Published var deviceUDID: String?
    @Published var deviceState: DeviceState = .disconnected
    @Published var isPaired = false
    @Published var isDeveloperModeEnabled = false
    @Published var iosVersion: String?

    private var monitorTimer: Timer?
    private var checkTask: Task<Void, Never>?

    @AppStorage("pythonPath") private var pythonPath = "/usr/bin/python3"

    // MARK: - Public Methods

    func startMonitoring() {
        // Check immediately
        checkConnection()

        // Set up periodic checking
        monitorTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkConnection()
            }
        }
    }

    func stopMonitoring() {
        monitorTimer?.invalidate()
        monitorTimer = nil
        checkTask?.cancel()
    }

    func checkConnection() {
        // Cancel any existing check
        checkTask?.cancel()

        checkTask = Task {
            await performConnectionCheck()
        }
    }

    // MARK: - Private Methods

    private func performConnectionCheck() async {
        isChecking = true

        do {
            // Step 1: Check if any device is connected via USB
            let listResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "usbmux", "list", "--no-color"]
            )

            if Task.isCancelled { return }

            let output = listResult.output.trimmingCharacters(in: .whitespacesAndNewlines)

            if listResult.exitCode != 0 || output.isEmpty || output.contains("No devices") {
                // No device connected
                resetState()
                deviceState = .disconnected
                isChecking = false
                return
            }

            // Device found - parse basic info
            isConnected = true
            parseDeviceInfo(output)

            // Step 2: Check if device is paired (trusted)
            // Try to get device info - this will fail if not paired
            let pairResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "lockdown", "info", "--no-color"]
            )

            if Task.isCancelled { return }

            if pairResult.exitCode != 0 {
                // Device connected but not trusted
                deviceState = .connected
                isPaired = false
                isDeveloperModeEnabled = false
                isChecking = false
                return
            }

            // Device is paired - parse detailed info
            isPaired = true
            parseLockdownInfo(pairResult.output)

            // Step 3: Check Developer Mode status (iOS 16+)
            // Try to access developer services
            let devResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "developer", "dvt", "simulate-location", "clear", "--tunnel", ""]
            )

            if Task.isCancelled { return }

            // Check if developer services are accessible
            // Error containing "Developer Mode" or "enable Developer Mode" indicates it's disabled
            let devOutput = devResult.output.lowercased()
            if devOutput.contains("developer mode") && devOutput.contains("enable") {
                deviceState = .paired
                isDeveloperModeEnabled = false
            } else if devResult.exitCode == 0 || !devOutput.contains("error") {
                // Developer services accessible
                deviceState = .developerReady
                isDeveloperModeEnabled = true
            } else {
                // Some other error - might still work
                deviceState = .paired
                isDeveloperModeEnabled = false
            }

        } catch {
            if !Task.isCancelled {
                resetState()
                deviceState = .error(error.localizedDescription)
            }
        }

        if !Task.isCancelled {
            isChecking = false
        }
    }

    private func resetState() {
        isConnected = false
        isPaired = false
        isDeveloperModeEnabled = false
        deviceInfo = nil
        deviceUDID = nil
        iosVersion = nil
    }

    private func parseLockdownInfo(_ output: String) {
        // Parse lockdown info for iOS version and other details
        for line in output.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.contains("ProductVersion") {
                let parts = trimmed.components(separatedBy: ":")
                if parts.count >= 2 {
                    iosVersion = parts[1].trimmingCharacters(in: .whitespaces)
                }
            }
        }
    }

    private func parseDeviceInfo(_ output: String) {
        // pymobiledevice3 usbmux list output format:
        // UDID                                      Product Type  Connection Type  iOS Version  Model
        // xxxxxxxx-xxxxxxxxxxxx                     iPhone14,5    USB              17.2         iPhone 13

        let lines = output.components(separatedBy: "\n")

        // Skip header line
        for line in lines.dropFirst() {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty { continue }

            // Parse columns - they're separated by multiple spaces
            let components = trimmed.components(separatedBy: "  ")
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty }

            if components.count >= 2 {
                deviceUDID = components[0]

                // Build device info string
                var info = ""
                if components.count >= 2 {
                    // Product type (e.g., iPhone14,5 -> iPhone 13)
                    let productType = components[1]
                    info = formatProductType(productType)
                }
                if components.count >= 4 {
                    // iOS version
                    info += " (iOS \(components[3]))"
                }

                deviceInfo = info.isEmpty ? "iPhone" : info
                return
            }
        }

        // Fallback if parsing fails
        if isConnected {
            deviceInfo = "iPhone Connected"
        }
    }

    private func formatProductType(_ type: String) -> String {
        // Map product types to friendly names
        let productMap: [String: String] = [
            "iPhone14,5": "iPhone 13",
            "iPhone14,4": "iPhone 13 mini",
            "iPhone14,2": "iPhone 13 Pro",
            "iPhone14,3": "iPhone 13 Pro Max",
            "iPhone15,2": "iPhone 14 Pro",
            "iPhone15,3": "iPhone 14 Pro Max",
            "iPhone15,4": "iPhone 15",
            "iPhone15,5": "iPhone 15 Plus",
            "iPhone16,1": "iPhone 15 Pro",
            "iPhone16,2": "iPhone 15 Pro Max",
            "iPhone17,1": "iPhone 16 Pro",
            "iPhone17,2": "iPhone 16 Pro Max",
            "iPhone17,3": "iPhone 16",
            "iPhone17,4": "iPhone 16 Plus",
        ]

        return productMap[type] ?? type
    }

    private func runCommand(_ command: String, arguments: [String]) async throws -> CommandResult {
        return try await withCheckedThrowingContinuation { continuation in
            Task.detached {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: command)
                process.arguments = arguments

                let outputPipe = Pipe()
                let errorPipe = Pipe()
                process.standardOutput = outputPipe
                process.standardError = errorPipe

                do {
                    try process.run()
                    process.waitUntilExit()

                    let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
                    let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()

                    let output = String(data: outputData, encoding: .utf8) ?? ""
                    let errorOutput = String(data: errorData, encoding: .utf8) ?? ""

                    let result = CommandResult(
                        exitCode: Int(process.terminationStatus),
                        output: output.isEmpty ? errorOutput : output
                    )
                    continuation.resume(returning: result)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    deinit {
        monitorTimer?.invalidate()
    }
}

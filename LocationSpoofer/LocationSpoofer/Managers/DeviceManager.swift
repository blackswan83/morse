//
//  DeviceManager.swift
//  LocationSpoofer
//
//  Monitors iPhone connection status via pymobiledevice3
//

import Foundation
import Combine

@MainActor
class DeviceManager: ObservableObject {
    @Published var isConnected = false
    @Published var isChecking = false
    @Published var deviceInfo: String?
    @Published var deviceUDID: String?

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
            // Use pymobiledevice3 to list devices
            let result = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "usbmux", "list", "--no-color"]
            )

            if Task.isCancelled { return }

            // Parse the output
            let output = result.output.trimmingCharacters(in: .whitespacesAndNewlines)

            if result.exitCode == 0 && !output.isEmpty && !output.contains("No devices") {
                // Device found - parse details
                isConnected = true
                parseDeviceInfo(output)
            } else {
                isConnected = false
                deviceInfo = nil
                deviceUDID = nil
            }
        } catch {
            if !Task.isCancelled {
                isConnected = false
                deviceInfo = nil
                deviceUDID = nil
            }
        }

        if !Task.isCancelled {
            isChecking = false
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

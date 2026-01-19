//
//  TunnelManager.swift
//  LocationSpoofer
//
//  Manages the pymobiledevice3 tunnel service with admin privileges
//

import Foundation
import Combine
import SwiftUI
import Security

@MainActor
class TunnelManager: ObservableObject {
    @Published var isRunning = false
    @Published var isStarting = false
    @Published var statusMessage = "Tunnel not running"

    private var tunnelProcess: Process?
    private var statusCheckTimer: Timer?

    @AppStorage("pythonPath") private var pythonPath = "/usr/bin/python3"

    // MARK: - Public Methods

    func startTunnel() async {
        guard !isRunning && !isStarting else { return }

        isStarting = true
        statusMessage = "Starting tunnel..."

        do {
            // The tunnel requires sudo, so we need to use AppleScript to get admin privileges
            let success = try await startTunnelWithAdminPrivileges()

            if success {
                // Wait a moment for the tunnel to initialize
                try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds

                // Verify tunnel is running
                let isActive = await checkTunnelStatus()
                isRunning = isActive

                if isActive {
                    statusMessage = "Tunnel running"
                    startStatusMonitoring()
                } else {
                    statusMessage = "Tunnel failed to start"
                }
            } else {
                statusMessage = "Failed to start tunnel (admin required)"
            }
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }

        isStarting = false
    }

    func stopTunnel() async {
        stopStatusMonitoring()

        // Kill any running tunnel processes
        let script = """
        do shell script "pkill -f 'pymobiledevice3 remote tunneld'" with administrator privileges
        """

        let appleScript = NSAppleScript(source: script)
        var error: NSDictionary?
        appleScript?.executeAndReturnError(&error)

        // Also try without admin in case it was started differently
        let killProcess = Process()
        killProcess.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        killProcess.arguments = ["-f", "pymobiledevice3 remote tunneld"]
        try? killProcess.run()
        killProcess.waitUntilExit()

        isRunning = false
        statusMessage = "Tunnel stopped"
    }

    func checkTunnelStatus() async -> Bool {
        do {
            // Check if tunnel process is running
            let result = try await runCommand(
                "/usr/bin/pgrep",
                arguments: ["-f", "pymobiledevice3 remote tunneld"]
            )

            return result.exitCode == 0 && !result.output.isEmpty
        } catch {
            return false
        }
    }

    // MARK: - Private Methods

    private func startTunnelWithAdminPrivileges() async throws -> Bool {
        // Create a shell script to run the tunnel
        let scriptContent = """
        #!/bin/bash
        "\(pythonPath)" -m pymobiledevice3 remote tunneld &
        """

        // Write script to temp file
        let tempDir = FileManager.default.temporaryDirectory
        let scriptPath = tempDir.appendingPathComponent("start_tunnel.sh")

        try scriptContent.write(to: scriptPath, atomically: true, encoding: .utf8)

        // Make executable
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: scriptPath.path
        )

        // Run with admin privileges using AppleScript
        let appleScript = """
        do shell script "\(scriptPath.path)" with administrator privileges
        """

        return await withCheckedContinuation { continuation in
            DispatchQueue.global().async {
                let script = NSAppleScript(source: appleScript)
                var error: NSDictionary?
                script?.executeAndReturnError(&error)

                // Clean up
                try? FileManager.default.removeItem(at: scriptPath)

                let success = error == nil
                continuation.resume(returning: success)
            }
        }
    }

    private func startStatusMonitoring() {
        statusCheckTimer = Timer.scheduledTimer(withTimeInterval: 10.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self else { return }
                let isActive = await self.checkTunnelStatus()
                if !isActive && self.isRunning {
                    self.isRunning = false
                    self.statusMessage = "Tunnel stopped unexpectedly"
                }
            }
        }
    }

    private func stopStatusMonitoring() {
        statusCheckTimer?.invalidate()
        statusCheckTimer = nil
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
        statusCheckTimer?.invalidate()
    }
}

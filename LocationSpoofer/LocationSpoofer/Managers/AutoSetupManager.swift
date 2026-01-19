//
//  AutoSetupManager.swift
//  LocationSpoofer
//
//  Automatically installs dependencies and triggers Developer Mode to appear
//

import Foundation
import AppKit
import SwiftUI

@MainActor
class AutoSetupManager: ObservableObject {
    @Published var isSettingUp = false
    @Published var currentStep = ""
    @Published var progress: Double = 0
    @Published var logs: [String] = []
    @Published var hasError = false
    @Published var errorMessage = ""

    // Dependency status
    @Published var homebrewInstalled = false
    @Published var pythonInstalled = false
    @Published var pymobiledeviceInstalled = false
    @Published var libimobiledeviceInstalled = false

    @AppStorage("pythonPath") private var pythonPath = "/usr/bin/python3"

    // MARK: - Check Dependencies

    func checkAllDependencies() async {
        logs.append("Checking dependencies...")

        // Check Homebrew
        homebrewInstalled = await checkCommand("/opt/homebrew/bin/brew", fallback: "/usr/local/bin/brew")

        // Check Python
        pythonInstalled = await checkCommand("/usr/bin/python3", fallback: "/opt/homebrew/bin/python3")

        // Check pymobiledevice3
        pymobiledeviceInstalled = await checkPymobiledevice()

        // Check libimobiledevice
        libimobiledeviceInstalled = await checkCommand("/opt/homebrew/bin/idevice_id", fallback: "/usr/local/bin/idevice_id")

        logs.append("Homebrew: \(homebrewInstalled ? "✓" : "✗")")
        logs.append("Python 3: \(pythonInstalled ? "✓" : "✗")")
        logs.append("pymobiledevice3: \(pymobiledeviceInstalled ? "✓" : "✗")")
        logs.append("libimobiledevice: \(libimobiledeviceInstalled ? "✓" : "✗")")
    }

    private func checkCommand(_ path: String, fallback: String? = nil) async -> Bool {
        let fm = FileManager.default
        if fm.fileExists(atPath: path) {
            return true
        }
        if let fallback = fallback, fm.fileExists(atPath: fallback) {
            return true
        }
        return false
    }

    private func checkPymobiledevice() async -> Bool {
        do {
            let result = try await runCommand(
                "/usr/bin/python3",
                arguments: ["-c", "import pymobiledevice3; print('ok')"]
            )
            return result.exitCode == 0 && result.output.contains("ok")
        } catch {
            // Try with Homebrew Python
            do {
                let result = try await runCommand(
                    "/opt/homebrew/bin/python3",
                    arguments: ["-c", "import pymobiledevice3; print('ok')"]
                )
                if result.exitCode == 0 && result.output.contains("ok") {
                    pythonPath = "/opt/homebrew/bin/python3"
                    return true
                }
            } catch {}
        }
        return false
    }

    // MARK: - Install Dependencies

    func installAllDependencies() async {
        isSettingUp = true
        hasError = false
        errorMessage = ""
        progress = 0
        logs = ["Starting automatic setup..."]

        do {
            // Step 1: Install Homebrew if needed
            if !homebrewInstalled {
                progress = 0.1
                currentStep = "Installing Homebrew..."
                logs.append("\n📦 Installing Homebrew...")
                try await installHomebrew()
                homebrewInstalled = true
                logs.append("✓ Homebrew installed")
            }
            progress = 0.25

            // Step 2: Install Python if needed
            if !pythonInstalled {
                progress = 0.3
                currentStep = "Installing Python 3..."
                logs.append("\n🐍 Installing Python 3...")
                try await installPython()
                pythonInstalled = true
                logs.append("✓ Python 3 installed")
            }
            progress = 0.5

            // Step 3: Install libimobiledevice
            if !libimobiledeviceInstalled {
                progress = 0.55
                currentStep = "Installing libimobiledevice..."
                logs.append("\n📱 Installing libimobiledevice...")
                try await installLibimobiledevice()
                libimobiledeviceInstalled = true
                logs.append("✓ libimobiledevice installed")
            }
            progress = 0.7

            // Step 4: Install pymobiledevice3
            if !pymobiledeviceInstalled {
                progress = 0.75
                currentStep = "Installing pymobiledevice3..."
                logs.append("\n🔧 Installing pymobiledevice3...")
                try await installPymobiledevice3()
                pymobiledeviceInstalled = true
                logs.append("✓ pymobiledevice3 installed")
            }
            progress = 1.0

            currentStep = "Setup complete!"
            logs.append("\n✅ All dependencies installed successfully!")

        } catch {
            hasError = true
            errorMessage = error.localizedDescription
            logs.append("\n❌ Error: \(error.localizedDescription)")
        }

        isSettingUp = false
    }

    private func installHomebrew() async throws {
        // Homebrew requires an interactive terminal, so we use AppleScript
        let script = """
        tell application "Terminal"
            activate
            do script "/bin/bash -c \\"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\\""
        end tell
        """

        logs.append("Opening Terminal for Homebrew installation...")
        logs.append("Please follow the prompts in Terminal, then return here.")

        let appleScript = NSAppleScript(source: script)
        var error: NSDictionary?
        appleScript?.executeAndReturnError(&error)

        if let error = error {
            throw SetupError.installFailed("Homebrew: \(error)")
        }

        // Wait and check
        for _ in 0..<60 { // Wait up to 5 minutes
            try await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
            if await checkCommand("/opt/homebrew/bin/brew", fallback: "/usr/local/bin/brew") {
                return
            }
        }

        throw SetupError.installFailed("Homebrew installation timed out. Please install manually.")
    }

    private func installPython() async throws {
        let brewPath = FileManager.default.fileExists(atPath: "/opt/homebrew/bin/brew")
            ? "/opt/homebrew/bin/brew"
            : "/usr/local/bin/brew"

        let result = try await runCommand(brewPath, arguments: ["install", "python3"])

        if result.exitCode != 0 {
            throw SetupError.installFailed("Python: \(result.output)")
        }

        pythonPath = "/opt/homebrew/bin/python3"
    }

    private func installLibimobiledevice() async throws {
        let brewPath = FileManager.default.fileExists(atPath: "/opt/homebrew/bin/brew")
            ? "/opt/homebrew/bin/brew"
            : "/usr/local/bin/brew"

        let result = try await runCommand(brewPath, arguments: ["install", "libimobiledevice"])

        if result.exitCode != 0 {
            throw SetupError.installFailed("libimobiledevice: \(result.output)")
        }
    }

    private func installPymobiledevice3() async throws {
        // Use pip3 to install pymobiledevice3
        let pip3Path: String
        if FileManager.default.fileExists(atPath: "/opt/homebrew/bin/pip3") {
            pip3Path = "/opt/homebrew/bin/pip3"
        } else if FileManager.default.fileExists(atPath: "/usr/local/bin/pip3") {
            pip3Path = "/usr/local/bin/pip3"
        } else {
            pip3Path = "/usr/bin/pip3"
        }

        let result = try await runCommand(pip3Path, arguments: ["install", "-U", "pymobiledevice3"])

        if result.exitCode != 0 {
            // Try with python -m pip
            let pipResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pip", "install", "-U", "pymobiledevice3"]
            )
            if pipResult.exitCode != 0 {
                throw SetupError.installFailed("pymobiledevice3: \(pipResult.output)")
            }
        }
    }

    // MARK: - Trigger Developer Mode

    /// Attempts to make Developer Mode option appear in iOS Settings
    /// This works by mounting the developer disk image or triggering developer services
    func triggerDeveloperMode() async -> Bool {
        logs.append("\n🔧 Attempting to trigger Developer Mode...")

        do {
            // Method 1: Try mounting developer disk image
            logs.append("Mounting developer disk image...")
            let mountResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "mounter", "auto-mount"]
            )

            if mountResult.exitCode == 0 {
                logs.append("✓ Developer disk mounted - Developer Mode should now appear in Settings")
                return true
            }

            // Method 2: Try accessing developer services (this can trigger the prompt)
            logs.append("Triggering developer services...")
            let devResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "developer", "dvt", "ls", "/"]
            )

            // Even if it fails, it might trigger the Developer Mode prompt on the device
            if devResult.output.lowercased().contains("developer mode") {
                logs.append("⚠️ Developer Mode prompt triggered - check your iPhone!")
                logs.append("Go to Settings → Privacy & Security → Developer Mode")
                return true
            }

            // Method 3: Try enabling developer mode directly (iOS 17+)
            logs.append("Attempting direct developer mode activation...")
            let enableResult = try await runCommand(
                pythonPath,
                arguments: ["-m", "pymobiledevice3", "amfi", "enable-developer-mode"]
            )

            if enableResult.exitCode == 0 {
                logs.append("✓ Developer Mode activation triggered!")
                logs.append("Your iPhone may prompt you to restart.")
                return true
            }

            logs.append("⚠️ Could not automatically trigger Developer Mode")
            logs.append("Please manually enable it: Settings → Privacy & Security → Developer Mode")
            return false

        } catch {
            logs.append("Error triggering Developer Mode: \(error.localizedDescription)")
            return false
        }
    }

    // MARK: - Helper Methods

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

                // Add PATH for Homebrew
                var env = ProcessInfo.processInfo.environment
                env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
                process.environment = env

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
}

// MARK: - Errors

enum SetupError: LocalizedError {
    case installFailed(String)
    case timeout
    case permissionDenied

    var errorDescription: String? {
        switch self {
        case .installFailed(let details):
            return "Installation failed: \(details)"
        case .timeout:
            return "Installation timed out"
        case .permissionDenied:
            return "Permission denied - try running with administrator privileges"
        }
    }
}

// CommandResult is defined in LocationManager.swift

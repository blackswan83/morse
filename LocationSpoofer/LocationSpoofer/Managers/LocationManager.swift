//
//  LocationManager.swift
//  LocationSpoofer
//
//  Manages location spoofing via pymobiledevice3 CLI
//

import Foundation
import Combine

@MainActor
class LocationManager: ObservableObject {
    @Published var isSpoofing = false
    @Published var isSettingLocation = false
    @Published var isClearingLocation = false
    @Published var currentSpoofedLocation: Coordinate?
    @Published var lastError: String?

    // Route simulation state
    @Published var isSimulatingRoute = false
    @Published var isRoutePaused = false
    @Published var routeProgress: Double = 0
    @Published var currentRoutePointIndex = 0
    @Published var totalRoutePoints = 0
    @Published var estimatedTimeRemaining: TimeInterval = 0

    private var routeSimulationTask: Task<Void, Never>?
    private var simulationCancelled = false

    @AppStorage("pythonPath") private var pythonPath = "/usr/bin/python3"
    @AppStorage("updateInterval") private var updateInterval: Double = 2.0

    // MARK: - Set Location

    func setLocation(_ coordinate: Coordinate, tunnelManager: TunnelManager) async {
        guard tunnelManager.isRunning else {
            lastError = "Tunnel is not running. Please start the tunnel first."
            return
        }

        isSettingLocation = true
        lastError = nil

        do {
            let result = try await runPymobiledeviceCommand(
                arguments: [
                    "developer", "dvt", "simulate-location", "set",
                    "--tunnel", "",
                    String(coordinate.latitude),
                    String(coordinate.longitude)
                ]
            )

            if result.exitCode == 0 {
                isSpoofing = true
                currentSpoofedLocation = coordinate

                // Send notification
                sendNotification(
                    title: "Location Set",
                    body: "GPS spoofed to \(String(format: "%.4f", coordinate.latitude)), \(String(format: "%.4f", coordinate.longitude))"
                )
            } else {
                lastError = "Failed to set location: \(result.output)"
            }
        } catch {
            lastError = "Error: \(error.localizedDescription)"
        }

        isSettingLocation = false
    }

    // MARK: - Clear Location

    func clearLocation(tunnelManager: TunnelManager) async {
        guard tunnelManager.isRunning else {
            lastError = "Tunnel is not running."
            return
        }

        isClearingLocation = true
        lastError = nil

        // Stop any running route simulation
        stopRouteSimulation()

        do {
            let result = try await runPymobiledeviceCommand(
                arguments: [
                    "developer", "dvt", "simulate-location", "clear",
                    "--tunnel", ""
                ]
            )

            if result.exitCode == 0 {
                isSpoofing = false
                currentSpoofedLocation = nil

                sendNotification(
                    title: "Location Cleared",
                    body: "GPS returned to real location"
                )
            } else {
                lastError = "Failed to clear location: \(result.output)"
            }
        } catch {
            lastError = "Error: \(error.localizedDescription)"
        }

        isClearingLocation = false
    }

    // MARK: - Route Simulation

    func startRouteSimulation(route: Route, speedKmh: Double) async {
        // Interpolate route points based on speed
        let pointsPerKm = max(5, 60 / speedKmh * 10) // More points at lower speeds
        let interpolatedPoints = route.interpolate(pointsPerKm: pointsPerKm)

        guard interpolatedPoints.count >= 2 else {
            lastError = "Route must have at least 2 points"
            return
        }

        isSimulatingRoute = true
        isRoutePaused = false
        simulationCancelled = false
        totalRoutePoints = interpolatedPoints.count
        currentRoutePointIndex = 0
        routeProgress = 0

        // Calculate interval between points based on speed
        // Speed in km/h, interval in seconds
        let distanceBetweenPoints = route.totalDistance / Double(interpolatedPoints.count - 1)
        let speedMps = speedKmh * 1000 / 3600 // Convert to m/s
        let intervalBetweenPoints = distanceBetweenPoints / speedMps

        // Estimate total time
        let totalTime = Double(interpolatedPoints.count - 1) * intervalBetweenPoints
        estimatedTimeRemaining = totalTime

        routeSimulationTask = Task {
            var pointIndex = 0
            var loopCount = 0
            let maxLoops = route.isLoop ? Int.max : 1

            while !simulationCancelled && loopCount < maxLoops {
                for i in pointIndex..<interpolatedPoints.count {
                    if simulationCancelled {
                        break
                    }

                    // Wait if paused
                    while isRoutePaused && !simulationCancelled {
                        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 second
                    }

                    if simulationCancelled {
                        break
                    }

                    let point = interpolatedPoints[i]
                    currentRoutePointIndex = i
                    routeProgress = Double(i) / Double(interpolatedPoints.count - 1)
                    estimatedTimeRemaining = Double(interpolatedPoints.count - i - 1) * intervalBetweenPoints

                    // Set location
                    do {
                        let result = try await runPymobiledeviceCommand(
                            arguments: [
                                "developer", "dvt", "simulate-location", "set",
                                "--tunnel", "",
                                String(point.latitude),
                                String(point.longitude)
                            ]
                        )

                        if result.exitCode == 0 {
                            currentSpoofedLocation = point
                            isSpoofing = true
                        } else {
                            lastError = "Route simulation error: \(result.output)"
                            break
                        }
                    } catch {
                        lastError = "Route simulation error: \(error.localizedDescription)"
                        break
                    }

                    // Wait for next point
                    if i < interpolatedPoints.count - 1 {
                        try? await Task.sleep(nanoseconds: UInt64(updateInterval * 1_000_000_000))
                    }
                }

                if route.isLoop && !simulationCancelled {
                    loopCount += 1
                    pointIndex = 0
                } else {
                    break
                }
            }

            // Simulation complete
            await MainActor.run {
                isSimulatingRoute = false
                routeProgress = 1.0
                estimatedTimeRemaining = 0

                if !simulationCancelled {
                    sendNotification(
                        title: "Route Complete",
                        body: "Route simulation finished"
                    )
                }
            }
        }
    }

    func pauseRouteSimulation() {
        isRoutePaused.toggle()
    }

    func stopRouteSimulation() {
        simulationCancelled = true
        routeSimulationTask?.cancel()
        routeSimulationTask = nil
        isSimulatingRoute = false
        isRoutePaused = false
        routeProgress = 0
        currentRoutePointIndex = 0
        estimatedTimeRemaining = 0
    }

    // MARK: - Helper Methods

    private func runPymobiledeviceCommand(arguments: [String]) async throws -> CommandResult {
        return try await withCheckedThrowingContinuation { continuation in
            Task.detached {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: self.pythonPath)
                process.arguments = ["-m", "pymobiledevice3"] + arguments

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

    private func sendNotification(title: String, body: String) {
        let notifyOnChange = UserDefaults.standard.bool(forKey: "notifyOnLocationChange")
        guard notifyOnChange else { return }

        let notification = NSUserNotification()
        notification.title = title
        notification.informativeText = body
        notification.soundName = NSUserNotificationDefaultSoundName
        NSUserNotificationCenter.default.deliver(notification)
    }
}

// MARK: - Command Result
struct CommandResult {
    let exitCode: Int
    let output: String

    var isSuccess: Bool { exitCode == 0 }
}

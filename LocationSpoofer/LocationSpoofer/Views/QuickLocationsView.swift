//
//  QuickLocationsView.swift
//  LocationSpoofer
//
//  Grid of preset location buttons for quick access
//

import SwiftUI

struct QuickLocationsView: View {
    @Binding var selectedCoordinate: Coordinate?
    @EnvironmentObject var appState: AppState
    @State private var customLocations: [PresetLocation] = []
    @State private var showingAddLocation = false

    private let columns = [
        GridItem(.flexible()),
        GridItem(.flexible())
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Quick Locations", systemImage: "star.fill")
                    .font(.headline)

                Spacer()

                Button {
                    showingAddLocation = true
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(.borderless)
                .help("Save current location")
            }

            LazyVGrid(columns: columns, spacing: 8) {
                ForEach(PresetLocation.all) { location in
                    QuickLocationButton(
                        location: location,
                        isSelected: isLocationSelected(location)
                    ) {
                        selectLocation(location)
                    }
                }
            }

            if !customLocations.isEmpty {
                Divider()

                Text("Saved Locations")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                LazyVGrid(columns: columns, spacing: 8) {
                    ForEach(customLocations) { location in
                        QuickLocationButton(
                            location: location,
                            isSelected: isLocationSelected(location),
                            onDelete: {
                                deleteLocation(location)
                            }
                        ) {
                            selectLocation(location)
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showingAddLocation) {
            AddLocationSheet(
                coordinate: selectedCoordinate,
                onSave: { location in
                    customLocations.append(location)
                    saveCustomLocations()
                }
            )
        }
        .onAppear {
            loadCustomLocations()
        }
    }

    private func isLocationSelected(_ location: PresetLocation) -> Bool {
        guard let selected = selectedCoordinate else { return false }
        return abs(selected.latitude - location.coordinate.latitude) < 0.0001 &&
               abs(selected.longitude - location.coordinate.longitude) < 0.0001
    }

    private func selectLocation(_ location: PresetLocation) {
        selectedCoordinate = location.coordinate
        appState.saveLastLocation(location.coordinate)
    }

    private func deleteLocation(_ location: PresetLocation) {
        customLocations.removeAll { $0.id == location.id }
        saveCustomLocations()
    }

    private func loadCustomLocations() {
        if let data = UserDefaults.standard.data(forKey: "customLocations"),
           let locations = try? JSONDecoder().decode([PresetLocation].self, from: data) {
            customLocations = locations
        }
    }

    private func saveCustomLocations() {
        if let data = try? JSONEncoder().encode(customLocations) {
            UserDefaults.standard.set(data, forKey: "customLocations")
        }
    }
}

struct QuickLocationButton: View {
    let location: PresetLocation
    let isSelected: Bool
    var onDelete: (() -> Void)?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Text(location.emoji)
                    .font(.title3)

                Text(location.name)
                    .font(.caption)
                    .lineLimit(1)

                Spacer()

                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(isSelected ? Color.accentColor.opacity(0.2) : Color(nsColor: .controlBackgroundColor))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.accentColor : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .contextMenu {
            if let onDelete = onDelete {
                Button(role: .destructive) {
                    onDelete()
                } label: {
                    Label("Delete", systemImage: "trash")
                }
            }

            Button {
                let pasteboard = NSPasteboard.general
                pasteboard.clearContents()
                pasteboard.setString("\(location.coordinate.latitude), \(location.coordinate.longitude)", forType: .string)
            } label: {
                Label("Copy Coordinates", systemImage: "doc.on.doc")
            }
        }
    }
}

struct AddLocationSheet: View {
    let coordinate: Coordinate?
    let onSave: (PresetLocation) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var emoji = "📍"

    private let emojis = ["📍", "🏠", "🏢", "🏫", "🏥", "🏪", "⭐️", "❤️", "🎯", "🔵"]

    var body: some View {
        VStack(spacing: 20) {
            Text("Save Location")
                .font(.headline)

            if let coord = coordinate {
                Text("Coordinates: \(String(format: "%.4f", coord.latitude)), \(String(format: "%.4f", coord.longitude))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            TextField("Location Name", text: $name)
                .textFieldStyle(.roundedBorder)

            VStack(alignment: .leading) {
                Text("Icon")
                    .font(.caption)
                    .foregroundColor(.secondary)

                HStack(spacing: 8) {
                    ForEach(emojis, id: \.self) { e in
                        Button {
                            emoji = e
                        } label: {
                            Text(e)
                                .font(.title2)
                                .padding(6)
                                .background(emoji == e ? Color.accentColor.opacity(0.3) : Color.clear)
                                .cornerRadius(6)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.bordered)

                Button("Save") {
                    guard let coord = coordinate, !name.isEmpty else { return }
                    let location = PresetLocation(
                        name: name,
                        latitude: coord.latitude,
                        longitude: coord.longitude,
                        emoji: emoji
                    )
                    onSave(location)
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.isEmpty || coordinate == nil)
            }
        }
        .padding()
        .frame(width: 300)
    }
}

#Preview {
    QuickLocationsView(selectedCoordinate: .constant(nil))
        .environmentObject(AppState())
        .frame(width: 300)
        .padding()
}

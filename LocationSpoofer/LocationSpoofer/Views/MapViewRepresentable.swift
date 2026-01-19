//
//  MapViewRepresentable.swift
//  LocationSpoofer
//
//  NSViewRepresentable wrapper for MKMapView with click-to-place-pin functionality
//

import SwiftUI
import MapKit

struct MapViewRepresentable: NSViewRepresentable {
    @Binding var selectedCoordinate: Coordinate?
    @Binding var routeWaypoints: [Coordinate]
    @Binding var isDrawingRoute: Bool
    let isSpoofingActive: Bool

    func makeNSView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator

        // Configure map
        mapView.mapType = .standard
        mapView.showsCompass = true
        mapView.showsZoomControls = true
        mapView.showsScale = true

        // Add click gesture
        let clickGesture = NSClickGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleClick(_:))
        )
        mapView.addGestureRecognizer(clickGesture)

        // Set initial region (Riyadh)
        let initialRegion = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 24.7136, longitude: 46.6753),
            span: MKCoordinateSpan(latitudeDelta: 0.1, longitudeDelta: 0.1)
        )
        mapView.setRegion(initialRegion, animated: false)

        return mapView
    }

    func updateNSView(_ mapView: MKMapView, context: Context) {
        // Update coordinator references
        context.coordinator.parent = self

        // Update annotations
        updateAnnotations(mapView)

        // Update route overlay
        updateRouteOverlay(mapView)

        // Center on selected coordinate if changed
        if let coord = selectedCoordinate,
           !context.coordinator.isUserInteracting {
            let region = MKCoordinateRegion(
                center: coord.clLocation,
                span: mapView.region.span
            )
            mapView.setRegion(region, animated: true)
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    private func updateAnnotations(_ mapView: MKMapView) {
        // Remove existing annotations
        let existingAnnotations = mapView.annotations.filter { !($0 is MKUserLocation) }
        mapView.removeAnnotations(existingAnnotations)

        // Add selected location pin
        if let coord = selectedCoordinate {
            let annotation = LocationAnnotation(coordinate: coord, isActive: isSpoofingActive)
            mapView.addAnnotation(annotation)
        }

        // Add route waypoints
        for (index, waypoint) in routeWaypoints.enumerated() {
            let annotation = WaypointAnnotation(
                coordinate: waypoint,
                index: index
            )
            mapView.addAnnotation(annotation)
        }
    }

    private func updateRouteOverlay(_ mapView: MKMapView) {
        // Remove existing overlays
        mapView.removeOverlays(mapView.overlays)

        // Add route polyline if we have waypoints
        guard routeWaypoints.count >= 2 else { return }

        let coordinates = routeWaypoints.map { $0.clLocation }
        let polyline = MKPolyline(coordinates: coordinates, count: coordinates.count)
        mapView.addOverlay(polyline)
    }

    // MARK: - Coordinator
    class Coordinator: NSObject, MKMapViewDelegate {
        var parent: MapViewRepresentable
        var isUserInteracting = false

        init(_ parent: MapViewRepresentable) {
            self.parent = parent
        }

        @objc func handleClick(_ gesture: NSClickGestureRecognizer) {
            guard let mapView = gesture.view as? MKMapView else { return }

            let point = gesture.location(in: mapView)
            let coordinate = mapView.convert(point, toCoordinateFrom: mapView)
            let coord = Coordinate(from: coordinate)

            if parent.isDrawingRoute {
                // Add waypoint to route
                parent.routeWaypoints.append(coord)
            } else {
                // Set selected location
                parent.selectedCoordinate = coord
            }
        }

        // MARK: - MKMapViewDelegate

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation {
                return nil
            }

            if let locationAnnotation = annotation as? LocationAnnotation {
                let identifier = "LocationPin"
                var view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? MKMarkerAnnotationView

                if view == nil {
                    view = MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)
                } else {
                    view?.annotation = annotation
                }

                view?.markerTintColor = locationAnnotation.isActive ? .systemGreen : .systemBlue
                view?.glyphImage = NSImage(systemSymbolName: "location.fill", accessibilityDescription: nil)
                view?.animatesWhenAdded = true
                view?.isDraggable = true

                return view
            }

            if let waypointAnnotation = annotation as? WaypointAnnotation {
                let identifier = "WaypointPin"
                var view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? MKMarkerAnnotationView

                if view == nil {
                    view = MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)
                } else {
                    view?.annotation = annotation
                }

                view?.markerTintColor = .systemOrange
                view?.glyphText = "\(waypointAnnotation.index + 1)"
                view?.animatesWhenAdded = true
                view?.isDraggable = true

                return view
            }

            return nil
        }

        func mapView(_ mapView: MKMapView, annotationView view: MKAnnotationView, didChange newState: MKAnnotationView.DragState, fromOldState oldState: MKAnnotationView.DragState) {
            guard newState == .ending,
                  let annotation = view.annotation else { return }

            let newCoord = Coordinate(from: annotation.coordinate)

            if annotation is LocationAnnotation {
                parent.selectedCoordinate = newCoord
            } else if let waypointAnnotation = annotation as? WaypointAnnotation {
                if waypointAnnotation.index < parent.routeWaypoints.count {
                    parent.routeWaypoints[waypointAnnotation.index] = newCoord
                }
            }
        }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? MKPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                renderer.strokeColor = .systemOrange
                renderer.lineWidth = 3
                renderer.lineDashPattern = [10, 5]
                return renderer
            }
            return MKOverlayRenderer(overlay: overlay)
        }

        func mapViewDidChangeVisibleRegion(_ mapView: MKMapView) {
            isUserInteracting = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                self.isUserInteracting = false
            }
        }
    }
}

// MARK: - Custom Annotations
class LocationAnnotation: NSObject, MKAnnotation {
    let coordinate: CLLocationCoordinate2D
    let isActive: Bool

    var title: String? { "Spoofed Location" }
    var subtitle: String? {
        String(format: "%.4f, %.4f", coordinate.latitude, coordinate.longitude)
    }

    init(coordinate: Coordinate, isActive: Bool) {
        self.coordinate = coordinate.clLocation
        self.isActive = isActive
        super.init()
    }
}

class WaypointAnnotation: NSObject, MKAnnotation {
    dynamic var coordinate: CLLocationCoordinate2D
    let index: Int

    var title: String? { "Waypoint \(index + 1)" }

    init(coordinate: Coordinate, index: Int) {
        self.coordinate = coordinate.clLocation
        self.index = index
        super.init()
    }
}

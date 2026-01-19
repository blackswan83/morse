#!/usr/bin/env python3
"""
move_location.py - Dynamic GPS Location Simulator

Simulates realistic movement along predefined or custom routes by updating
the iPhone's GPS location at regular intervals via pymobiledevice3.

Usage:
    python3 move_location.py --route riyadh --speed 5 --loop
    python3 move_location.py --waypoints '24.71,46.67;24.72,46.68' --speed 40
    python3 move_location.py --gpx route.gpx --speed 15

Requirements:
    - Python 3.8+
    - pymobiledevice3
    - iPhone connected via USB with Developer Mode enabled
    - Tunnel service running (sudo python3 -m pymobiledevice3 remote tunneld)
"""

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


@dataclass
class Coordinate:
    """Represents a GPS coordinate with latitude and longitude."""
    latitude: float
    longitude: float

    def distance_to(self, other: 'Coordinate') -> float:
        """Calculate distance to another coordinate in meters using Haversine formula."""
        R = 6371000  # Earth's radius in meters
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def bearing_to(self, other: 'Coordinate') -> float:
        """Calculate bearing to another coordinate in degrees."""
        lat1 = math.radians(self.latitude)
        lat2 = math.radians(other.latitude)
        dlon = math.radians(other.longitude - self.longitude)

        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    def __str__(self) -> str:
        return f"({self.latitude:.6f}, {self.longitude:.6f})"


# Predefined routes
ROUTES = {
    'riyadh': [
        Coordinate(24.7136, 46.6753),  # Kingdom Centre
        Coordinate(24.7255, 46.6823),  # Al Faisaliah Tower
        Coordinate(24.7350, 46.6900),  # King Fahd Road
        Coordinate(24.7200, 46.7000),  # Return path
    ],
    'london': [
        Coordinate(51.5014, -0.1419),  # Buckingham Palace
        Coordinate(51.5007, -0.1246),  # Big Ben
        Coordinate(51.5033, -0.1195),  # London Eye
        Coordinate(51.5080, -0.0759),  # Tower Bridge
    ],
    'newyork': [
        Coordinate(40.7484, -73.9857),  # Empire State Building
        Coordinate(40.7580, -73.9855),  # Times Square
        Coordinate(40.7614, -73.9776),  # Rockefeller Center
        Coordinate(40.7829, -73.9654),  # Central Park
    ],
    'paris': [
        Coordinate(48.8584, 2.2945),   # Eiffel Tower
        Coordinate(48.8606, 2.3376),   # Louvre
        Coordinate(48.8530, 2.3499),   # Notre-Dame
        Coordinate(48.8738, 2.2950),   # Arc de Triomphe
    ],
    'dubai': [
        Coordinate(25.1972, 55.2744),  # Burj Khalifa
        Coordinate(25.0657, 55.1713),  # Palm Jumeirah
        Coordinate(25.0772, 55.1394),  # Burj Al Arab
        Coordinate(25.1171, 55.2008),  # Dubai Marina
    ],
    'tokyo': [
        Coordinate(35.6762, 139.6503), # Shibuya
        Coordinate(35.6586, 139.7454), # Tokyo Tower
        Coordinate(35.6895, 139.6917), # Shinjuku
        Coordinate(35.7101, 139.8107), # Asakusa
    ],
}


def interpolate_route(waypoints: List[Coordinate], points_per_km: float = 10) -> List[Coordinate]:
    """
    Interpolate points between waypoints for smooth movement.

    Args:
        waypoints: List of coordinate waypoints
        points_per_km: Number of intermediate points per kilometer

    Returns:
        List of interpolated coordinates
    """
    if len(waypoints) < 2:
        return waypoints

    interpolated = []

    for i in range(len(waypoints) - 1):
        start = waypoints[i]
        end = waypoints[i + 1]
        distance = start.distance_to(end)

        # Calculate number of points based on distance
        num_points = max(2, int(distance / 1000 * points_per_km))

        for j in range(num_points):
            fraction = j / num_points
            lat = start.latitude + (end.latitude - start.latitude) * fraction
            lon = start.longitude + (end.longitude - start.longitude) * fraction
            interpolated.append(Coordinate(lat, lon))

    # Add the final point
    interpolated.append(waypoints[-1])

    return interpolated


def parse_waypoints(waypoints_str: str) -> List[Coordinate]:
    """
    Parse waypoints from a string format.

    Format: "lat1,lon1;lat2,lon2;lat3,lon3"

    Args:
        waypoints_str: Semicolon-separated coordinate pairs

    Returns:
        List of Coordinate objects
    """
    coordinates = []

    for point in waypoints_str.split(';'):
        parts = point.strip().split(',')
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                coordinates.append(Coordinate(lat, lon))
            except ValueError:
                print(f"{Colors.RED}Invalid coordinate: {point}{Colors.RESET}")

    return coordinates


def parse_gpx(gpx_path: str) -> List[Coordinate]:
    """
    Parse waypoints from a GPX file.

    Args:
        gpx_path: Path to the GPX file

    Returns:
        List of Coordinate objects
    """
    coordinates = []

    try:
        tree = ET.parse(gpx_path)
        root = tree.getroot()

        # Handle GPX namespace
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}

        # Try to find track points first
        for trkpt in root.findall('.//gpx:trkpt', ns) or root.findall('.//{http://www.topografix.com/GPX/1/0}trkpt'):
            lat = float(trkpt.get('lat'))
            lon = float(trkpt.get('lon'))
            coordinates.append(Coordinate(lat, lon))

        # If no track points, try waypoints
        if not coordinates:
            for wpt in root.findall('.//gpx:wpt', ns) or root.findall('.//{http://www.topografix.com/GPX/1/0}wpt'):
                lat = float(wpt.get('lat'))
                lon = float(wpt.get('lon'))
                coordinates.append(Coordinate(lat, lon))

        # If still no coordinates, try without namespace
        if not coordinates:
            for elem in root.iter():
                if 'trkpt' in elem.tag or 'wpt' in elem.tag:
                    lat = elem.get('lat')
                    lon = elem.get('lon')
                    if lat and lon:
                        coordinates.append(Coordinate(float(lat), float(lon)))

    except Exception as e:
        print(f"{Colors.RED}Error parsing GPX file: {e}{Colors.RESET}")

    return coordinates


def set_location(coord: Coordinate) -> bool:
    """
    Set the iPhone's GPS location using pymobiledevice3.

    Args:
        coord: The coordinate to set

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            [
                sys.executable, '-m', 'pymobiledevice3',
                'developer', 'dvt', 'simulate-location', 'set',
                '--tunnel', '',
                str(coord.latitude),
                str(coord.longitude)
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}Timeout setting location{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Error setting location: {e}{Colors.RESET}")
        return False


def clear_location() -> bool:
    """Clear the simulated location and return to real GPS."""
    try:
        result = subprocess.run(
            [
                sys.executable, '-m', 'pymobiledevice3',
                'developer', 'dvt', 'simulate-location', 'clear',
                '--tunnel', ''
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.returncode == 0

    except Exception as e:
        print(f"{Colors.RED}Error clearing location: {e}{Colors.RESET}")
        return False


def calculate_total_distance(waypoints: List[Coordinate]) -> float:
    """Calculate total distance of a route in meters."""
    total = 0
    for i in range(len(waypoints) - 1):
        total += waypoints[i].distance_to(waypoints[i + 1])
    return total


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable time string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def simulate_movement(
    waypoints: List[Coordinate],
    speed_kmh: float,
    update_interval: float = 2.0,
    loop: bool = False,
    verbose: bool = True
) -> None:
    """
    Simulate movement along a route.

    Args:
        waypoints: List of coordinates to move through
        speed_kmh: Speed in kilometers per hour
        update_interval: Time between location updates in seconds
        loop: Whether to loop the route continuously
        verbose: Whether to print progress information
    """
    if len(waypoints) < 2:
        print(f"{Colors.RED}Need at least 2 waypoints{Colors.RESET}")
        return

    # Calculate interpolated points based on speed
    points_per_km = max(5, 60 / speed_kmh * 10)
    points = interpolate_route(waypoints, points_per_km)

    total_distance = calculate_total_distance(points)
    speed_mps = speed_kmh * 1000 / 3600

    # Calculate total time
    total_time = total_distance / speed_mps

    if verbose:
        print(f"\n{Colors.BOLD}Route Simulation{Colors.RESET}")
        print(f"  Waypoints: {len(waypoints)}")
        print(f"  Interpolated points: {len(points)}")
        print(f"  Total distance: {total_distance/1000:.2f} km")
        print(f"  Speed: {speed_kmh} km/h")
        print(f"  Estimated time: {format_time(total_time)}")
        print(f"  Loop: {'Yes' if loop else 'No'}")
        print(f"\n{Colors.CYAN}Press Ctrl+C to stop{Colors.RESET}\n")

    # Set up signal handler for clean exit
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print(f"\n{Colors.YELLOW}Stopping simulation...{Colors.RESET}")

    signal.signal(signal.SIGINT, signal_handler)

    loop_count = 0
    start_time = time.time()

    while running:
        loop_count += 1

        for i, point in enumerate(points):
            if not running:
                break

            # Set the location
            success = set_location(point)

            if verbose:
                progress = (i + 1) / len(points) * 100
                elapsed = time.time() - start_time
                remaining = (len(points) - i - 1) * update_interval

                status = f"{Colors.GREEN}OK{Colors.RESET}" if success else f"{Colors.RED}FAIL{Colors.RESET}"
                loop_info = f" (Loop {loop_count})" if loop else ""

                print(
                    f"\r{Colors.BOLD}[{progress:5.1f}%]{Colors.RESET} "
                    f"Point {i+1}/{len(points)}{loop_info} | "
                    f"{point} | "
                    f"ETA: {format_time(remaining)} | "
                    f"{status}    ",
                    end='',
                    flush=True
                )

            if not success and verbose:
                print(f"\n{Colors.YELLOW}Warning: Failed to set location{Colors.RESET}")

            # Wait before next update
            time.sleep(update_interval)

        if not loop:
            break

        if verbose and running:
            print(f"\n{Colors.CYAN}Route completed, starting loop {loop_count + 1}...{Colors.RESET}")

    # Clean up
    print(f"\n\n{Colors.YELLOW}Clearing simulated location...{Colors.RESET}")
    if clear_location():
        print(f"{Colors.GREEN}Location cleared successfully{Colors.RESET}")
    else:
        print(f"{Colors.RED}Failed to clear location{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description='Simulate GPS movement on iPhone',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --route riyadh --speed 5
  %(prog)s --route london --speed 40 --loop
  %(prog)s --waypoints '24.71,46.67;24.72,46.68;24.73,46.65' --speed 10
  %(prog)s --gpx my_route.gpx --speed 15

Available routes: riyadh, london, newyork, paris, dubai, tokyo
        """
    )

    # Route source (mutually exclusive)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        '--route', '-r',
        choices=list(ROUTES.keys()),
        help='Use a predefined route'
    )
    source.add_argument(
        '--waypoints', '-w',
        help='Custom waypoints in format "lat1,lon1;lat2,lon2;..."'
    )
    source.add_argument(
        '--gpx', '-g',
        help='Path to a GPX file'
    )

    # Movement options
    parser.add_argument(
        '--speed', '-s',
        type=float,
        default=5.0,
        help='Speed in km/h (default: 5 for walking)'
    )
    parser.add_argument(
        '--interval', '-i',
        type=float,
        default=2.0,
        help='Update interval in seconds (default: 2.0)'
    )
    parser.add_argument(
        '--loop', '-l',
        action='store_true',
        help='Loop the route continuously'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Get waypoints from the specified source
    if args.route:
        waypoints = ROUTES[args.route]
        print(f"{Colors.BLUE}Using predefined route: {args.route}{Colors.RESET}")
    elif args.waypoints:
        waypoints = parse_waypoints(args.waypoints)
        print(f"{Colors.BLUE}Using custom waypoints{Colors.RESET}")
    elif args.gpx:
        if not Path(args.gpx).exists():
            print(f"{Colors.RED}GPX file not found: {args.gpx}{Colors.RESET}")
            sys.exit(1)
        waypoints = parse_gpx(args.gpx)
        print(f"{Colors.BLUE}Loaded {len(waypoints)} points from GPX file{Colors.RESET}")

    if len(waypoints) < 2:
        print(f"{Colors.RED}Error: Need at least 2 waypoints{Colors.RESET}")
        sys.exit(1)

    # Start simulation
    simulate_movement(
        waypoints=waypoints,
        speed_kmh=args.speed,
        update_interval=args.interval,
        loop=args.loop,
        verbose=not args.quiet
    )


if __name__ == '__main__':
    main()

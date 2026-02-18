#!/bin/bash
#
# Quick location spoofing script
# Usage: ./quick_spoof.sh <city|coordinates>
#
# Examples:
#   ./quick_spoof.sh riyadh
#   ./quick_spoof.sh london
#   ./quick_spoof.sh "24.7136 46.6753"
#   ./quick_spoof.sh clear
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Preset locations
declare -A LOCATIONS
LOCATIONS["riyadh"]="24.7136 46.6753"
LOCATIONS["london"]="51.5074 -0.1278"
LOCATIONS["newyork"]="40.7128 -74.0060"
LOCATIONS["paris"]="48.8566 2.3522"
LOCATIONS["dubai"]="25.2048 55.2708"
LOCATIONS["tokyo"]="35.6762 139.6503"
LOCATIONS["sydney"]="-33.8688 151.2093"
LOCATIONS["singapore"]="1.3521 103.8198"
LOCATIONS["hongkong"]="22.3193 114.1694"
LOCATIONS["mumbai"]="19.0760 72.8777"

show_usage() {
    echo -e "${BLUE}Usage: $0 <city|coordinates|clear>${NC}"
    echo ""
    echo "Available cities:"
    for city in "${!LOCATIONS[@]}"; do
        echo -e "  ${GREEN}$city${NC} → ${LOCATIONS[$city]}"
    done
    echo ""
    echo "Or use custom coordinates:"
    echo -e "  $0 \"24.7136 46.6753\""
    echo ""
    echo "To clear location:"
    echo -e "  $0 clear"
}

if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

INPUT="$1"

# Handle clear command
if [ "$INPUT" == "clear" ]; then
    echo -e "${YELLOW}Clearing spoofed location...${NC}"
    python3 -m pymobiledevice3 developer dvt simulate-location clear --tunnel ""
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Location cleared successfully!${NC}"
    else
        echo -e "${RED}Failed to clear location. Is the tunnel running?${NC}"
        exit 1
    fi
    exit 0
fi

# Get coordinates
if [ -n "${LOCATIONS[$INPUT]}" ]; then
    COORDS="${LOCATIONS[$INPUT]}"
    echo -e "${BLUE}Setting location to $INPUT${NC}"
else
    COORDS="$INPUT"
    echo -e "${BLUE}Setting custom coordinates${NC}"
fi

# Parse coordinates
LAT=$(echo "$COORDS" | awk '{print $1}')
LON=$(echo "$COORDS" | awk '{print $2}')

if [ -z "$LAT" ] || [ -z "$LON" ]; then
    echo -e "${RED}Error: Invalid coordinates format${NC}"
    show_usage
    exit 1
fi

echo -e "${YELLOW}Coordinates: $LAT, $LON${NC}"

# Set location
python3 -m pymobiledevice3 developer dvt simulate-location set --tunnel "" "$LAT" "$LON"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Location set successfully!${NC}"
else
    echo -e "${RED}Failed to set location. Is the tunnel running?${NC}"
    echo -e "${YELLOW}Start tunnel with: sudo python3 -m pymobiledevice3 remote tunneld${NC}"
    exit 1
fi

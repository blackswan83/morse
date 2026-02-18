#!/bin/bash
#
# Start the pymobiledevice3 tunnel service
# This script requires sudo/admin privileges
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Starting pymobiledevice3 tunnel service...${NC}"
echo -e "${YELLOW}This requires administrator privileges.${NC}"
echo ""

# Check if tunnel is already running
if pgrep -f "pymobiledevice3 remote tunneld" > /dev/null; then
    echo -e "${GREEN}Tunnel is already running.${NC}"
    exit 0
fi

# Start the tunnel
sudo python3 -m pymobiledevice3 remote tunneld

echo -e "${GREEN}Tunnel started successfully.${NC}"

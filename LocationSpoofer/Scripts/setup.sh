#!/bin/bash
#
# Location Spoofer Setup Script
# Installs all required dependencies for the iPhone Location Spoofer
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     iPhone Location Spoofer Setup          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}Error: This script is designed for macOS only.${NC}"
    exit 1
fi

# Check for Homebrew
echo -e "${YELLOW}Checking for Homebrew...${NC}"
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Homebrew not found. Installing...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}Homebrew is already installed.${NC}"
fi

# Install Python 3
echo ""
echo -e "${YELLOW}Checking for Python 3...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 not found. Installing via Homebrew...${NC}"
    brew install python3
else
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}Python 3 is already installed: ${PYTHON_VERSION}${NC}"
fi

# Install libimobiledevice
echo ""
echo -e "${YELLOW}Checking for libimobiledevice...${NC}"
if ! brew list libimobiledevice &> /dev/null; then
    echo -e "${YELLOW}Installing libimobiledevice...${NC}"
    brew install libimobiledevice
else
    echo -e "${GREEN}libimobiledevice is already installed.${NC}"
fi

# Install pymobiledevice3
echo ""
echo -e "${YELLOW}Checking for pymobiledevice3...${NC}"
if ! python3 -c "import pymobiledevice3" &> /dev/null; then
    echo -e "${YELLOW}Installing pymobiledevice3...${NC}"
    pip3 install pymobiledevice3
else
    PMD3_VERSION=$(python3 -m pymobiledevice3 --version 2>/dev/null || echo "installed")
    echo -e "${GREEN}pymobiledevice3 is already installed: ${PMD3_VERSION}${NC}"
fi

# Verify installation
echo ""
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo -e "${BLUE}Verifying installation...${NC}"
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo ""

# Check Python
echo -n "Python 3: "
if python3 --version &> /dev/null; then
    echo -e "${GREEN}$(python3 --version)${NC}"
else
    echo -e "${RED}Not found${NC}"
fi

# Check pip
echo -n "pip3: "
if pip3 --version &> /dev/null; then
    echo -e "${GREEN}$(pip3 --version | head -n1)${NC}"
else
    echo -e "${RED}Not found${NC}"
fi

# Check pymobiledevice3
echo -n "pymobiledevice3: "
if python3 -c "import pymobiledevice3" &> /dev/null; then
    echo -e "${GREEN}Installed${NC}"
else
    echo -e "${RED}Not found${NC}"
fi

# Check libimobiledevice
echo -n "libimobiledevice: "
if brew list libimobiledevice &> /dev/null; then
    echo -e "${GREEN}Installed${NC}"
else
    echo -e "${RED}Not found${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Connect your iPhone via USB"
echo -e "  2. Enable Developer Mode on iPhone:"
echo -e "     ${YELLOW}Settings → Privacy & Security → Developer Mode → ON${NC}"
echo -e "  3. Trust your Mac on the iPhone when prompted"
echo -e "  4. Start the tunnel service:"
echo -e "     ${YELLOW}sudo python3 -m pymobiledevice3 remote tunneld${NC}"
echo -e "  5. Open the Location Spoofer app or use CLI commands"
echo ""
echo -e "Quick CLI usage:"
echo -e "  ${BLUE}# Set location to Riyadh${NC}"
echo -e "  python3 -m pymobiledevice3 developer dvt simulate-location set --tunnel \"\" 24.7136 46.6753"
echo ""
echo -e "  ${BLUE}# Clear spoofed location${NC}"
echo -e "  python3 -m pymobiledevice3 developer dvt simulate-location clear --tunnel \"\""
echo ""
echo -e "  ${BLUE}# Simulate movement${NC}"
echo -e "  python3 Scripts/move_location.py --route riyadh --speed 5 --loop"
echo ""

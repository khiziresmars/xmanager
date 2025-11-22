#!/bin/bash
#
# XManager Auto-Update Script
# Updates XManager to the latest version from GitHub
#
# Usage:
#   wget -qO- https://raw.githubusercontent.com/khiziresmars/xmanager/main/update.sh | sudo bash
#   # or
#   curl -sSL https://raw.githubusercontent.com/khiziresmars/xmanager/main/update.sh | sudo bash
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REPO="khiziresmars/xmanager"
INSTALL_DIR="/opt/xui-manager"
BACKUP_DIR="/opt/xui-manager/backups"
SERVICE_NAME="xui-manager"
VENV_DIR="$INSTALL_DIR/venv"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     XManager Auto-Update Script        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (sudo)${NC}"
    exit 1
fi

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Error: XManager not installed in $INSTALL_DIR${NC}"
    echo -e "${YELLOW}Run install.sh first${NC}"
    exit 1
fi

# Get current version
CURRENT_VERSION="unknown"
if [ -f "$INSTALL_DIR/app/version.py" ]; then
    CURRENT_VERSION=$(grep -oP 'CURRENT_VERSION\s*=\s*"\K[^"]+' "$INSTALL_DIR/app/version.py" 2>/dev/null || echo "unknown")
fi
echo -e "${YELLOW}Current version: ${NC}$CURRENT_VERSION"

# Get latest version from GitHub
echo -e "${YELLOW}Checking latest version...${NC}"
LATEST_INFO=$(curl -s "https://api.github.com/repos/$REPO/releases/latest")
LATEST_VERSION=$(echo "$LATEST_INFO" | grep -oP '"tag_name":\s*"v?\K[^"]+' | head -1)
DOWNLOAD_URL=$(echo "$LATEST_INFO" | grep -oP '"tarball_url":\s*"\K[^"]+' | head -1)

if [ -z "$LATEST_VERSION" ]; then
    # Fallback to main branch if no releases
    echo -e "${YELLOW}No releases found, using main branch...${NC}"
    DOWNLOAD_URL="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
    LATEST_VERSION="main"
fi

echo -e "${GREEN}Target version: ${NC}$LATEST_VERSION"

# Check if update is needed
if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
    echo -e "${GREEN}✓ Already on latest version ($LATEST_VERSION)${NC}"
    read -p "Force update anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Create backup
echo -e "${YELLOW}Creating backup...${NC}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"

if [ -d "$INSTALL_DIR/app" ]; then
    tar -czf "$BACKUP_FILE" \
        -C "$INSTALL_DIR" \
        --exclude=venv \
        --exclude=.git \
        --exclude=__pycache__ \
        --exclude='*.pyc' \
        --exclude='*.log' \
        --exclude=backups \
        . 2>/dev/null || true
    echo -e "${GREEN}✓ Backup created: ${NC}$BACKUP_FILE"
fi

# Stop service
echo -e "${YELLOW}Stopping service...${NC}"
systemctl stop $SERVICE_NAME 2>/dev/null || true

# Download latest release
echo -e "${YELLOW}Downloading update...${NC}"
TEMP_DIR=$(mktemp -d)
TARBALL="$TEMP_DIR/release.tar.gz"

curl -L -o "$TARBALL" "$DOWNLOAD_URL"

if [ ! -f "$TARBALL" ]; then
    echo -e "${RED}Error: Download failed${NC}"
    systemctl start $SERVICE_NAME 2>/dev/null || true
    exit 1
fi

# Extract release
echo -e "${YELLOW}Extracting files...${NC}"
EXTRACT_DIR="$TEMP_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$TARBALL" -C "$EXTRACT_DIR"

# Find source directory
SOURCE_DIR=$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)

if [ -z "$SOURCE_DIR" ] || [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}Error: Could not find extracted files${NC}"
    systemctl start $SERVICE_NAME 2>/dev/null || true
    exit 1
fi

# Preserve config files
echo -e "${YELLOW}Preserving configuration...${NC}"
CONFIG_BACKUP=""
if [ -f "$INSTALL_DIR/.env" ]; then
    CONFIG_BACKUP="$TEMP_DIR/env_backup"
    cp "$INSTALL_DIR/.env" "$CONFIG_BACKUP"
fi

TOKENS_BACKUP=""
if [ -f "$INSTALL_DIR/api_tokens.json" ]; then
    TOKENS_BACKUP="$TEMP_DIR/tokens_backup"
    cp "$INSTALL_DIR/api_tokens.json" "$TOKENS_BACKUP"
fi

TEMPLATES_BACKUP=""
if [ -f "$INSTALL_DIR/templates.json" ]; then
    TEMPLATES_BACKUP="$TEMP_DIR/templates_backup"
    cp "$INSTALL_DIR/templates.json" "$TEMPLATES_BACKUP"
fi

QUEUES_BACKUP=""
if [ -f "$INSTALL_DIR/queues.json" ]; then
    QUEUES_BACKUP="$TEMP_DIR/queues_backup"
    cp "$INSTALL_DIR/queues.json" "$QUEUES_BACKUP"
fi

# Update files
echo -e "${YELLOW}Installing new version...${NC}"

# Remove old code files (keep data directories)
rm -rf "$INSTALL_DIR/app" 2>/dev/null || true
rm -rf "$INSTALL_DIR/templates" 2>/dev/null || true
rm -f "$INSTALL_DIR/requirements.txt" 2>/dev/null || true
rm -f "$INSTALL_DIR/README.md" 2>/dev/null || true
rm -f "$INSTALL_DIR/install.sh" 2>/dev/null || true
rm -f "$INSTALL_DIR/update.sh" 2>/dev/null || true
rm -f "$INSTALL_DIR/fix-nginx.sh" 2>/dev/null || true
rm -f "$INSTALL_DIR/setup_update_permissions.sh" 2>/dev/null || true

# Copy new files
cp -r "$SOURCE_DIR/app" "$INSTALL_DIR/"
cp -r "$SOURCE_DIR/templates" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/install.sh" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/update.sh" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/fix-nginx.sh" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/setup_update_permissions.sh" "$INSTALL_DIR/" 2>/dev/null || true

# Restore config files
if [ -n "$CONFIG_BACKUP" ] && [ -f "$CONFIG_BACKUP" ]; then
    cp "$CONFIG_BACKUP" "$INSTALL_DIR/.env"
fi

if [ -n "$TOKENS_BACKUP" ] && [ -f "$TOKENS_BACKUP" ]; then
    cp "$TOKENS_BACKUP" "$INSTALL_DIR/api_tokens.json"
fi

if [ -n "$TEMPLATES_BACKUP" ] && [ -f "$TEMPLATES_BACKUP" ]; then
    cp "$TEMPLATES_BACKUP" "$INSTALL_DIR/templates.json"
fi

if [ -n "$QUEUES_BACKUP" ] && [ -f "$QUEUES_BACKUP" ]; then
    cp "$QUEUES_BACKUP" "$INSTALL_DIR/queues.json"
fi

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
if [ -d "$VENV_DIR" ]; then
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet --no-cache-dir
else
    pip3 install -r "$INSTALL_DIR/requirements.txt" --quiet --no-cache-dir
fi

# Set permissions
chown -R root:root "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/update.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/install.sh" 2>/dev/null || true

# Clean up
rm -rf "$TEMP_DIR"

# Start service
echo -e "${YELLOW}Starting service...${NC}"
systemctl start $SERVICE_NAME

# Wait and check status
sleep 3
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Service started successfully${NC}"
else
    echo -e "${RED}Warning: Service may not be running properly${NC}"
    echo -e "${YELLOW}Check logs: journalctl -u $SERVICE_NAME -f${NC}"
fi

# Get new version
NEW_VERSION="unknown"
if [ -f "$INSTALL_DIR/app/version.py" ]; then
    NEW_VERSION=$(grep -oP 'CURRENT_VERSION\s*=\s*"\K[^"]+' "$INSTALL_DIR/app/version.py" 2>/dev/null || echo "unknown")
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Update Complete!                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Previous version: ${YELLOW}$CURRENT_VERSION${NC}"
echo -e "  New version:      ${GREEN}$NEW_VERSION${NC}"
echo -e "  Backup file:      ${BLUE}$BACKUP_FILE${NC}"
echo ""
echo -e "${YELLOW}Rollback command:${NC}"
echo -e "  tar -xzf $BACKUP_FILE -C $INSTALL_DIR && systemctl restart $SERVICE_NAME"
echo ""

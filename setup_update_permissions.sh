#!/bin/bash
#
# Setup Update Permissions for XUI Manager
# This script configures sudo permissions for auto-update functionality
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Check root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root: sudo bash $0"
    exit 1
fi

print_info "Setting up update permissions for XUI Manager..."

# Detect service user
SERVICE_USER=$(systemctl show -p User xui-manager | cut -d= -f2)

if [ -z "$SERVICE_USER" ] || [ "$SERVICE_USER" = "root" ]; then
    # Try to get from service file
    SERVICE_FILE="/etc/systemd/system/xui-manager.service"
    if [ -f "$SERVICE_FILE" ]; then
        SERVICE_USER=$(grep "^User=" "$SERVICE_FILE" | cut -d= -f2)
    fi
fi

if [ -z "$SERVICE_USER" ] || [ "$SERVICE_USER" = "root" ]; then
    print_warning "Could not detect service user, using 'root'"
    SERVICE_USER="root"
else
    print_success "Detected service user: $SERVICE_USER"
fi

# Create sudoers file
SUDOERS_FILE="/etc/sudoers.d/xui-manager-update"

print_info "Creating sudoers file: $SUDOERS_FILE"

cat > "$SUDOERS_FILE" <<EOF
# XUI Manager Auto-Update Permissions
# Allows xui-manager service to restart itself during updates
# Created: $(date)

# User: $SERVICE_USER
$SERVICE_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /bin/systemctl status xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl status xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /bin/systemctl start xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /bin/systemctl stop xui-manager
$SERVICE_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop xui-manager
EOF

# Set correct permissions
chmod 0440 "$SUDOERS_FILE"

# Validate sudoers file
if visudo -c -f "$SUDOERS_FILE" &>/dev/null; then
    print_success "Sudoers file created and validated successfully"
else
    print_error "Sudoers file validation failed"
    rm "$SUDOERS_FILE"
    exit 1
fi

# Test sudo permissions
print_info "Testing sudo permissions..."

if sudo -u "$SERVICE_USER" sudo -n systemctl status xui-manager &>/dev/null; then
    print_success "Sudo permissions working correctly"
else
    print_warning "Could not test sudo permissions (service may not be running)"
fi

print_success "Setup completed successfully!"
echo ""
print_info "The xui-manager service can now restart itself during updates"
print_info "Auto-update functionality is fully enabled"
echo ""
print_info "You can test the update system by:"
echo "  1. Opening the web interface: https://your-domain/manager/"
echo "  2. Checking the footer for version information"
echo "  3. Clicking 'Check for Updates' button"
echo ""

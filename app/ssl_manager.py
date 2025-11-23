"""
SSL/Certificate Manager for Let's Encrypt integration.
Handles certificate renewal, status checks, and 3x-ui integration.
"""

import os
import ssl
import socket
import subprocess
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class SSLManager:
    """Manager for SSL certificates with Let's Encrypt support."""

    def __init__(self, xui_db_path: str = "/etc/x-ui/x-ui.db"):
        self.xui_db_path = xui_db_path
        self.xui_config_path = "/usr/local/x-ui/bin/config.json"
        self.letsencrypt_base = "/etc/letsencrypt/live"
        self.renewal_threshold_days = 30  # Renew if less than 30 days left

    def get_domain_from_config(self) -> Optional[str]:
        """Get domain from various sources."""
        domain = None

        # Try to get from 3x-ui database
        try:
            if os.path.exists(self.xui_db_path):
                conn = sqlite3.connect(self.xui_db_path)
                cursor = conn.cursor()

                # Check various settings that might contain domain
                cursor.execute("""
                    SELECT key, value FROM settings
                    WHERE key IN ('webCertFile', 'webKeyFile', 'webDomain')
                """)

                for key, value in cursor.fetchall():
                    if key == 'webDomain' and value:
                        domain = value
                        break
                    elif key == 'webCertFile' and value:
                        # Extract domain from path like /etc/letsencrypt/live/domain/...
                        if '/letsencrypt/live/' in value:
                            parts = value.split('/letsencrypt/live/')
                            if len(parts) > 1:
                                domain = parts[1].split('/')[0]
                                break

                conn.close()
        except Exception as e:
            logger.error(f"Error reading domain from x-ui database: {e}")

        # Try to get from 3x-ui config.json
        if not domain:
            try:
                if os.path.exists(self.xui_config_path):
                    with open(self.xui_config_path, 'r') as f:
                        config = json.load(f)
                        domain = config.get('certDomain', '')
            except Exception as e:
                logger.error(f"Error reading domain from x-ui config: {e}")

        # Try to get from Nginx configs
        if not domain:
            domain = self._get_domain_from_nginx()

        # Try to get from Let's Encrypt directory
        if not domain:
            try:
                if os.path.exists(self.letsencrypt_base):
                    domains = [d for d in os.listdir(self.letsencrypt_base)
                              if os.path.isdir(os.path.join(self.letsencrypt_base, d))]
                    if domains:
                        domain = domains[0]
            except Exception as e:
                logger.error(f"Error reading from letsencrypt directory: {e}")

        return domain

    def _get_domain_from_nginx(self) -> Optional[str]:
        """Extract domain from Nginx configuration."""
        nginx_paths = [
            '/etc/nginx/sites-enabled/',
            '/etc/nginx/sites-available/',
            '/etc/nginx/conf.d/'
        ]

        for nginx_dir in nginx_paths:
            if not os.path.exists(nginx_dir):
                continue

            try:
                for filename in os.listdir(nginx_dir):
                    filepath = os.path.join(nginx_dir, filename)
                    if os.path.isfile(filepath):
                        with open(filepath, 'r') as f:
                            content = f.read()
                            # Look for server_name directive
                            import re
                            match = re.search(r'server_name\s+([^\s;]+)', content)
                            if match:
                                domain = match.group(1)
                                if domain and domain != '_' and domain != 'localhost':
                                    return domain
            except Exception as e:
                logger.error(f"Error reading nginx config {nginx_dir}: {e}")

        return None

    def get_certificate_info(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed information about the SSL certificate."""
        if not domain:
            domain = self.get_domain_from_config()

        if not domain:
            return {
                "status": "error",
                "message": "Domain not found",
                "has_certificate": False
            }

        cert_path = os.path.join(self.letsencrypt_base, domain, "fullchain.pem")
        key_path = os.path.join(self.letsencrypt_base, domain, "privkey.pem")

        if not os.path.exists(cert_path):
            return {
                "status": "not_found",
                "domain": domain,
                "has_certificate": False,
                "message": f"Certificate not found at {cert_path}"
            }

        try:
            # Read certificate details using openssl
            result = subprocess.run(
                ['openssl', 'x509', '-in', cert_path, '-noout', '-dates', '-subject'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "domain": domain,
                    "has_certificate": True,
                    "message": f"Error reading certificate: {result.stderr}"
                }

            output = result.stdout

            # Parse dates
            not_before = None
            not_after = None
            subject = None

            for line in output.split('\n'):
                if 'notBefore=' in line:
                    date_str = line.split('=')[1].strip()
                    not_before = self._parse_openssl_date(date_str)
                elif 'notAfter=' in line:
                    date_str = line.split('=')[1].strip()
                    not_after = self._parse_openssl_date(date_str)
                elif 'subject=' in line:
                    subject = line.split('=', 1)[1].strip()

            # Calculate days until expiry
            days_until_expiry = None
            is_expired = False
            needs_renewal = False

            if not_after:
                now = datetime.utcnow()
                days_until_expiry = (not_after - now).days
                is_expired = days_until_expiry < 0
                needs_renewal = days_until_expiry < self.renewal_threshold_days

            return {
                "status": "valid" if not is_expired else "expired",
                "domain": domain,
                "has_certificate": True,
                "cert_path": cert_path,
                "key_path": key_path,
                "not_before": not_before.isoformat() if not_before else None,
                "not_after": not_after.isoformat() if not_after else None,
                "days_until_expiry": days_until_expiry,
                "is_expired": is_expired,
                "needs_renewal": needs_renewal,
                "subject": subject
            }

        except Exception as e:
            logger.error(f"Error getting certificate info: {e}")
            return {
                "status": "error",
                "domain": domain,
                "has_certificate": True,
                "message": str(e)
            }

    def _parse_openssl_date(self, date_str: str) -> Optional[datetime]:
        """Parse OpenSSL date format."""
        try:
            # Format: "Dec 23 12:00:00 2024 GMT"
            return datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
        except ValueError:
            try:
                # Alternative format
                return datetime.strptime(date_str, "%b  %d %H:%M:%S %Y %Z")
            except ValueError:
                return None

    def renew_certificate(self, domain: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Renew SSL certificate using certbot."""
        if not domain:
            domain = self.get_domain_from_config()

        if not domain:
            return {
                "success": False,
                "message": "Domain not found. Please specify a domain."
            }

        # Check current certificate status
        cert_info = self.get_certificate_info(domain)

        if cert_info.get("has_certificate") and not cert_info.get("needs_renewal") and not force:
            return {
                "success": True,
                "message": f"Certificate is still valid for {cert_info.get('days_until_expiry')} days. Use force=true to renew anyway.",
                "renewed": False,
                "cert_info": cert_info
            }

        try:
            # Check if certbot is installed
            certbot_check = subprocess.run(['which', 'certbot'], capture_output=True)
            if certbot_check.returncode != 0:
                return {
                    "success": False,
                    "message": "certbot is not installed. Please install it with: apt install certbot python3-certbot-nginx"
                }

            # Determine renewal command
            if cert_info.get("has_certificate"):
                # Renew existing certificate
                cmd = [
                    'certbot', 'renew',
                    '--cert-name', domain,
                    '--non-interactive',
                    '--quiet'
                ]
                if force:
                    cmd.append('--force-renewal')
            else:
                # Obtain new certificate
                cmd = [
                    'certbot', '--nginx',
                    '-d', domain,
                    '--non-interactive',
                    '--agree-tos',
                    '--register-unsafely-without-email'
                ]

            logger.info(f"Running certbot command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "message": f"certbot failed: {result.stderr or result.stdout}",
                    "command": ' '.join(cmd)
                }

            # Get updated certificate info
            new_cert_info = self.get_certificate_info(domain)

            return {
                "success": True,
                "message": f"Certificate {'renewed' if cert_info.get('has_certificate') else 'obtained'} successfully",
                "renewed": True,
                "cert_info": new_cert_info,
                "output": result.stdout
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "certbot command timed out after 120 seconds"
            }
        except Exception as e:
            logger.error(f"Error renewing certificate: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def update_3xui_certificate(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Update 3x-ui panel to use the new certificate."""
        if not domain:
            domain = self.get_domain_from_config()

        if not domain:
            return {
                "success": False,
                "message": "Domain not found"
            }

        cert_path = os.path.join(self.letsencrypt_base, domain, "fullchain.pem")
        key_path = os.path.join(self.letsencrypt_base, domain, "privkey.pem")

        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            return {
                "success": False,
                "message": f"Certificate files not found for domain {domain}"
            }

        try:
            # Update 3x-ui database settings
            if os.path.exists(self.xui_db_path):
                conn = sqlite3.connect(self.xui_db_path)
                cursor = conn.cursor()

                # Update certificate paths in settings
                settings_to_update = [
                    ('webCertFile', cert_path),
                    ('webKeyFile', key_path),
                    ('webDomain', domain)
                ]

                for key, value in settings_to_update:
                    cursor.execute("""
                        INSERT OR REPLACE INTO settings (key, value)
                        VALUES (?, ?)
                    """, (key, value))

                conn.commit()
                conn.close()

                logger.info(f"Updated 3x-ui database with certificate paths for {domain}")

            # Update 3x-ui config.json if it exists
            if os.path.exists(self.xui_config_path):
                try:
                    with open(self.xui_config_path, 'r') as f:
                        config = json.load(f)

                    config['certFile'] = cert_path
                    config['keyFile'] = key_path
                    config['certDomain'] = domain

                    with open(self.xui_config_path, 'w') as f:
                        json.dump(config, f, indent=2)

                    logger.info(f"Updated 3x-ui config.json with certificate paths")
                except Exception as e:
                    logger.warning(f"Could not update 3x-ui config.json: {e}")

            return {
                "success": True,
                "message": f"Updated 3x-ui configuration with certificate for {domain}",
                "cert_path": cert_path,
                "key_path": key_path
            }

        except Exception as e:
            logger.error(f"Error updating 3x-ui certificate: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def restart_services(self) -> Dict[str, Any]:
        """Restart Nginx and 3x-ui services."""
        results = {
            "nginx": {"success": False, "message": ""},
            "x-ui": {"success": False, "message": ""},
            "xui-manager": {"success": False, "message": ""}
        }

        # Restart Nginx
        try:
            # Test nginx config first
            test_result = subprocess.run(
                ['nginx', '-t'],
                capture_output=True,
                text=True
            )

            if test_result.returncode != 0:
                results["nginx"]["message"] = f"Nginx config test failed: {test_result.stderr}"
            else:
                reload_result = subprocess.run(
                    ['systemctl', 'reload', 'nginx'],
                    capture_output=True,
                    text=True
                )

                if reload_result.returncode == 0:
                    results["nginx"]["success"] = True
                    results["nginx"]["message"] = "Nginx reloaded successfully"
                else:
                    results["nginx"]["message"] = f"Failed to reload nginx: {reload_result.stderr}"
        except Exception as e:
            results["nginx"]["message"] = str(e)

        # Restart 3x-ui
        try:
            restart_result = subprocess.run(
                ['systemctl', 'restart', 'x-ui'],
                capture_output=True,
                text=True
            )

            if restart_result.returncode == 0:
                results["x-ui"]["success"] = True
                results["x-ui"]["message"] = "x-ui restarted successfully"
            else:
                results["x-ui"]["message"] = f"Failed to restart x-ui: {restart_result.stderr}"
        except Exception as e:
            results["x-ui"]["message"] = str(e)

        # Note: xui-manager restart should be handled separately to avoid killing the current process
        results["xui-manager"]["success"] = True
        results["xui-manager"]["message"] = "xui-manager will continue running (restart separately if needed)"

        return results

    def full_certificate_renewal(self, domain: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        Complete certificate renewal process:
        1. Renew certificate with certbot
        2. Update 3x-ui configuration
        3. Restart services
        """
        steps = []

        # Step 1: Renew certificate
        renewal_result = self.renew_certificate(domain, force)
        steps.append({
            "step": "renew_certificate",
            "result": renewal_result
        })

        if not renewal_result.get("success"):
            return {
                "success": False,
                "message": "Certificate renewal failed",
                "steps": steps
            }

        # Get domain from renewal result
        used_domain = renewal_result.get("cert_info", {}).get("domain") or domain

        # Step 2: Update 3x-ui
        if renewal_result.get("renewed"):
            update_result = self.update_3xui_certificate(used_domain)
            steps.append({
                "step": "update_3xui",
                "result": update_result
            })

            if not update_result.get("success"):
                logger.warning(f"3x-ui update failed but continuing: {update_result.get('message')}")

            # Step 3: Restart services
            restart_result = self.restart_services()
            steps.append({
                "step": "restart_services",
                "result": restart_result
            })

        return {
            "success": True,
            "message": "Certificate renewal process completed",
            "renewed": renewal_result.get("renewed", False),
            "domain": used_domain,
            "cert_info": renewal_result.get("cert_info"),
            "steps": steps
        }

    def check_and_auto_renew(self) -> Dict[str, Any]:
        """
        Check certificate status and auto-renew if needed.
        This is called on application startup.
        """
        domain = self.get_domain_from_config()

        if not domain:
            return {
                "checked": True,
                "renewed": False,
                "message": "No domain configured, skipping SSL check"
            }

        cert_info = self.get_certificate_info(domain)

        if not cert_info.get("has_certificate"):
            return {
                "checked": True,
                "renewed": False,
                "message": f"No certificate found for {domain}",
                "cert_info": cert_info
            }

        if cert_info.get("is_expired") or cert_info.get("needs_renewal"):
            logger.info(f"Certificate needs renewal (days left: {cert_info.get('days_until_expiry')})")

            # Perform full renewal
            renewal_result = self.full_certificate_renewal(domain, force=False)

            return {
                "checked": True,
                "renewed": renewal_result.get("renewed", False),
                "message": "Auto-renewal performed" if renewal_result.get("renewed") else "Renewal not needed",
                "cert_info": cert_info,
                "renewal_result": renewal_result
            }

        return {
            "checked": True,
            "renewed": False,
            "message": f"Certificate is valid for {cert_info.get('days_until_expiry')} days",
            "cert_info": cert_info
        }


# Global instance
ssl_manager = SSLManager()

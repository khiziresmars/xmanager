#!/usr/bin/env python3
"""
3x-ui Configuration Diagnostics and Auto-Repair
Analyzes and fixes common configuration errors
"""

import json
import sqlite3
import subprocess
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Protocol field requirements
PROTOCOL_FIELDS = {
    "vmess": {
        "required": ["id", "alterId"],
        "optional": ["email", "level", "security"],
        "forbidden": ["password", "method", "flow"]
    },
    "vless": {
        "required": ["id"],
        "optional": ["email", "level", "flow", "encryption"],
        "forbidden": ["password", "method", "alterId"]
    },
    "trojan": {
        "required": ["password"],
        "optional": ["email", "level", "flow"],
        "forbidden": ["id", "alterId", "method"]
    },
    "shadowsocks": {
        "required": ["password", "method"],
        "optional": ["email", "level"],
        "forbidden": ["id", "alterId", "flow"]
    }
}

# Valid fingerprints (updated list)
VALID_FINGERPRINTS = [
    "randomized",
    "chrome",
    "firefox",
    "safari",
    "ios",
    "android",
    "edge",
    "360",
    "qq"
]

# Recommended fingerprint
RECOMMENDED_FINGERPRINT = "randomized"


class DiagnosticsManager:
    """Manages diagnostics and auto-repair of 3x-ui configuration"""

    def __init__(self, db_path: str = "/etc/x-ui/x-ui.db", config_path: str = "/usr/local/x-ui/bin/config.json"):
        self.db_path = db_path
        self.config_path = config_path
        self.backup_dir = "/opt/xui-manager/diagnostics_backups"
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Dict[str, str]:
        """Create backup of database and config"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backups = {}

        try:
            # Backup database
            if Path(self.db_path).exists():
                db_backup = f"{self.backup_dir}/x-ui_{timestamp}.db"
                shutil.copy2(self.db_path, db_backup)
                backups["database"] = db_backup
                logger.info(f"Database backed up to {db_backup}")

            # Backup config
            if Path(self.config_path).exists():
                config_backup = f"{self.backup_dir}/config_{timestamp}.json"
                shutil.copy2(self.config_path, config_backup)
                backups["config"] = config_backup
                logger.info(f"Config backed up to {config_backup}")

            return backups

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return {}

    def check_inbound_protocol(self, inbound: Dict) -> Dict:
        """Check if inbound has correct fields for its protocol"""
        protocol = inbound.get("protocol", "").lower()
        issues = []

        if protocol not in PROTOCOL_FIELDS:
            return {"valid": True, "issues": []}

        try:
            # Parse settings
            settings_str = inbound.get("settings", "{}")
            if isinstance(settings_str, str):
                settings = json.loads(settings_str) if settings_str else {}
            else:
                settings = settings_str

            clients = settings.get("clients", [])

            for idx, client in enumerate(clients):
                client_issues = []
                required_fields = PROTOCOL_FIELDS[protocol]["required"]
                forbidden_fields = PROTOCOL_FIELDS[protocol]["forbidden"]

                # Check required fields
                for field in required_fields:
                    if field not in client:
                        client_issues.append(f"Missing required field: {field}")

                # Check forbidden fields
                for field in forbidden_fields:
                    if field in client:
                        client_issues.append(f"Has forbidden field for {protocol}: {field}")

                if client_issues:
                    issues.append({
                        "client_index": idx,
                        "email": client.get("email", "unknown"),
                        "issues": client_issues
                    })

        except json.JSONDecodeError as e:
            issues.append({"error": f"Invalid JSON in settings: {e}"})

        return {
            "valid": len(issues) == 0,
            "protocol": protocol,
            "issues": issues
        }

    def fix_shadowsocks_clients(self, inbound_id: int, dry_run: bool = False) -> Dict:
        """Fix Shadowsocks clients with wrong fields"""
        import uuid

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get inbound
            cursor.execute("SELECT settings FROM inbounds WHERE id = ?", (inbound_id,))
            row = cursor.fetchone()

            if not row:
                return {"success": False, "message": "Inbound not found"}

            settings = json.loads(row[0])
            clients = settings.get("clients", [])
            fixed_count = 0
            removed_clients = []

            # Fix each client
            for client in clients[:]:  # Copy list to allow removal
                has_issues = False

                # Check if has VMESS fields in SS inbound
                if "id" in client or "alterId" in client:
                    has_issues = True

                if has_issues:
                    # Try to fix or remove
                    if "password" not in client or "method" not in client:
                        # Can't fix, remove
                        removed_clients.append(client.get("email", "unknown"))
                        clients.remove(client)
                        logger.info(f"Removed invalid SS client: {client.get('email')}")
                    else:
                        # Remove forbidden fields
                        client.pop("id", None)
                        client.pop("alterId", None)
                        client.pop("flow", None)
                        fixed_count += 1
                        logger.info(f"Fixed SS client: {client.get('email')}")

            if not dry_run and (fixed_count > 0 or removed_clients):
                # Update database
                settings["clients"] = clients
                new_settings = json.dumps(settings)

                cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", (new_settings, inbound_id))
                conn.commit()

            conn.close()

            return {
                "success": True,
                "fixed": fixed_count,
                "removed": len(removed_clients),
                "removed_emails": removed_clients,
                "dry_run": dry_run
            }

        except Exception as e:
            logger.error(f"Error fixing SS clients: {e}")
            return {"success": False, "message": str(e)}

    def check_fingerprints(self) -> Dict:
        """Check all fingerprints in database"""
        issues = []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT id, remark, stream_settings FROM inbounds")
            inbounds = cursor.fetchall()

            for inbound_id, remark, stream_settings_str in inbounds:
                try:
                    stream_settings = json.loads(stream_settings_str) if stream_settings_str else {}

                    # Check TLS settings
                    tls_settings = stream_settings.get("tlsSettings", {})
                    reality_settings = stream_settings.get("realitySettings", {})

                    for settings_type, settings in [("tls", tls_settings), ("reality", reality_settings)]:
                        if settings:
                            fingerprint = settings.get("fingerprint", "")

                            if not fingerprint:
                                issues.append({
                                    "inbound_id": inbound_id,
                                    "remark": remark,
                                    "issue": f"No fingerprint in {settings_type}Settings",
                                    "recommended": RECOMMENDED_FINGERPRINT
                                })
                            elif fingerprint not in VALID_FINGERPRINTS:
                                issues.append({
                                    "inbound_id": inbound_id,
                                    "remark": remark,
                                    "issue": f"Invalid fingerprint: {fingerprint}",
                                    "current": fingerprint,
                                    "recommended": RECOMMENDED_FINGERPRINT
                                })
                            elif fingerprint == "chrome" and settings_type == "reality":
                                issues.append({
                                    "inbound_id": inbound_id,
                                    "remark": remark,
                                    "issue": f"Outdated fingerprint for Reality: {fingerprint}",
                                    "current": fingerprint,
                                    "recommended": RECOMMENDED_FINGERPRINT
                                })

                except json.JSONDecodeError:
                    issues.append({
                        "inbound_id": inbound_id,
                        "remark": remark,
                        "issue": "Invalid JSON in stream_settings"
                    })

            conn.close()

            return {
                "total_checked": len(inbounds),
                "issues_found": len(issues),
                "issues": issues
            }

        except Exception as e:
            logger.error(f"Error checking fingerprints: {e}")
            return {"error": str(e)}

    def update_fingerprint(self, inbound_id: int, fingerprint: str = RECOMMENDED_FINGERPRINT, dry_run: bool = False) -> Dict:
        """Update fingerprint for inbound"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT stream_settings FROM inbounds WHERE id = ?", (inbound_id,))
            row = cursor.fetchone()

            if not row:
                return {"success": False, "message": "Inbound not found"}

            stream_settings = json.loads(row[0]) if row[0] else {}
            updated = False

            # Update TLS
            if "tlsSettings" in stream_settings:
                stream_settings["tlsSettings"]["fingerprint"] = fingerprint
                updated = True

            # Update Reality
            if "realitySettings" in stream_settings:
                stream_settings["realitySettings"]["fingerprint"] = fingerprint
                updated = True

            if updated and not dry_run:
                new_stream = json.dumps(stream_settings)
                cursor.execute("UPDATE inbounds SET stream_settings = ? WHERE id = ?", (new_stream, inbound_id))
                conn.commit()

            conn.close()

            return {
                "success": True,
                "updated": updated,
                "fingerprint": fingerprint,
                "dry_run": dry_run
            }

        except Exception as e:
            logger.error(f"Error updating fingerprint: {e}")
            return {"success": False, "message": str(e)}

    def validate_config_json(self) -> Dict:
        """Validate Xray config.json structure"""
        issues = []

        try:
            if not Path(self.config_path).exists():
                return {"valid": False, "issues": ["Config file not found"]}

            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Check required top-level fields
            required_fields = ["inbounds", "outbounds", "routing"]
            for field in required_fields:
                if field not in config:
                    issues.append(f"Missing required field: {field}")

            # Check inbounds
            if "inbounds" in config:
                for idx, inbound in enumerate(config["inbounds"]):
                    if "protocol" not in inbound:
                        issues.append(f"Inbound #{idx}: Missing protocol")
                    if "port" not in inbound and "listen" not in inbound:
                        issues.append(f"Inbound #{idx}: Missing port/listen")

            # Check outbounds
            if "outbounds" in config:
                if len(config["outbounds"]) == 0:
                    issues.append("No outbounds defined")

            return {
                "valid": len(issues) == 0,
                "issues": issues
            }

        except json.JSONDecodeError as e:
            return {"valid": False, "issues": [f"Invalid JSON: {e}"]}
        except Exception as e:
            return {"valid": False, "issues": [str(e)]}

    def diagnose_all(self) -> Dict:
        """Run full diagnostics"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "database": {},
            "config": {},
            "inbounds": [],
            "fingerprints": {},
            "overall_status": "healthy"
        }

        # Check database
        if Path(self.db_path).exists():
            results["database"]["exists"] = True
            results["database"]["path"] = self.db_path

            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Get all inbounds
                cursor.execute("SELECT id, protocol, remark FROM inbounds")
                inbounds = cursor.fetchall()

                for inbound_id, protocol, remark in inbounds:
                    cursor.execute("SELECT * FROM inbounds WHERE id = ?", (inbound_id,))
                    cursor.description
                    row = cursor.fetchone()

                    inbound_dict = {
                        "id": row[0],
                        "protocol": row[2],
                        "settings": row[4],
                        "stream_settings": row[5]
                    }

                    check_result = self.check_inbound_protocol(inbound_dict)
                    check_result["id"] = inbound_id
                    check_result["remark"] = remark

                    if not check_result["valid"]:
                        results["overall_status"] = "issues_found"

                    results["inbounds"].append(check_result)

                conn.close()

            except Exception as e:
                results["database"]["error"] = str(e)
                results["overall_status"] = "error"

        else:
            results["database"]["exists"] = False
            results["overall_status"] = "error"

        # Check config.json
        results["config"] = self.validate_config_json()
        if not results["config"].get("valid"):
            results["overall_status"] = "issues_found"

        # Check fingerprints
        results["fingerprints"] = self.check_fingerprints()
        if results["fingerprints"].get("issues_found", 0) > 0:
            results["overall_status"] = "issues_found"

        return results

    def auto_fix(self, fix_shadowsocks: bool = True, update_fingerprints: bool = True, backup: bool = True) -> Dict:
        """Automatically fix common issues"""
        if backup:
            backups = self.create_backup()
            if not backups:
                return {"success": False, "message": "Failed to create backup"}
        else:
            backups = {}

        results = {
            "success": True,
            "backups": backups,
            "fixes": []
        }

        try:
            # Fix Shadowsocks clients
            if fix_shadowsocks:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id, protocol FROM inbounds WHERE protocol = 'shadowsocks'")
                ss_inbounds = cursor.fetchall()
                conn.close()

                for inbound_id, _ in ss_inbounds:
                    fix_result = self.fix_shadowsocks_clients(inbound_id, dry_run=False)
                    if fix_result["success"] and (fix_result["fixed"] > 0 or fix_result["removed"] > 0):
                        results["fixes"].append({
                            "type": "shadowsocks_fix",
                            "inbound_id": inbound_id,
                            "result": fix_result
                        })

            # Update fingerprints
            if update_fingerprints:
                fp_check = self.check_fingerprints()
                for issue in fp_check.get("issues", []):
                    inbound_id = issue["inbound_id"]
                    update_result = self.update_fingerprint(inbound_id, dry_run=False)
                    if update_result["success"]:
                        results["fixes"].append({
                            "type": "fingerprint_update",
                            "inbound_id": inbound_id,
                            "result": update_result
                        })

            return results

        except Exception as e:
            logger.error(f"Error in auto_fix: {e}")
            return {"success": False, "message": str(e)}

    def restart_xui(self) -> bool:
        """Restart x-ui service"""
        try:
            result = subprocess.run(
                ["systemctl", "restart", "x-ui"],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error restarting x-ui: {e}")
            return False


# Global instance
diagnostics = DiagnosticsManager()

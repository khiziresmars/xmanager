"""
Camouflage/Fake Website Manager for XUI-Manager
Provides fake website templates for hiding proxy infrastructure
Inspired by: https://github.com/GFW4Fun/x-ui-pro (170+ templates)
"""

import os
import random
import shutil
import logging
import subprocess
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class FakeSiteCategory(Enum):
    """Categories of fake websites"""
    BUSINESS = "business"
    PORTFOLIO = "portfolio"
    BLOG = "blog"
    LANDING = "landing"
    ECOMMERCE = "ecommerce"
    TECH = "tech"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    MINIMAL = "minimal"


@dataclass
class FakeSiteTemplate:
    """Fake website template"""
    id: str
    name: str
    category: FakeSiteCategory
    description: str
    preview_image: Optional[str] = None


# Pre-built fake site templates (HTML content)
FAKE_SITE_TEMPLATES = {
    "corporate_blue": {
        "name": "Corporate Blue",
        "category": FakeSiteCategory.BUSINESS,
        "description": "Professional corporate website with blue theme",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TechCorp Solutions - Enterprise Technology</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; }
        .header { background: linear-gradient(135deg, #1a5276 0%, #2980b9 100%); color: white; padding: 20px 50px; }
        .header h1 { font-size: 24px; }
        .nav { display: flex; gap: 30px; margin-top: 15px; }
        .nav a { color: rgba(255,255,255,0.9); text-decoration: none; }
        .hero { background: linear-gradient(135deg, #2980b9 0%, #1a5276 100%); color: white; padding: 100px 50px; text-align: center; }
        .hero h2 { font-size: 48px; margin-bottom: 20px; }
        .hero p { font-size: 18px; opacity: 0.9; max-width: 600px; margin: 0 auto; }
        .services { display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; padding: 80px 50px; max-width: 1200px; margin: 0 auto; }
        .service { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        .service h3 { color: #1a5276; margin-bottom: 15px; }
        .footer { background: #1a252f; color: white; padding: 40px 50px; text-align: center; }
    </style>
</head>
<body>
    <header class="header">
        <h1>TechCorp Solutions</h1>
        <nav class="nav">
            <a href="#">Home</a>
            <a href="#">Services</a>
            <a href="#">About</a>
            <a href="#">Contact</a>
        </nav>
    </header>
    <section class="hero">
        <h2>Enterprise Technology Solutions</h2>
        <p>Empowering businesses with cutting-edge technology and innovative solutions for the digital age.</p>
    </section>
    <section class="services">
        <div class="service">
            <h3>Cloud Infrastructure</h3>
            <p>Scalable and secure cloud solutions tailored to your business needs.</p>
        </div>
        <div class="service">
            <h3>Cybersecurity</h3>
            <p>Comprehensive security solutions to protect your digital assets.</p>
        </div>
        <div class="service">
            <h3>Digital Transformation</h3>
            <p>Modernize your business with our digital transformation expertise.</p>
        </div>
    </section>
    <footer class="footer">
        <p>&copy; 2024 TechCorp Solutions. All rights reserved.</p>
    </footer>
</body>
</html>"""
    },

    "portfolio_dark": {
        "name": "Portfolio Dark",
        "category": FakeSiteCategory.PORTFOLIO,
        "description": "Dark themed portfolio website",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alex Johnson - Creative Designer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #0a0a0a; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
        .header { padding: 30px 0; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: bold; }
        .nav a { color: #888; margin-left: 30px; text-decoration: none; transition: color 0.3s; }
        .nav a:hover { color: #fff; }
        .hero { padding: 150px 0; text-align: center; }
        .hero h1 { font-size: 72px; margin-bottom: 20px; background: linear-gradient(90deg, #ff6b6b, #feca57); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero p { font-size: 20px; color: #888; }
        .work { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; padding: 50px 0; }
        .work-item { background: #151515; aspect-ratio: 16/9; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
        .footer { text-align: center; padding: 50px 0; color: #444; }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="logo">AJ.</div>
            <nav class="nav">
                <a href="#">Work</a>
                <a href="#">About</a>
                <a href="#">Contact</a>
            </nav>
        </header>
        <section class="hero">
            <h1>Creative Designer</h1>
            <p>Crafting beautiful digital experiences since 2015</p>
        </section>
        <section class="work">
            <div class="work-item">Project 1</div>
            <div class="work-item">Project 2</div>
            <div class="work-item">Project 3</div>
            <div class="work-item">Project 4</div>
        </section>
        <footer class="footer">
            <p>&copy; 2024 Alex Johnson. All rights reserved.</p>
        </footer>
    </div>
</body>
</html>"""
    },

    "blog_minimal": {
        "name": "Minimal Blog",
        "category": FakeSiteCategory.BLOG,
        "description": "Clean minimal blog design",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thoughts & Ideas - A Personal Blog</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Georgia, serif; background: #fefefe; color: #333; line-height: 1.8; }
        .container { max-width: 700px; margin: 0 auto; padding: 40px 20px; }
        .header { text-align: center; padding: 60px 0; border-bottom: 1px solid #eee; }
        .header h1 { font-size: 32px; font-weight: normal; }
        .header p { color: #888; margin-top: 10px; }
        .post { padding: 40px 0; border-bottom: 1px solid #eee; }
        .post-date { color: #888; font-size: 14px; }
        .post h2 { font-size: 24px; font-weight: normal; margin: 10px 0; }
        .post h2 a { color: #333; text-decoration: none; }
        .post p { color: #555; }
        .footer { text-align: center; padding: 40px 0; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>Thoughts & Ideas</h1>
            <p>A personal blog about technology, design, and life</p>
        </header>
        <article class="post">
            <span class="post-date">December 5, 2024</span>
            <h2><a href="#">The Art of Simplicity in Design</a></h2>
            <p>Exploring how minimalism can enhance user experience and create more meaningful digital products...</p>
        </article>
        <article class="post">
            <span class="post-date">November 28, 2024</span>
            <h2><a href="#">Future of Web Development</a></h2>
            <p>Predictions and insights on emerging technologies that will shape the web in the coming years...</p>
        </article>
        <footer class="footer">
            <p>&copy; 2024 Thoughts & Ideas</p>
        </footer>
    </div>
</body>
</html>"""
    },

    "landing_startup": {
        "name": "Startup Landing",
        "category": FakeSiteCategory.LANDING,
        "description": "Modern startup landing page",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LaunchPad - Your Ideas, Launched</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .gradient { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .header { padding: 20px 50px; display: flex; justify-content: space-between; align-items: center; }
        .logo { color: white; font-size: 24px; font-weight: bold; }
        .btn { background: white; color: #667eea; padding: 12px 30px; border-radius: 25px; text-decoration: none; font-weight: 600; }
        .hero { text-align: center; padding: 150px 50px; color: white; }
        .hero h1 { font-size: 56px; margin-bottom: 20px; }
        .hero p { font-size: 20px; opacity: 0.9; margin-bottom: 40px; }
        .hero .btn-hero { background: white; color: #667eea; padding: 15px 40px; border-radius: 30px; font-size: 18px; text-decoration: none; }
        .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; padding: 100px 50px; background: white; }
        .feature { text-align: center; }
        .feature-icon { font-size: 48px; margin-bottom: 20px; }
        .feature h3 { margin-bottom: 10px; color: #333; }
        .feature p { color: #666; }
    </style>
</head>
<body>
    <div class="gradient">
        <header class="header">
            <div class="logo">LaunchPad</div>
            <a href="#" class="btn">Get Started</a>
        </header>
        <section class="hero">
            <h1>Your Ideas, Launched</h1>
            <p>The fastest way to build and deploy your next big project</p>
            <a href="#" class="btn-hero">Start Free Trial</a>
        </section>
    </div>
    <section class="features">
        <div class="feature">
            <div class="feature-icon">&#9889;</div>
            <h3>Lightning Fast</h3>
            <p>Deploy in seconds, scale infinitely</p>
        </div>
        <div class="feature">
            <div class="feature-icon">&#128274;</div>
            <h3>Secure by Default</h3>
            <p>Enterprise-grade security built-in</p>
        </div>
        <div class="feature">
            <div class="feature-icon">&#127759;</div>
            <h3>Global CDN</h3>
            <p>Lightning fast worldwide delivery</p>
        </div>
    </section>
</body>
</html>"""
    },

    "maintenance": {
        "name": "Maintenance Page",
        "category": FakeSiteCategory.MINIMAL,
        "description": "Simple maintenance/coming soon page",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Site Under Maintenance</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { text-align: center; padding: 40px; }
        .icon { font-size: 64px; margin-bottom: 20px; }
        h1 { font-size: 32px; color: #333; margin-bottom: 10px; }
        p { color: #666; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#128736;</div>
        <h1>Under Maintenance</h1>
        <p>We'll be back shortly. Thank you for your patience.</p>
    </div>
</body>
</html>"""
    },

    "ecommerce_store": {
        "name": "E-Commerce Store",
        "category": FakeSiteCategory.ECOMMERCE,
        "description": "Online store template",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StyleHub - Fashion & Lifestyle</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Helvetica Neue', sans-serif; background: #fff; }
        .header { background: #000; color: white; padding: 15px 50px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: bold; letter-spacing: 2px; }
        .nav a { color: white; margin-left: 30px; text-decoration: none; font-size: 14px; }
        .banner { background: #f8f8f8; padding: 80px 50px; text-align: center; }
        .banner h1 { font-size: 48px; margin-bottom: 20px; }
        .products { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; padding: 50px; }
        .product { background: #f8f8f8; aspect-ratio: 3/4; display: flex; align-items: center; justify-content: center; }
        .footer { background: #000; color: white; padding: 40px 50px; text-align: center; }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">STYLEHUB</div>
        <nav class="nav">
            <a href="#">New Arrivals</a>
            <a href="#">Women</a>
            <a href="#">Men</a>
            <a href="#">Sale</a>
        </nav>
    </header>
    <section class="banner">
        <h1>Winter Collection 2024</h1>
        <p>Discover the latest trends</p>
    </section>
    <section class="products">
        <div class="product">Product 1</div>
        <div class="product">Product 2</div>
        <div class="product">Product 3</div>
        <div class="product">Product 4</div>
    </section>
    <footer class="footer">
        <p>&copy; 2024 StyleHub. All rights reserved.</p>
    </footer>
</body>
</html>"""
    },

    "tech_docs": {
        "name": "Tech Documentation",
        "category": FakeSiteCategory.TECH,
        "description": "Technical documentation site",
        "html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation - DevPlatform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; display: flex; }
        .sidebar { width: 280px; background: #16213e; padding: 20px; height: 100vh; }
        .sidebar h2 { font-size: 20px; margin-bottom: 20px; color: #4a9fff; }
        .sidebar a { display: block; color: #888; padding: 10px 0; text-decoration: none; border-left: 2px solid transparent; padding-left: 15px; }
        .sidebar a:hover { color: #fff; border-left-color: #4a9fff; }
        .content { flex: 1; padding: 40px; }
        .content h1 { font-size: 36px; margin-bottom: 20px; }
        .code-block { background: #0f0f1a; padding: 20px; border-radius: 8px; font-family: 'Fira Code', monospace; margin: 20px 0; }
        .method { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-right: 10px; }
        .get { background: #10b981; }
        .post { background: #3b82f6; }
    </style>
</head>
<body>
    <nav class="sidebar">
        <h2>DevPlatform API</h2>
        <a href="#">Getting Started</a>
        <a href="#">Authentication</a>
        <a href="#">Users</a>
        <a href="#">Projects</a>
        <a href="#">Webhooks</a>
    </nav>
    <main class="content">
        <h1>API Reference</h1>
        <p>Welcome to the DevPlatform API documentation. Get started by obtaining your API key.</p>
        <div class="code-block">
            <span class="method get">GET</span> /api/v1/users
        </div>
        <p>Returns a list of all users in your organization.</p>
    </main>
</body>
</html>"""
    }
}


class CamouflageManager:
    """Manages fake website camouflage for nginx"""

    DEFAULT_ROOT = "/var/www/html"
    BACKUP_DIR = "/opt/xui-manager/backups/camouflage"

    def __init__(self, web_root: str = None):
        self.web_root = web_root or self.DEFAULT_ROOT
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available fake site templates"""
        templates = []
        for template_id, template in FAKE_SITE_TEMPLATES.items():
            templates.append({
                "id": template_id,
                "name": template["name"],
                "category": template["category"].value,
                "description": template["description"]
            })
        return templates

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific template"""
        return FAKE_SITE_TEMPLATES.get(template_id)

    def get_random_template(self, category: str = None) -> Dict[str, Any]:
        """Get a random template, optionally from specific category"""
        templates = list(FAKE_SITE_TEMPLATES.items())

        if category:
            try:
                cat_enum = FakeSiteCategory(category)
                templates = [
                    (k, v) for k, v in templates
                    if v["category"] == cat_enum
                ]
            except ValueError:
                pass

        if not templates:
            templates = list(FAKE_SITE_TEMPLATES.items())

        template_id, template = random.choice(templates)
        return {"id": template_id, **template}

    def get_current_site(self) -> Dict[str, Any]:
        """Get current fake site if installed"""
        index_path = os.path.join(self.web_root, "index.html")

        if not os.path.exists(index_path):
            return {"installed": False}

        try:
            with open(index_path, 'r') as f:
                content = f.read()

            # Try to identify template
            for template_id, template in FAKE_SITE_TEMPLATES.items():
                if template["html"][:100] in content[:200]:
                    return {
                        "installed": True,
                        "template_id": template_id,
                        "template_name": template["name"]
                    }

            return {
                "installed": True,
                "template_id": "custom",
                "template_name": "Custom Site"
            }

        except Exception as e:
            logger.error(f"Error reading current site: {e}")
            return {"installed": False, "error": str(e)}

    def install_template(self, template_id: str, backup: bool = True) -> Dict[str, Any]:
        """Install a fake site template"""
        try:
            template = FAKE_SITE_TEMPLATES.get(template_id)
            if not template:
                return {"success": False, "error": f"Template not found: {template_id}"}

            # Backup current site
            if backup:
                self._backup_current()

            # Ensure web root exists
            os.makedirs(self.web_root, exist_ok=True)

            # Write index.html
            index_path = os.path.join(self.web_root, "index.html")
            with open(index_path, 'w') as f:
                f.write(template["html"])

            # Set permissions
            os.chmod(index_path, 0o644)

            logger.info(f"Installed fake site template: {template_id}")

            return {
                "success": True,
                "message": f"Template '{template['name']}' installed",
                "template_id": template_id,
                "path": index_path
            }

        except Exception as e:
            logger.error(f"Error installing template: {e}")
            return {"success": False, "error": str(e)}

    def install_random(self, category: str = None) -> Dict[str, Any]:
        """Install a random fake site template"""
        template = self.get_random_template(category)
        return self.install_template(template["id"])

    def install_custom(self, html_content: str, backup: bool = True) -> Dict[str, Any]:
        """Install custom HTML content"""
        try:
            if backup:
                self._backup_current()

            os.makedirs(self.web_root, exist_ok=True)

            index_path = os.path.join(self.web_root, "index.html")
            with open(index_path, 'w') as f:
                f.write(html_content)

            os.chmod(index_path, 0o644)

            return {
                "success": True,
                "message": "Custom site installed",
                "path": index_path
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backup_current(self):
        """Backup current site content"""
        try:
            index_path = os.path.join(self.web_root, "index.html")
            if os.path.exists(index_path):
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(self.BACKUP_DIR, f"index_{timestamp}.html")
                shutil.copy2(index_path, backup_path)
                logger.info(f"Backed up current site to {backup_path}")
        except Exception as e:
            logger.warning(f"Could not backup current site: {e}")

    def remove_site(self) -> Dict[str, Any]:
        """Remove the fake site"""
        try:
            index_path = os.path.join(self.web_root, "index.html")

            if os.path.exists(index_path):
                self._backup_current()
                os.remove(index_path)

            return {"success": True, "message": "Fake site removed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def preview_template(self, template_id: str) -> Optional[str]:
        """Get HTML preview of a template"""
        template = FAKE_SITE_TEMPLATES.get(template_id)
        if template:
            return template["html"]
        return None


# Global instance
_camouflage_manager = None


def get_camouflage_manager() -> CamouflageManager:
    """Get or create camouflage manager instance"""
    global _camouflage_manager
    if _camouflage_manager is None:
        _camouflage_manager = CamouflageManager()
    return _camouflage_manager

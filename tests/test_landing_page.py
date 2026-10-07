"""
Unit tests for Minimalist Landing Page, Offline Solution A Guide, and Offline Bat Launcher.
"""

import unittest
from pathlib import Path


class TestLandingPageAndOfflineGuide(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.html_file = self.root_dir / "src" / "web" / "static" / "index.html"
        self.css_file = self.root_dir / "src" / "web" / "static" / "style.css"
        self.js_file = self.root_dir / "src" / "web" / "static" / "app.js"
        self.bat_file = self.root_dir / "start_offline_chat.bat"

    def test_html_contains_landing_modal_and_components(self):
        self.assertTrue(self.html_file.exists(), "index.html must exist")
        content = self.html_file.read_text(encoding="utf-8")

        # Navbar Guide button
        self.assertIn('id="btn-guide-toggle"', content)
        self.assertIn("btn-guide-nav", content)
        self.assertIn("openLandingModal()", content)

        # Landing Modal container
        self.assertIn('id="landing-modal"', content)
        self.assertIn("landing-box", content)

        # Hero section & title
        self.assertIn("Private Local Communication.", content)
        self.assertIn("Zero Internet Required.", content)

        # 3 Quick Action Cards
        self.assertIn("launchChatFromLanding()", content)
        self.assertIn("Enter Live Chat", content)
        self.assertIn("startPrivateNetworkFlow()", content)
        self.assertIn("Start Private Network", content)
        self.assertIn("scrollToOfflineGuide()", content)
        self.assertIn("Offline Mode Guide", content)

        # Solution A Zero-Internet Hotspot Guide (4 steps)
        self.assertIn("SOLUTION A", content)
        self.assertIn("Turn On Hotspot", content)
        self.assertIn("Connect Devices", content)
        self.assertIn("Start Local Host", content)
        self.assertIn("Scan &amp; Chat at 300+ Mbps", content)
        self.assertIn("start_offline_chat.bat", content)

        # Features grid
        self.assertIn("Ultra-Fast Direct LAN Transfer", content)
        self.assertIn("In-Browser Voice Notes", content)
        self.assertIn("End-to-End Encryption", content)
        self.assertIn("Zero Mobile App Store Installs", content)

        # Skip landing checkbox
        self.assertIn('id="chk-skip-landing"', content)

    def test_css_contains_landing_and_guide_styles(self):
        self.assertTrue(self.css_file.exists(), "style.css must exist")
        content = self.css_file.read_text(encoding="utf-8")

        self.assertIn(".btn-guide-nav", content)
        self.assertIn(".landing-box", content)
        self.assertIn(".landing-hero-title", content)
        self.assertIn(".landing-actions-grid", content)
        self.assertIn(".landing-action-card", content)
        self.assertIn(".landing-offline-section", content)
        self.assertIn(".offline-steps-grid", content)
        self.assertIn(".offline-step-card", content)
        self.assertIn(".landing-features-grid", content)
        self.assertIn(".landing-remember-checkbox", content)

    def test_js_contains_landing_logic_and_option3_behavior(self):
        self.assertTrue(self.js_file.exists(), "app.js must exist")
        content = self.js_file.read_text(encoding="utf-8")

        # DOM references
        self.assertIn("btnGuideToggle:", content)
        self.assertIn("landingModal:", content)
        self.assertIn("chkSkipLanding:", content)

        # Event listener wiring
        self.assertIn("dom.btnGuideToggle.addEventListener", content)

        # Modal functions
        self.assertIn("function openLandingModal(", content)
        self.assertIn("function closeLandingModal(", content)
        self.assertIn("function launchChatFromLanding(", content)
        self.assertIn("function startPrivateNetworkFlow(", content)
        self.assertIn("function scrollToOfflineGuide(", content)

        # Global window bindings
        self.assertIn("window.openLandingModal = openLandingModal", content)
        self.assertIn("window.closeLandingModal = closeLandingModal", content)
        self.assertIn("window.launchChatFromLanding = launchChatFromLanding", content)
        self.assertIn("window.startPrivateNetworkFlow = startPrivateNetworkFlow", content)
        self.assertIn("window.scrollToOfflineGuide = scrollToOfflineGuide", content)

        # Option 3 check: only direct visits without pendingAutoJoin show landing modal
        self.assertIn("!state.pendingAutoJoin && !shouldSkipLanding", content)

    def test_offline_bat_launcher(self):
        self.assertTrue(self.bat_file.exists(), "start_offline_chat.bat must exist in repo root")
        content = self.bat_file.read_text(encoding="utf-8")

        self.assertIn("OFFLINE / ZERO-INTERNET MODE", content)
        self.assertIn("SOLUTION A: MOBILE HOTSPOT SETUP", content)
        self.assertIn("python web_main.py --port 8080", content)
        self.assertIn("http://localhost:8080", content)


if __name__ == "__main__":
    unittest.main()

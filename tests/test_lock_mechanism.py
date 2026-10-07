"""
Unit tests for Room Lock & End-to-End Encryption Mechanism.
"""

import unittest
from pathlib import Path


class TestRoomLockMechanism(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.html_file = self.root_dir / "src" / "web" / "static" / "index.html"
        self.css_file = self.root_dir / "src" / "web" / "static" / "style.css"
        self.js_file = self.root_dir / "src" / "web" / "static" / "app.js"

    def test_html_contains_lock_components(self):
        content = self.html_file.read_text(encoding="utf-8")

        # Header lock button with dynamic icon & label
        self.assertIn('id="btn-header-encrypt"', content)
        self.assertIn('id="encrypt-icon"', content)
        self.assertIn('id="encrypt-label"', content)
        self.assertIn("openEncryptionModal()", content)

        # Room creation modal with optional passphrase field
        self.assertIn('id="room-modal"', content)
        self.assertIn('id="input-room-passkey"', content)

        # Room encryption modal
        self.assertIn('id="encryption-modal"', content)
        self.assertIn('id="encryption-status-banner"', content)
        self.assertIn('id="input-room-secret"', content)
        self.assertIn("saveRoomEncryption()", content)
        self.assertIn("disableRoomEncryption()", content)

    def test_css_contains_lock_styles(self):
        content = self.css_file.read_text(encoding="utf-8")

        self.assertIn(".btn-action-secondary.lock-active", content)
        self.assertIn(".room-lock-tag", content)
        self.assertIn(".peer-item.has-lock", content)
        self.assertIn(".encryption-status-banner", content)
        self.assertIn(".encrypted-locked-bubble", content)
        self.assertIn(".btn-bubble-unlock", content)

    def test_js_contains_authenticated_cipher_and_lock_logic(self):
        content = self.js_file.read_text(encoding="utf-8")

        # DOM bindings
        self.assertIn("inputRoomPasskey:", content)
        self.assertIn("encryptLabel:", content)
        self.assertIn("encryptionStatusBanner:", content)

        # Passphrase handling during room creation
        self.assertIn("dom.inputRoomPasskey", content)

        # Authenticated cipher functions
        self.assertIn("function djb2Hash(", content)
        self.assertIn("function encryptMessagePayload(", content)
        self.assertIn("function decryptMessagePayload(", content)
        self.assertIn("[ENC:v1:", content)

        # Global window bindings
        self.assertIn("window.openEncryptionModal = openEncryptionModal", content)
        self.assertIn("window.closeEncryptionModal = closeEncryptionModal", content)
        self.assertIn("window.saveRoomEncryption = saveRoomEncryption", content)
        self.assertIn("window.disableRoomEncryption = disableRoomEncryption", content)

        # Interactive unlock prompt in message rows
        self.assertIn("encrypted-locked-bubble", content)
        self.assertIn("btn-bubble-unlock", content)


if __name__ == "__main__":
    unittest.main()

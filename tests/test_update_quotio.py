import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("update_quotio", Path(__file__).parents[1] / "scripts/update_quotio.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)

DMG = b"test disk image"
SHA = hashlib.sha256(DMG).hexdigest()
RELEASE = {
    "tag_name": "v0.33.1", "draft": False, "prerelease": False,
    "assets": [{
        "name": "Quotio-0.33.1.dmg", "state": "uploaded", "size": len(DMG),
        "browser_download_url": f"{updater.RELEASE_BASE}/v0.33.1/Quotio-0.33.1.dmg",
        "digest": f"sha256:{SHA}",
    }],
}


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "quotio.rb"
        self.original = 'cask "quotio" do\n  version "0.33.0"\n  sha256 "' + '0' * 64 + '"\n  app "Quotio.app"\nend\n'
        self.path.write_text(self.original)

    def test_new_release_uses_downloaded_checksum_and_preserves_other_lines(self):
        with patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(DMG)):
            self.assertEqual(updater.update_cask(self.path, RELEASE), (True, "0.33.1"))
        expected = self.original.replace('"0.33.0"', '"0.33.1"').replace('0' * 64, SHA)
        self.assertEqual(self.path.read_text(), expected)

    def test_current_release_is_a_noop_without_downloading(self):
        text = self.original.replace('"0.33.0"', '"0.33.1"').replace('0' * 64, SHA)
        self.path.write_text(text)
        with patch.object(updater, "download_sha256") as download:
            self.assertEqual(updater.update_cask(self.path, RELEASE), (False, "0.33.1"))
            download.assert_not_called()
        self.assertEqual(self.path.read_text(), text)

    def test_same_version_can_repair_a_changed_checksum(self):
        self.path.write_text(self.original.replace('"0.33.0"', '"0.33.1"'))
        with patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(DMG)):
            self.assertEqual(updater.update_cask(self.path, RELEASE), (True, "0.33.1"))
        self.assertIn(SHA, self.path.read_text())

    def test_older_upstream_version_does_not_downgrade(self):
        text = self.original.replace('"0.33.0"', '"0.34.0"')
        self.path.write_text(text)
        with patch.object(updater, "download_sha256") as download:
            self.assertEqual(updater.update_cask(self.path, RELEASE), (False, "0.34.0"))
            download.assert_not_called()
        self.assertEqual(self.path.read_text(), text)

    def test_unsafe_or_incomplete_release_does_not_change_the_cask(self):
        invalid = []
        for field in ("draft", "prerelease"):
            release = copy.deepcopy(RELEASE)
            release[field] = True
            invalid.append(release)
        for field, value in (("name", "wrong.dmg"), ("state", "new"), ("browser_download_url", "https://example.com/app.dmg")):
            release = copy.deepcopy(RELEASE)
            release["assets"][0][field] = value
            invalid.append(release)
        release = copy.deepcopy(RELEASE)
        release["tag_name"] = "v0.33.1-beta"
        invalid.append(release)
        for release in invalid:
            with self.subTest(release=release), patch.object(updater, "download_sha256") as download:
                with self.assertRaises(ValueError):
                    updater.update_cask(self.path, release)
                download.assert_not_called()
                self.assertEqual(self.path.read_text(), self.original)

    def test_bad_download_does_not_change_the_cask(self):
        for data in (DMG[:-1], b"x" * len(DMG)):
            with self.subTest(data=data), patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(data)):
                with self.assertRaises(ValueError):
                    updater.update_cask(self.path, RELEASE)
                self.assertEqual(self.path.read_text(), self.original)

    def test_download_without_a_github_digest_still_computes_checksum(self):
        release = copy.deepcopy(RELEASE)
        release["assets"][0]["digest"] = None
        with patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(DMG)):
            self.assertEqual(updater.update_cask(self.path, release), (True, "0.33.1"))
        self.assertIn(SHA, self.path.read_text())


if __name__ == "__main__":
    unittest.main()

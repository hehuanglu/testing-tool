import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("semgrep_skill", Path(__file__).resolve().parents[1] / "scripts/install_skill.py")
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


class SkillInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "repo/skill"
        self.source.mkdir(parents=True)
        (self.source / "SKILL.md").write_text("current")
        (self.source / "rules").mkdir()
        (self.source / "rules/local.yml").write_text("rules: []")
        self.target = self.root / "codex/skills/run-semgrep-scanner"

    def test_fresh_install_includes_nested_resources_and_is_repeatable(self):
        self.assertIsNone(skill.install(self.source, self.target))
        self.assertEqual(skill.differences(self.source, self.target), [])
        self.assertIsNone(skill.install(self.source, self.target))

    def test_changed_copy_requires_update_and_preserves_previous_files(self):
        skill.install(self.source, self.target)
        (self.target / "SKILL.md").write_text("personal")
        (self.target / "stale.py").write_text("old")
        with self.assertRaises(ValueError):
            skill.install(self.source, self.target)
        backup = skill.install(self.source, self.target, update=True)
        self.assertEqual((backup / "SKILL.md").read_text(), "personal")
        self.assertTrue((backup / "stale.py").exists())
        self.assertNotIn(self.target.parent, backup.parents)
        self.assertFalse((self.target / "stale.py").exists())
        self.assertEqual(skill.differences(self.source, self.target), [])

    def test_cache_does_not_create_drift(self):
        skill.install(self.source, self.target)
        cache = self.target / "__pycache__"
        cache.mkdir()
        (cache / "local.pyc").write_bytes(b"cache")
        self.assertEqual(skill.differences(self.source, self.target), [])

    def test_rejects_symlink_without_touching_target(self):
        (self.source / "external").symlink_to(self.root)
        with self.assertRaises(ValueError):
            skill.install(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_rejects_overlapping_paths(self):
        for target in (self.source, self.source / "child", self.source.parent):
            with self.subTest(target=target), self.assertRaises(ValueError):
                skill.install(self.source, target, update=True)

    def test_missing_source_does_not_replace_installed_copy(self):
        skill.install(self.source, self.target)
        (self.source / "SKILL.md").unlink()
        with self.assertRaises(ValueError):
            skill.install(self.source, self.target, update=True)
        self.assertEqual((self.target / "SKILL.md").read_text(), "current")

    def test_failed_replacement_restores_previous_copy(self):
        skill.install(self.source, self.target)
        (self.source / "SKILL.md").write_text("next")
        rename = Path.rename

        def fail_staging(path, target):
            if path.name.startswith(".skill-install-"):
                raise OSError("replacement failed")
            return rename(path, target)

        with patch.object(Path, "rename", fail_staging), self.assertRaises(OSError):
            skill.install(self.source, self.target, update=True)
        self.assertEqual((self.target / "SKILL.md").read_text(), "current")


if __name__ == "__main__":
    unittest.main()

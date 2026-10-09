"""Distribution and bundled-tool checks for the standalone final-editor skill.

These tests check the published package rather than the skill's behaviour: the
required resources are present, every relative Markdown link resolves inside the
repository, the skill metadata is readable, no personal or cached files ship with
it, and the two bundled Python tools run end to end on a synthetic manuscript.
The synthetic drafts are written to temporary directories and never committed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCANNER = SCRIPTS / "scan_manuscript_style.py"
DISPOSITIONS = SCRIPTS / "check_scan_dispositions.py"
SKILL_NAME = "academic-manuscript-final-editor"
REFERENCES = ("defensive-rigor-signals.md", "editorial-style-rules.md", "readability-examples.md")
EXPECTED_ROOT = {
    ".github", ".gitignore", "LICENSE", "README.en.md", "README.md",
    "SKILL.md", "agents", "references", "scripts", "tests",
}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BANNED_NAMES = {"__pycache__", "node_modules", ".venv", "venv", ".DS_Store"}
BANNED_SUFFIXES = (".pyc", ".pyo", ".log", ".zip", ".tar", ".tmp", ".bak")
# Built from parts so that this file does not match its own scan.
PERSONAL_MARKERS = tuple("/" + part for part in ("Users/", "home/")) + ("C:\\Users\\",)
TEXT_SUFFIXES = (".md", ".py", ".yaml", ".yml", ".txt", ".json", ".toml", ".cfg")

# The first draft reaches the high-severity internal-workflow rule and the
# medium-severity version-migration rule; the second draft is clean.
DRAFT = ("# Results\n\n"
         "The stage receipt was saved for this revision round.\n\n"
         "The old version of the summary table is shown above.\n")
CLEAN_DRAFT = "# Results\n\nThe catch estimate is 1200 tonnes.\n"


def run(script, *arguments):
    return subprocess.run([sys.executable, "-B", str(script), *arguments],
                          capture_output=True, text=True, encoding="utf-8")


def published_files():
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:index]
    return []


def frontmatter_value(block, key):
    """Return a scalar or folded frontmatter value, joined for multi-line blocks."""
    for index, line in enumerate(block):
        if not line.startswith(key + ":"):
            continue
        value = line.split(":", 1)[1].strip()
        if value and value not in (">", ">-", "|", "|-"):
            return value
        parts = []
        for follow in block[index + 1:]:
            if follow.strip() and not follow.startswith((" ", "\t")):
                break
            parts.append(follow.strip())
        return " ".join(part for part in parts if part).strip()
    return None


def load_dispositions_helper():
    spec = importlib.util.spec_from_file_location("bundled_check_scan_dispositions", DISPOSITIONS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DistributionTests(unittest.TestCase):
    def test_required_resources_are_present(self):
        for relative in ("SKILL.md", "README.md", "README.en.md", "LICENSE",
                         "agents/openai.yaml", "scripts/scan_manuscript_style.py",
                         "scripts/check_scan_dispositions.py"):
            self.assertTrue((ROOT / relative).is_file(), relative)
        for name in REFERENCES:
            self.assertTrue((ROOT / "references" / name).is_file(), name)

    def test_root_layout_is_the_skill_folder(self):
        entries = {path.name for path in ROOT.iterdir() if path.name != ".git"}
        self.assertEqual(entries, EXPECTED_ROOT)

    def test_reference_documents_are_linked_from_the_skill(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for name in REFERENCES:
            self.assertIn(f"references/{name}", skill, name)

    def test_relative_links_resolve_inside_the_repository(self):
        checked = 0
        for path in published_files():
            if path.suffix.lower() != ".md":
                continue
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith(("#", "mailto:")):
                    continue
                checked += 1
                resolved = (path.parent / target.split("#")[0]).resolve()
                self.assertTrue(resolved.exists(), f"{path}: missing {target}")
                self.assertTrue(resolved.is_relative_to(ROOT), f"{path}: escapes repository: {target}")
        self.assertGreater(checked, 0, "no relative links were checked")

    def test_skill_metadata_is_readable(self):
        block = frontmatter((ROOT / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue(block, "SKILL.md frontmatter is missing")
        self.assertEqual(frontmatter_value(block, "name"), SKILL_NAME)
        self.assertTrue(frontmatter_value(block, "description"))
        agent = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("display_name:", agent)
        self.assertIn("default_prompt:", agent)
        self.assertIn("allow_implicit_invocation: true", agent)
        self.assertIn(SKILL_NAME, agent)

    def test_no_personal_or_cached_files_ship(self):
        for path in published_files():
            self.assertNotIn(path.name, BANNED_NAMES, str(path))
            self.assertNotIn(path.suffix.lower(), BANNED_SUFFIXES, str(path))
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in PERSONAL_MARKERS:
                self.assertNotIn(marker, text, f"{path} contains a personal path")

    def test_license_is_present_and_complete(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Permission is hereby granted", license_text)


class BundledToolTests(unittest.TestCase):
    def scan(self, directory, text, *extra):
        draft = Path(directory) / "draft.md"
        draft.write_text(text, encoding="utf-8")
        result = run(SCANNER, "--json", *extra, str(draft))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), draft

    def test_scanner_locates_candidates_without_touching_the_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            report, draft = self.scan(directory, DRAFT)
            self.assertGreater(report["finding_count"], 0)
            self.assertEqual(report["finding_count"], len(report["findings"]))
            for finding in report["findings"]:
                self.assertTrue(finding["finding_id"].startswith("fnd-"), finding)
                self.assertTrue(finding["rule_id"])
                self.assertTrue(finding["evidence"])
            for entry in report["files"]:
                self.assertTrue(entry["unchanged"], entry)
                self.assertEqual(entry["sha256_before"], entry["sha256_after"])
                self.assertEqual(entry["coverage_status"], "complete-for-supported-text")
            self.assertEqual(draft.read_text(encoding="utf-8"), DRAFT)

    def test_scanner_exit_code_follows_the_severity_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / "draft.md"
            draft.write_text(DRAFT, encoding="utf-8")
            self.assertEqual(run(SCANNER, str(draft)).returncode, 0)
            self.assertEqual(run(SCANNER, "--fail-on", "high", str(draft)).returncode, 1)
            clean = Path(directory) / "clean.md"
            clean.write_text(CLEAN_DRAFT, encoding="utf-8")
            self.assertEqual(run(SCANNER, "--fail-on", "high", str(clean)).returncode, 0)

    def test_disposition_template_covers_every_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            report, _ = self.scan(directory, DRAFT)
            scan_path = Path(directory) / "scan.json"
            scan_path.write_text(json.dumps(report), encoding="utf-8")
            template = Path(directory) / "dispositions.json"
            result = run(DISPOSITIONS, "--scan", str(scan_path), "--template-out", str(template))
            self.assertEqual(result.returncode, 0, result.stderr)
            skeleton = json.loads(template.read_text(encoding="utf-8"))
            self.assertEqual(skeleton["status"], "pass")
            self.assertEqual(skeleton["finding_count"], len(report["findings"]))
            self.assertEqual([item["finding_id"] for item in skeleton["dispositions"]],
                             [item["finding_id"] for item in report["findings"]])

    def test_dispositions_self_check_blocks_incomplete_and_passes_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            report, _ = self.scan(directory, DRAFT)
            scan_path = Path(directory) / "scan.json"
            scan_path.write_text(json.dumps(report), encoding="utf-8")
            template = Path(directory) / "dispositions.json"
            self.assertEqual(run(DISPOSITIONS, "--scan", str(scan_path),
                                 "--template-out", str(template)).returncode, 0)

            unfilled = run(DISPOSITIONS, "--scan", str(scan_path), "--dispositions", str(template))
            self.assertEqual(unfilled.returncode, 1)
            self.assertIn("evidence_refs must be non-empty", unfilled.stdout)

            filled = json.loads(template.read_text(encoding="utf-8"))
            for index, item in enumerate(filled["dispositions"]):
                item["decision"] = "reject" if index else "accept"
                item["evidence_refs"] = ["draft.md:1"]
            complete = Path(directory) / "complete.json"
            complete.write_text(json.dumps(filled), encoding="utf-8")
            passed = run(DISPOSITIONS, "--scan", str(scan_path), "--dispositions", str(complete))
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertIn("pass", passed.stdout)

            missing_evidence = json.loads(complete.read_text(encoding="utf-8"))
            missing_evidence["dispositions"][0]["evidence_refs"] = []
            broken = Path(directory) / "broken.json"
            broken.write_text(json.dumps(missing_evidence), encoding="utf-8")
            rejected = run(DISPOSITIONS, "--scan", str(scan_path), "--dispositions", str(broken))
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("evidence_refs must be non-empty", rejected.stdout)

    def test_dispositions_reject_a_report_from_another_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            first, _ = self.scan(directory, DRAFT)
            scan_path = Path(directory) / "scan.json"
            scan_path.write_text(json.dumps(first), encoding="utf-8")
            template = Path(directory) / "dispositions.json"
            self.assertEqual(run(DISPOSITIONS, "--scan", str(scan_path),
                                 "--template-out", str(template)).returncode, 0)
            filled = json.loads(template.read_text(encoding="utf-8"))
            for item in filled["dispositions"]:
                item["decision"] = "reject"
                item["evidence_refs"] = ["draft.md:1"]
            rebound = Path(directory) / "rebound.json"
            rebound.write_text(json.dumps(filled), encoding="utf-8")
            # A second scan that still carries findings, so the checker reaches the
            # hash-binding rule instead of the legacy-report rule.
            other = Path(directory) / "other.md"
            other.write_text(DRAFT.replace("The old version", "The previous version"), encoding="utf-8")
            other_scan = Path(directory) / "other_scan.json"
            other_report = run(SCANNER, "--json", str(other))
            self.assertEqual(other_report.returncode, 0, other_report.stderr)
            other_scan.write_text(other_report.stdout, encoding="utf-8")
            result = run(DISPOSITIONS, "--scan", str(other_scan), "--dispositions", str(rebound))
            self.assertEqual(result.returncode, 1)
            self.assertIn("scanner_report_sha256 must bind this scanner report", result.stdout)

    def test_finding_id_contract_matches_the_dispositions_helper(self):
        helper = load_dispositions_helper()
        with tempfile.TemporaryDirectory() as directory:
            report, _ = self.scan(directory, DRAFT)
            for finding in report["findings"]:
                self.assertEqual(helper.finding_id(finding), finding["finding_id"], finding)


if __name__ == "__main__":
    unittest.main()

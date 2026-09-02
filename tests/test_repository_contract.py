import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools import repository_contract


def write_candidate(root: Path, *, manifest: dict, files: dict[str, bytes]) -> None:
    (root / "factory-build-manifest.json").write_text(json.dumps(manifest))
    for name, data in files.items():
        path = root / "x86_64" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def config_for(root: Path, names: list[str]) -> Path:
    path = root / "upstream-sources.json"
    path.write_text(json.dumps({"packages": [{"name": name} for name in names]}))
    return path


class RepositoryContractTests(unittest.TestCase):
    def test_complete_candidate_passes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repository"
            repo.mkdir()
            payload = b"rpm"
            sha = repository_contract.hashlib.sha256(payload).hexdigest()
            write_candidate(
                repo,
                manifest={"packages": {"demo": {"build_key": "sha256:x", "outputs": [
                    {"file": "x86_64/demo-1.rpm", "sha256": sha}]}}},
                files={"demo-1.rpm": payload},
            )
            self.assertEqual(repository_contract.check(repo, config_for(root, ["demo"])), [])

    def test_package_absent_from_the_candidate_is_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repository"
            repo.mkdir()
            write_candidate(repo, manifest={"packages": {}}, files={})
            problems = repository_contract.check(repo, config_for(root, ["demo"]))
            self.assertEqual(len(problems), 1)
            self.assertIn("does not carry it", problems[0])

    def test_recorded_file_missing_from_disk_is_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repository"
            repo.mkdir()
            write_candidate(
                repo,
                manifest={"packages": {"demo": {"build_key": "sha256:x", "outputs": [
                    {"file": "x86_64/demo-1.rpm", "sha256": "0" * 64}]}}},
                files={},
            )
            problems = repository_contract.check(repo, config_for(root, ["demo"]))
            self.assertIn("missing from the repository", problems[0])

    def test_corrupt_file_is_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repository"
            repo.mkdir()
            write_candidate(
                repo,
                manifest={"packages": {"demo": {"build_key": "sha256:x", "outputs": [
                    {"file": "x86_64/demo-1.rpm", "sha256": "0" * 64}]}}},
                files={"demo-1.rpm": b"not what was recorded"},
            )
            problems = repository_contract.check(repo, config_for(root, ["demo"]))
            self.assertIn("does not match its recorded checksum", problems[0])
            # Existence alone is a weaker promise, and the flag says so.
            self.assertEqual(
                repository_contract.check(repo, config_for(root, ["demo"]), verify_digests=False),
                [],
            )

    def test_manifest_entry_without_outputs_is_reported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repository"
            repo.mkdir()
            write_candidate(
                repo,
                manifest={"packages": {"demo": {"build_key": "sha256:x", "outputs": []}}},
                files={},
            )
            problems = repository_contract.check(repo, config_for(root, ["demo"]))
            self.assertIn("no RPM outputs", problems[0])


if __name__ == "__main__":
    unittest.main()

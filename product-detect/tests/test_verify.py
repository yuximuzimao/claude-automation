import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import verify


class VerifyDatasetResolutionTest(unittest.TestCase):
    def test_resolve_dataset_dir_prefers_explicit_dataset_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            resolved = verify.resolve_dataset_dir(
                project_root=root,
                brand="kgos",
                dataset="kgos_business_val",
                dataset_dir=None,
            )

            self.assertEqual(resolved, root / "datasets" / "kgos_business_val")

    def test_resolve_dataset_dir_prefers_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "custom_dataset"

            resolved = verify.resolve_dataset_dir(
                project_root=Path("/unused"),
                brand="kgos",
                dataset=None,
                dataset_dir=explicit,
            )

            self.assertEqual(resolved, explicit)


if __name__ == "__main__":
    unittest.main()

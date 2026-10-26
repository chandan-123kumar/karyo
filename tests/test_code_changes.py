import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import code_changes


class CodeChangeTests(unittest.TestCase):
    def test_apply_patch_checks_before_applying(self):
        results = [SimpleNamespace(returncode=0, stdout="", stderr="") for _ in range(2)]
        with patch.object(code_changes, "_workspace_is_repo_root", return_value=True), \
                patch.object(code_changes, "_git", side_effect=results) as git:
            result = code_changes.apply_patch("diff --git a/a b/a\n")
        self.assertTrue(result["ok"])
        self.assertEqual(git.call_args_list[0].args[:2], ("apply", "--check"))
        self.assertEqual(git.call_args_list[1].args[:1], ("apply",))

    def test_rejected_patch_is_not_applied(self):
        rejected = SimpleNamespace(returncode=1, stdout="", stderr="does not apply")
        with patch.object(code_changes, "_workspace_is_repo_root", return_value=True), \
                patch.object(code_changes, "_git", return_value=rejected) as git:
            result = code_changes.apply_patch("bad patch")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "patch_rejected")
        git.assert_called_once()

    def test_show_diff_includes_untracked_file_patch(self):
        responses = [
            SimpleNamespace(returncode=0, stdout=" M file.py\0?? new.py\0", stderr=""),
            SimpleNamespace(returncode=0, stdout="tracked diff", stderr=""),
            SimpleNamespace(returncode=1, stdout="new file diff", stderr=""),
        ]
        with patch.object(code_changes, "_workspace_is_repo_root", return_value=True), \
                patch.object(code_changes, "_git", side_effect=responses):
            result = code_changes.show_diff()
        self.assertEqual(result["changed_files"], ["file.py", "new.py"])
        self.assertEqual(result["diff"], "tracked diffnew file diff")


if __name__ == "__main__":
    unittest.main()

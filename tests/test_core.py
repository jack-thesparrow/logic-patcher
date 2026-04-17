import os
import re
import shutil
import tempfile
import unittest

from logic_patcher.core import PATTERN, process_folder


def make_logic_bytes(name_roll: str, suffix: bytes = b"sr") -> bytes:
    content = name_roll.encode()
    return b"\x00" + bytes([len(content)]) + content + suffix + b"\x00"


class TestPattern(unittest.TestCase):
    def test_matches_bt_roll_with_sr(self):
        data = make_logic_bytes("Jane BT21CS001", b"sr")
        self.assertTrue(re.search(PATTERN, data))

    def test_matches_bt_roll_with_q(self):
        data = make_logic_bytes("Jane BT21CS001", b"q")
        self.assertTrue(re.search(PATTERN, data))

    def test_matches_bt_roll_with_xsr(self):
        data = make_logic_bytes("Jane BT21CS001", b"xsr")
        self.assertTrue(re.search(PATTERN, data))

    def test_no_match_on_plain_text(self):
        self.assertIsNone(re.search(PATTERN, b"hello world"))

    def test_no_match_without_bt(self):
        data = make_logic_bytes("Jane CS21001", b"sr")
        self.assertIsNone(re.search(PATTERN, data))


class TestProcessFolder(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write(self, name, data: bytes):
        path = os.path.join(self.tmpdir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_non_logic_files_are_copied(self):
        self._write("readme.txt", b"hello")
        changed, total, out = process_folder("New BT21CS999", "BT21CS999", self.tmpdir)
        self.assertEqual(changed, 0)
        self.assertTrue(os.path.exists(os.path.join(out, "readme.txt")))

    def test_logic_file_with_no_match_is_written_unchanged(self):
        original = b"\x00\x00plain data\x00\x00"
        self._write("empty.logic", original)
        changed, total, out = process_folder("New BT21CS999", "BT21CS999", self.tmpdir)
        self.assertEqual(changed, 0)
        with open(os.path.join(out, "empty.logic"), "rb") as f:
            self.assertEqual(f.read(), original)

    def test_logic_file_with_match_is_replaced(self):
        self._write("exam.logic", make_logic_bytes("Old Name BT21CS001", b"sr"))
        changed, total, out = process_folder("New Name BT99ZZ999", "BT99ZZ999", self.tmpdir)
        self.assertEqual(changed, 1)
        self.assertEqual(total, 1)
        with open(os.path.join(out, "exam.logic"), "rb") as f:
            result = f.read()
        self.assertIn(b"New Name BT99ZZ999", result)
        self.assertNotIn(b"Old Name", result)

    def test_replaced_output_excluded_from_walk(self):
        pre_out = os.path.join(self.tmpdir, "replaced_output")
        os.makedirs(pre_out, exist_ok=True)
        with open(os.path.join(pre_out, "stale.logic"), "wb") as f:
            f.write(b"old data")
        changed, total, out = process_folder("X BT21CS001", "BT21CS001", self.tmpdir)
        self.assertFalse(os.path.isdir(os.path.join(out, "replaced_output")))

    def test_progress_callback_called(self):
        self._write("a.txt", b"data")
        self._write("b.txt", b"data")
        calls = []
        process_folder("X BT21CS001", "BT21CS001", self.tmpdir,
                       progress_callback=lambda c, t: calls.append((c, t)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1][0], calls[-1][1])

    def test_output_folder_is_inside_source(self):
        _, _, out = process_folder("X BT21CS001", "BT21CS001", self.tmpdir)
        self.assertTrue(out.startswith(self.tmpdir))
        self.assertTrue(os.path.isdir(out))


if __name__ == "__main__":
    unittest.main()

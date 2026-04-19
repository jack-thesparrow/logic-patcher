import os
import shutil
import tempfile
import unittest

from logic_patcher.core import (
    ANCHOR, _read_student_string, _patch, process_folder, process_files
)


def make_logic_bytes(name_roll: str) -> bytes:
    encoded = name_roll.encode('utf-8')
    length = len(encoded)
    payload = ANCHOR + b'\x74' + length.to_bytes(2, 'big') + encoded
    return b'\x00' * 16 + payload + b'\x00' * 8


class TestAnchorParsing(unittest.TestCase):

    def test_finds_anchor_and_reads_string(self):
        data = make_logic_bytes("Jane BT21CS001")
        raw, tag_off = _read_student_string(data)
        self.assertEqual(raw, "Jane BT21CS001")
        self.assertIsNotNone(tag_off)

    def test_returns_none_when_anchor_missing(self):
        raw, tag_off = _read_student_string(b"no anchor here")
        self.assertIsNone(raw)
        self.assertIsNone(tag_off)

    def test_returns_none_when_tag_byte_wrong(self):
        encoded = b"Jane BT21CS001"
        data = ANCHOR + b'\x75' + len(encoded).to_bytes(2, 'big') + encoded
        raw, tag_off = _read_student_string(data)
        self.assertIsNone(raw)

    def test_patch_overwrites_string_and_updates_length(self):
        old_str = "Old Name BT21CS001"
        new_str = "New Name BT99ZZ999"
        data = make_logic_bytes(old_str)
        _, tag_off = _read_student_string(data)
        patched = _patch(data, tag_off, old_str, new_str)
        self.assertIsNotNone(patched)
        raw2, _ = _read_student_string(patched)
        self.assertEqual(raw2, new_str)

    def test_patch_returns_none_on_content_mismatch(self):
        data = make_logic_bytes("Correct BT21CS001")
        _, tag_off = _read_student_string(data)
        result = _patch(data, tag_off, "Wrong String", "New BT99ZZ999")
        self.assertIsNone(result)

    def test_patch_handles_longer_replacement(self):
        old_str = "Jo BT21CS001"
        new_str = "Bartholomew Fitzgerald BT99ZZ999"
        data = make_logic_bytes(old_str)
        _, tag_off = _read_student_string(data)
        patched = _patch(data, tag_off, old_str, new_str)
        self.assertIsNotNone(patched)
        raw2, _ = _read_student_string(patched)
        self.assertEqual(raw2, new_str)

    def test_patch_handles_shorter_replacement(self):
        old_str = "Bartholomew Fitzgerald BT99ZZ999"
        new_str = "Jo BT21CS001"
        data = make_logic_bytes(old_str)
        _, tag_off = _read_student_string(data)
        patched = _patch(data, tag_off, old_str, new_str)
        self.assertIsNotNone(patched)
        raw2, _ = _read_student_string(patched)
        self.assertEqual(raw2, new_str)


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

    def test_non_logic_files_are_ignored(self):
        self._write("readme.txt", b"hello")
        changed, total, out = process_folder("New Name", "BT21CS999", self.tmpdir)
        self.assertEqual(changed, 0)
        self.assertFalse(os.path.exists(os.path.join(out, "readme.txt")))

    def test_logic_file_without_anchor_is_written_unchanged(self):
        original = b"\x00\x00plain data\x00\x00"
        self._write("empty.logic", original)
        changed, total, out = process_folder("New Name", "BT21CS999", self.tmpdir)
        self.assertEqual(changed, 0)
        with open(os.path.join(out, "empty.logic"), "rb") as f:
            self.assertEqual(f.read(), original)

    def test_logic_file_with_anchor_is_replaced(self):
        self._write("exam.logic", make_logic_bytes("Old Name BT21CS001"))
        changed, total, out = process_folder("New Name", "BT99ZZ999", self.tmpdir)
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
        process_folder("X", "BT21CS001", self.tmpdir)
        out = os.path.join(self.tmpdir, "replaced_output")
        self.assertFalse(os.path.isdir(os.path.join(out, "replaced_output")))

    def test_progress_callback_called_once_per_logic_file(self):
        self._write("a.logic", make_logic_bytes("Old BT21CS001"))
        self._write("b.logic", make_logic_bytes("Old BT21CS001"))
        self._write("readme.txt", b"ignored")
        calls = []
        process_folder("X", "BT21CS001", self.tmpdir,
                       progress_callback=lambda c, t: calls.append((c, t)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1][0], calls[-1][1])

    def test_output_folder_is_inside_source(self):
        _, _, out = process_folder("X", "BT21CS001", self.tmpdir)
        self.assertTrue(out.startswith(self.tmpdir))
        self.assertTrue(os.path.isdir(out))

    def test_length_field_updated_after_replacement(self):
        self._write("exam.logic", make_logic_bytes("Old BT21CS001"))
        _, _, out = process_folder("Short", "BT99ZZ999", self.tmpdir)
        with open(os.path.join(out, "exam.logic"), "rb") as f:
            result = f.read()
        new_str = "Short BT99ZZ999"
        expected_length = len(new_str.encode()).to_bytes(2, 'big')
        self.assertIn(expected_length + new_str.encode(), result)

    def test_replacement_when_new_string_longer_than_old(self):
        old_str = "Jo BT21CS001"
        new_name, new_roll = "Bartholomew", "BT99ZZ999"
        new_str = f"{new_name} {new_roll}"
        self._write("exam.logic", make_logic_bytes(old_str))
        _, _, out = process_folder(new_name, new_roll, self.tmpdir)
        with open(os.path.join(out, "exam.logic"), "rb") as f:
            result = f.read()
        expected_length = len(new_str.encode()).to_bytes(2, 'big')
        self.assertIn(expected_length + new_str.encode(), result)
        old_length = len(old_str.encode()).to_bytes(2, 'big')
        self.assertNotIn(old_length + old_str.encode(), result)

    def test_raises_valueerror_if_name_roll_exceeds_65535_bytes(self):
        long_name = "A" * 60000
        long_roll = "B" * 6000
        with self.assertRaises(ValueError) as ctx:
            process_folder(long_name, long_roll, self.tmpdir)
        self.assertIn("65535", str(ctx.exception))


class TestProcessFiles(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.out_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        shutil.rmtree(self.out_dir)

    def _write(self, name, data: bytes):
        path = os.path.join(self.tmpdir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_patches_selected_logic_file(self):
        p = self._write("exam.logic", make_logic_bytes("Old Name BT21CS001"))
        changed, total, out = process_files("New Name", "BT99ZZ999", [p], self.out_dir)
        self.assertEqual(changed, 1)
        with open(os.path.join(out, "exam.logic"), "rb") as f:
            result = f.read()
        self.assertIn(b"New Name BT99ZZ999", result)

    def test_non_logic_paths_are_skipped(self):
        p = self._write("data.txt", b"irrelevant")
        changed, total, out = process_files("New Name", "BT99ZZ999", [p], self.out_dir)
        self.assertEqual(changed, 0)
        self.assertEqual(total, 0)

    def test_progress_callback_called_for_each_logic_file(self):
        p1 = self._write("a.logic", make_logic_bytes("Name BT21CS001"))
        p2 = self._write("b.logic", make_logic_bytes("Other BT21CS002"))
        calls = []
        process_files("X", "BT21CS001", [p1, p2], self.out_dir,
                      progress_callback=lambda c, t: calls.append((c, t)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1], (2, 2))

    def test_raises_valueerror_if_name_roll_exceeds_65535_bytes(self):
        with self.assertRaises(ValueError):
            process_files("A" * 60000, "B" * 6000, [], self.out_dir)


if __name__ == "__main__":
    unittest.main()

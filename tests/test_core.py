import os
import re
import shutil
import struct
import tempfile
import unittest
import warnings

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

    def test_matches_81_byte_string(self):
        # Strings of 81+ bytes were silently ignored by the old pattern because the
        # length-byte range was [\x05-\x50] (max 80). New range [\x05-\xff] must match.
        name_roll = "A" * 72 + "BT21CS001"  # 72 + 9 = 81 bytes
        data = make_logic_bytes(name_roll, b"sr")
        self.assertEqual(data[1], 81)
        self.assertIsNotNone(re.search(PATTERN, data))

    def test_no_match_below_minimum_length(self):
        # Length bytes 0x00-0x04 are below the lower bound and must not match.
        short = "BT1"  # 3 bytes
        data = make_logic_bytes(short, b"sr")
        self.assertIsNone(re.search(PATTERN, data))

    def test_matches_255_byte_string(self):
        # 255 is the maximum encodable with a zero high byte (\x00\xff header).
        name_roll = "A" * 246 + "BT21CS001"  # 246 + 9 = 255 bytes
        data = make_logic_bytes(name_roll, b"sr")
        self.assertEqual(data[1], 255)
        self.assertIsNotNone(re.search(PATTERN, data))


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

    def test_length_byte_updated_after_replacement(self):
        # The 2-byte Java writeUTF header must reflect the NEW string length, not the old one.
        self._write("exam.logic", make_logic_bytes("Old BT21CS001", b"sr"))
        _, _, out = process_folder("Short", "BT99ZZ999", self.tmpdir)
        with open(os.path.join(out, "exam.logic"), "rb") as f:
            result = f.read()
        new_str = "Short BT99ZZ999"
        expected_header = struct.pack(">H", len(new_str.encode()))
        self.assertIn(expected_header + new_str.encode(), result)
        old_header = struct.pack(">H", len("Old BT21CS001".encode()))
        self.assertNotIn(old_header + b"Old", result)

    def test_replacement_when_new_string_longer_than_old(self):
        # When the new name+roll is longer than the old, the length byte must grow.
        old_str = "Jo BT21CS001"
        new_name, new_roll = "Bartholomew", "BT99ZZ999"
        new_str = f"{new_name} {new_roll}"
        self._write("exam.logic", make_logic_bytes(old_str, b"sr"))
        _, _, out = process_folder(new_name, new_roll, self.tmpdir)
        with open(os.path.join(out, "exam.logic"), "rb") as f:
            result = f.read()
        expected_header = struct.pack(">H", len(new_str.encode()))
        self.assertIn(expected_header + new_str.encode(), result)
        self.assertNotIn(struct.pack(">H", len(old_str.encode())), result)

    def test_raises_valueerror_if_name_roll_exceeds_65535_bytes(self):
        # Java writeUTF cannot encode strings longer than 65535 bytes.
        long_name = "A" * 60000
        long_roll = "B" * 6000  # combined = 66001 bytes > 65535
        with self.assertRaises(ValueError) as ctx:
            process_folder(long_name, long_roll, self.tmpdir)
        self.assertIn("65535", str(ctx.exception))

    def test_warns_if_name_roll_exceeds_255_bytes(self):
        # Strings between 256 and 65535 bytes are valid writeUTF but will not be re-matched
        # by PATTERN on a second run (high byte != \x00). A UserWarning must be issued.
        medium_name = "A" * 200
        medium_roll = "B" * 60  # combined = 261 bytes > 255
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            process_folder(medium_name, medium_roll, self.tmpdir)
        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        self.assertEqual(len(user_warnings), 1)
        self.assertIn("255", str(user_warnings[0].message))


if __name__ == "__main__":
    unittest.main()

import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('nsight_doctor','/mnt/data/nteam_nsight_report_doctor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class NsightDoctorTest(unittest.TestCase):
    def test_60_synthetic_fixtures(self):
        extensions = ['.nsys-rep', '.ncu-rep', '.ncu-repz', '.sqlite', '.qdstrm', '.txt']
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            checked = 0
            for i in range(60):
                ext = extensions[i % len(extensions)]
                path = root / f'report_case_{i:02d}{ext}'
                mode = i // len(extensions)   # ten modes
                if mode == 0:
                    # Missing
                    ok, result = m.inspection(path)
                    self.assertFalse(ok, result)
                elif mode == 1:
                    # Empty
                    path.touch()
                    ok, result = m.inspection(path)
                    self.assertFalse(ok, result)
                elif mode == 2:
                    # Valid or recognizable payload
                    if ext == '.sqlite':
                        con = sqlite3.connect(path)
                        con.execute('CREATE TABLE t (id INTEGER)')
                        con.commit(); con.close()
                    else:
                        path.write_bytes(b'example report placeholder')
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext != '.txt', result)
                elif mode == 3:
                    # Bad SQLite header; otherwise recognizable report type
                    path.write_bytes(b'no sqlite signature 00000000000000')
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext not in ('.sqlite', '.txt'), result)
                elif mode == 4:
                    # File with spaces in its parent path
                    spaced = root / 'path with spaces'; spaced.mkdir(exist_ok=True)
                    path = spaced / path.name
                    path.write_bytes(b'x' * 4096)
                    if ext == '.sqlite':
                        path.unlink()
                        con = sqlite3.connect(path)
                        con.execute('CREATE TABLE t(x)')
                        con.close()
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext != '.txt', result)
                elif mode == 5:
                    # Long names
                    path = root / ('long_report_' + 'a' * 100 + ext)
                    path.write_bytes(b'hello')
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext not in ('.sqlite', '.txt'), result)
                elif mode == 6:
                    # Subdirectory path
                    nested = root / 'nested'; nested.mkdir(exist_ok=True)
                    path = nested / path.name
                    path.write_bytes(b'a' * 2)
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext not in ('.sqlite', '.txt'), result)
                elif mode == 7:
                    # Directory mistakenly named a report
                    path.mkdir()
                    ok, result = m.inspection(path)
                    self.assertFalse(ok, result)
                elif mode == 8:
                    # Mixed-case extension (case-insensitive detection)
                    path = root / f'report_upper_{i:02d}{ext.upper()}'
                    path.write_bytes(b'abc')
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext not in ('.sqlite', '.txt'), result)
                elif mode == 9:
                    # File with trailing unexpected bytes, still recognizable extension
                    path.write_bytes(b'example report signature' + b'?' * 200)
                    ok, result = m.inspection(path)
                    self.assertEqual(ok, ext not in ('.sqlite', '.txt'), result)
                self.assertEqual(m.classify(path), ext if ext != '.txt' else 'unknown')
                checked += 1
            self.assertEqual(checked, 60)
            print(f'PASS: {checked} distinct synthetic file/path diagnosis scenarios')

if __name__ == '__main__':
    unittest.main(verbosity=2)

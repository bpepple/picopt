"""Test handling files."""
from unittest import TestCase
from pathlib import Path

from picopt import files


class TestCleanupAterOptimise(TestCase):

    TEST_FN_OLD = '/tmp/TEST_FILE_OLD.{}'
    TEST_FN_NEW = '/tmp/TEST_FILE_NEW.{}'

    @staticmethod
    def create_file(fn_template, ext, num_chars):
        filename = fn_template.format(ext)
        with open(filename, 'w') as test_file:
            test_file.write('x' * num_chars)
        return filename

    @classmethod
    def cleanup_aux(cls, old_size, new_size, old_format, new_format):
        fn_old = cls.create_file(cls.TEST_FN_OLD, old_format, old_size)
        fn_new = cls.create_file(cls.TEST_FN_NEW, new_format, new_size)
        res = files._cleanup_after_optimize_aux(fn_old, fn_new,
                                                old_format, new_format)
        Path(res[0]).unlink()
        return res

    def test_small_big(self):
        old_size = 32
        new_size = 40
        old_format = 'png'
        new_format = 'png'
        path, b_in, b_out = self.cleanup_aux(old_size, new_size,
                                             old_format, new_format)
        self.assertTrue(path.suffix == '.'+old_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)

    def test_big_small(self):
        old_size = 44
        new_size = 4
        old_format = 'bmp'
        new_format = 'png'
        path, b_in, b_out = self.cleanup_aux(old_size, new_size,
                                             old_format, new_format)
        self.assertTrue(path.suffix == '.'+new_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(new_size, b_out)

    def test_small_small(self):
        old_size = 5
        new_size = 5
        old_format = 'bmp'
        new_format = 'png'
        path, b_in, b_out = self.cleanup_aux(old_size, new_size,
                                             old_format, new_format)
        self.assertTrue(path.suffix == '.'+old_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)

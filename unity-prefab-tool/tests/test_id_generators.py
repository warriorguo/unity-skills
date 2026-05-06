#!/usr/bin/env python3
"""Tests for Unity-legal ID generators."""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

from prefab_tool import (  # noqa: E402
    _INT64_MAX,
    _INT64_MIN,
    generate_file_id,
    generate_guid,
    parse_prefab_raw,
)


SAMPLE_PREFAB = os.path.join(HERE, "sample.prefab")


class GuidTests(unittest.TestCase):
    def test_format(self):
        for _ in range(50):
            g = generate_guid()
            self.assertEqual(len(g), 32)
            self.assertRegex(g, r"^[0-9a-f]{32}$")

    def test_uniqueness(self):
        guids = {generate_guid() for _ in range(1000)}
        self.assertEqual(len(guids), 1000)


class FileIdTests(unittest.TestCase):
    def test_int64_range(self):
        for _ in range(200):
            fid = generate_file_id(set())
            self.assertIsInstance(fid, int)
            self.assertNotEqual(fid, 0)
            self.assertGreaterEqual(fid, _INT64_MIN)
            self.assertLessEqual(fid, _INT64_MAX)

    def test_does_not_collide_with_existing(self):
        existing = {1, 100, 100000, 400000, 11400000}
        for _ in range(200):
            fid = generate_file_id(existing)
            self.assertNotIn(fid, existing)
            existing.add(fid)

    def test_does_not_collide_with_real_prefab(self):
        if not os.path.exists(SAMPLE_PREFAB):
            self.skipTest("sample.prefab missing")
        _, doc_ranges = parse_prefab_raw(SAMPLE_PREFAB)
        existing = {dr["file_id"] for dr in doc_ranges}
        self.assertGreater(len(existing), 0)
        for _ in range(50):
            fid = generate_file_id(existing)
            self.assertNotIn(fid, existing)
            existing.add(fid)


if __name__ == "__main__":
    unittest.main()

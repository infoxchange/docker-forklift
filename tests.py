"""
Tests for Forklift.
"""

import unittest
import subprocess


class TestCase(unittest.TestCase):
    """
    Base test case.
    """

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        return subprocess.call(['./forklift'] + list(args))

    def assert_forklift_success(self, *args):
        """
        Run Forklift and check the result.
        """

        self.assertEqual(0, self.run_forklift(*args))


class BasicTestCase(TestCase):
    """
    Test basic functionality.
    """

    def test_direct_run(self):
        """
        Test running a command directly.
        """

        self.assert_forklift_success('--executioner', 'direct', '/bin/true')
        self.assertNotEqual(
            0, self.run_forklift('--executioner', 'direct', '/bin/false'))

"""
Tests for argument parsing utilities.
"""

from argparse import Namespace
from collections import OrderedDict
import unittest

from forklift.arguments import convert_to_args, project_args


class ConvertToArgsTestCase(unittest.TestCase):
    """
    Test convert_to_args.
    """

    def test_convert_to_args(self):
        """
        Test convert_to_args.
        """

        conf = OrderedDict([
            ('simple', 'value'),
            ('number', 10),
            ('array', [
                'one',
                'two',
            ]),
            ('empty_array', []),
            ('nested', OrderedDict([
                ('first', 'deep'),
                ('second', 'deeper'),
            ])),
        ])

        self.assertEqual(convert_to_args(conf), [
            '--simple', 'value',
            '--number', '10',
            '--array', 'one', 'two',
            '--nested.first', 'deep',
            '--nested.second', 'deeper',
        ])


class ProjectArgsTestCase(unittest.TestCase):
    """
    Test project_args.
    """

    def test_project_args(self):
        """
        Test project_args.
        """

        args = Namespace(**{
            'one.a': '1a',
            'one.b': '1b',
            'two.c': '2c',
        })

        self.assertEqual(
            vars(project_args(args, 'one')),
            {
                'a': '1a',
                'b': '1b',
            }
        )

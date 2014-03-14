#
# Copyright 2014  Infoxchange Australia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.3

"""
Tests for utility functions.
"""

import unittest

from forklift import dict_deep_merge


class DeepMergeTestCase(unittest.TestCase):
    """
    Test dict_deep_merge.
    """

    def test_dict_deep_merge(self):
        """
        Test dict_deep_merge.
        """

        original = {
            'unchanged': 'item',
            'array': [1, 2],
            'replaced': {
                'was_a_dict': True,
            },
            'to_change': {
                'good': 'one',
                'bad': 'two',
            },
        }

        updated = {
            'added': 'item',
            'replaced': 'now a string',
            'array': [3, 4],
            'to_change': {
                'bad': 'three',
                'more': 'five',
            },
        }

        self.assertEqual(
            dict_deep_merge(original, updated),
            {
                'unchanged': 'item',
                'added': 'item',
                'array': [3, 4],
                'replaced': 'now a string',
                'to_change': {
                    'good': 'one',
                    'bad': 'three',
                    'more': 'five',
                },
            }
        )

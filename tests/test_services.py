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
# limitations under the License.

"""
Tests for services provided by Forklift.
"""

import unittest

from urllib.parse import urlparse

from forklift.services import ElasticsearchService


class ElasticsearchTestCase(unittest.TestCase):
    """
    Test Elasticsearch service.
    """

    def test_host(self):
        """
        Test host get/set.
        """

        service = ElasticsearchService(
            'index',
            'http://alpha:9200|http://beta:9200')

        self.assertEqual(service.url_array, [
            urlparse('http://alpha:9200'),
            urlparse('http://beta:9200'),
        ])
        self.assertEqual(service.host, 'alpha|beta')

        service.host = 'elsewhere'

        self.assertEqual(service.url_array, [
            urlparse('http://elsewhere:9200'),
            urlparse('http://elsewhere:9200'),
        ])
        self.assertEqual(
            service.urls,
            'http://elsewhere:9200|http://elsewhere:9200')

        service = ElasticsearchService(
            'index',
            'http://localhost:9200')

        self.assertEqual(service.url_array, [
            urlparse('http://localhost:9200'),
        ])
        self.assertEqual(service.host, 'localhost')

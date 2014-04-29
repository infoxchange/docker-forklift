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

import forklift.services


class ElasticsearchTestCase(unittest.TestCase):
    """
    Test Elasticsearch service.
    """

    def test_host(self):
        """
        Test host get/set.
        """

        service = forklift.services.ElasticsearchService(
            'index',
            'http://alpha:9200|http://beta:9200')

        self.assertEqual(service.urls, [
            urlparse('http://alpha:9200'),
            urlparse('http://beta:9200'),
        ])
        self.assertEqual(
            service.environment()['ELASTICSEARCH_URLS'],
            'http://alpha:9200|http://beta:9200'
        )
        self.assertEqual(service.host, 'alpha|beta')

        service.host = 'elsewhere'

        self.assertEqual(service.urls, [
            urlparse('http://elsewhere:9200'),
            urlparse('http://elsewhere:9200'),
        ])
        self.assertEqual(
            service.environment()['ELASTICSEARCH_URLS'],
            'http://elsewhere:9200|http://elsewhere:9200'
        )

        service = forklift.services.ElasticsearchService(
            'index',
            'http://localhost:9200')

        self.assertEqual(service.urls, [
            urlparse('http://localhost:9200'),
        ])
        self.assertEqual(service.host, 'localhost')


class MemcacheTestCase(unittest.TestCase):
    """
    Test Memcache service.
    """

    def test_host(self):
        """
        Test host get/set.
        """

        service = forklift.services.MemcacheService(
            'index',
            ['alpha', 'beta:11222'])

        self.assertEqual(service.hosts, [
            'alpha',
            'beta:11222',
        ])
        self.assertEqual(service.host, 'alpha|beta')

        service.host = 'elsewhere'

        self.assertEqual(service.hosts, [
            'elsewhere:11211',
        ])


class ServicesAPITestCase(unittest.TestCase):
    """
    Test all services match the API
    """

    def test_services_api_conformance(self):
        """
        Test services have the correct API
        """
        for cls in forklift.services.register.values():

            print(cls)

            # assert we have at least one provider
            self.assertGreaterEqual(len(cls.providers), 1)

            # assert those providers exist on the class
            for provider in cls.providers:
                assert hasattr(cls, provider)

            # assert can build a provider
            service = getattr(cls, cls.providers[0])('test-app')

            # assert we can set the host
            #
            # Only the Docker driver uses the host property, and it is
            # currently optional. However this test is useful because the
            # property is useful. If it turns out there are services for
            # which host is not useful, then this test should be changed :)
            assert hasattr(service, 'host')
            service.host = 'badger'

            assert hasattr(service, 'environment')
            assert hasattr(service, 'available')

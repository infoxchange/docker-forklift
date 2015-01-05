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
Test services API.
"""

import unittest

import forklift.services

from tests.base import docker_image_available


class ServiceTestCase(unittest.TestCase):
    """
    Generic service tests.
    """

    service_class = None

    def test_api_conformance(self):
        """
        Test that the service has the correct API.
        """

        # assert we have at least one provider
        self.assertGreaterEqual(len(self.service_class.providers), 1)

        # assert those providers exist on the class
        for provider in self.service_class.providers:
            assert hasattr(self.service_class, provider)

        # assert can build a provider
        service = getattr(self.service_class,
                          self.service_class.providers[0])('fake')

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

        # Test all attributes in allow_override exist
        for attr in service.allow_override:
            value = getattr(service, attr)
            setattr(service, attr, value)

    def test_available(self):
        """
        Test that the service provided by the image is available.
        """

        image = self.service_class.CONTAINER_IMAGE
        if image and not docker_image_available(image):
            raise unittest.SkipTest(
                "Docker image {0} is required.".format(image))

        service = self.service_class.provide('fake', transient=True)
        self.assertTrue(service.available())

        service.cleanup()


def load_tests(loader, tests, pattern):
    """
    Generate a test class for each service.
    """

    suite = unittest.TestSuite()
    for cls in forklift.services.register.values():
        test_class = type(ServiceTestCase)(
            cls.__name__ + 'TestCase',
            (ServiceTestCase,),
            {
                'service_class': cls,
            }
        )
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    return suite

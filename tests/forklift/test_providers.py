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
Test the base Service choosing from the available providers.
"""

from forklift.base import ImproperlyConfigured
from forklift.services.base import (
    ProviderNotAvailable,
    Service,
)

from tests.base import (TestCase)


class FussyService(Service):
    """
    A service with a few providers which are only sometimes available.
    """

    def __init__(self, value, application_id):
        self.application_id = application_id
        self.value = value

    providers = (
        'one',
        'two',
    )

    # An array of values deemed available
    nice = (
        'one',
        'two',
    )

    @classmethod
    def one(cls, application_id):
        """
        One nice provider.
        """
        return cls('one', application_id)

    @classmethod
    def two(cls, application_id):
        """
        Another nice provider.
        """
        return cls('two', application_id)

    def check_available(self):
        """
        Only treat nice providers as available.
        """
        if self.value in self.nice:
            return True
        else:
            raise ProviderNotAvailable()


class TestProvide(TestCase):
    """
    Test choosing an available provider.
    """

    def test_first_available(self):
        """
        The first provider tried is available.
        """
        self.assertEqual(FussyService.provide(application_id='test').value,
                         'one')

    def test_second_available(self):
        """
        One provider isn't available, the other one is.
        """
        FussyService.nice = ('two',)
        self.assertEqual(FussyService.provide(application_id='test').value,
                         'two')

    def test_none_available(self):
        """
        No providers are available.
        """
        FussyService.nice = ()
        with self.assertRaises(ImproperlyConfigured):
            FussyService.provide(application_id='test')

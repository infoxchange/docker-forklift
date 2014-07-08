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
Test the --rm and --transient flags
"""

from tests.base import docker, TestCase, TestDriver, TestForklift


def assertion_driver(func):
    """
    Create a test driver that runs func to assert test conditions
    """
    class InnerClass(TestDriver):
        run = func

    return InnerClass


def assertion_forklift_class(func):
    """
    Create a test forklift class that has only an assertion driver
    """
    class InnerClass(TestForklift):
        drivers = {'assertion_driver': assertion_driver(func)}

    return InnerClass


class TestTransient(TestCase):
    """
    Test the --transient flag
    """

    def test_transient_service(self):
        """
        Make sure that a transient service is selected
        """
        def assertions_func(driver, *_):
            """
            Make sure that the transient service is used
            """
            self.assertEqual('here_occasionally',
                             driver.services[0].provided_by)
            return 0

        self.forklift_class = assertion_forklift_class(assertions_func)
        self.assertEqual(0, self.run_forklift(
            '--driver', 'assertion_driver',
            '--service', 'test',
            '--transient',
            '--', 'fake',
        ))

    def test_non_transient_service(self):
        """
        Negative test to make sure the test_transient_service test is valid
        """
        def assertions_func(driver, *_):
            """
            Make sure that the transient service is not used
            """
            self.assertEqual('here',
                             driver.services[0].provided_by)
            return 0

        self.forklift_class = assertion_forklift_class(assertions_func)
        self.assertEqual(0, self.run_forklift(
            '--driver', 'assertion_driver',
            '--service', 'test',
            '--', 'fake',
        ))

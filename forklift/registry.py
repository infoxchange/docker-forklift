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
Helpers related to maintaining a registry of classes
"""


class Registry(dict):
    """
    A registry class, used for registering services, drivers, etc.

    This is not the registry itself. The registry itself is in
    forklift.services, forklift.drivers, etc.
    """

    def __call__(self, name):
        """
        Use registry as a decorator to register Forklift services
        """

        def inner(cls):
            """
            Decorator
            """
            self[name] = cls

            return cls

        return inner

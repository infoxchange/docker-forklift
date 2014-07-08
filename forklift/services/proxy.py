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
Proxy service.
"""

from .base import Service, port_open, register, transient_provider


@register('proxy')
class Proxy(Service):
    """
    Proxy service for the application.
    """

    allow_override = ('host', 'port')

    def __init__(self, host=None, port=None):
        self.host = host
        self.port = port

    def available(self):
        """
        Check whether the proxy is available.
        """

        if self.host:
            return port_open(self.host, self.port)
        else:
            return True

    def environment(self):
        """
        The environment to access the proxy.
        """

        if self.host:
            return {
                'HTTP_PROXY': 'http://{host}:{port}'.format(**self.__dict__),
            }
        else:
            return {}

    # pylint:disable=unused-argument
    @classmethod
    @transient_provider
    def manual(cls, application_id):
        """
        Manually-configured proxy. Will not be available unless parameters
        are overridden in configuration.
        """

        return cls()

    providers = ('manual',)

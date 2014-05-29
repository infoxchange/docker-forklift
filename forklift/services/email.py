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

from .base import Service, port_open, register


@register('email')
class Email(Service):
    """
    An MTA for the application.
    """

    allow_override = ('host', 'port')

    def __init__(self, host, port=25):
        self.host = host
        self.port = port

    def environment(self):
        """
        The environment to send email.
        """

        return {
            'EMAIL_HOST': self.host,
            'EMAIL_PORT': str(self.port),
        }

    def available(self):
        """
        Check whether the MTA is available.
        """

        return port_open(self.host, self.port)

    # pylint:disable=unused-argument
    @classmethod
    def localhost(cls, application_id):
        """
        The MTA on the local machine.
        """
        return cls(host='localhost')

    providers = ('localhost',)

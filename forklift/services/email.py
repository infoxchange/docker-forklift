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

import socket

from forklift.base import free_port
from .base import Service, register, transient_provider, try_port


@register('email')
class Email(Service):
    """
    An MTA for the application.
    """

    TEMPORARY_AVAILABILITY_ERRORS = (socket.error,)

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

    def check_available(self):
        """
        Check whether the MTA is available.
        """

        return try_port(self.host, self.port)

    # pylint:disable=unused-argument
    @classmethod
    def localhost(cls, application_id):
        """
        The MTA on the local machine.
        """
        return cls(host='localhost')

    # pylint:disable=unused-argument
    @classmethod
    @transient_provider
    def stdout(cls, application_id):
        """
        Mailer printing all the messages to the standard output of Forklift.
        """

        from forklift.services.satellite import start_satellite
        from smtpd import DebuggingServer

        port = free_port()

        def run_server():
            """
            Run the syslog server.
            """

            DebuggingServer(('0.0.0.0', port), None)
            import asyncore
            asyncore.loop()

        start_satellite(target=run_server)

        instance = cls('localhost', port)
        instance.wait_until_available()
        return instance

    providers = ('localhost', 'stdout')

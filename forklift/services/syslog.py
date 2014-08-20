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
Syslog service.
"""

import socket

from forklift.base import free_port
from .base import Service, register, transient_provider, try_port


@register('syslog')
class Syslog(Service):
    """
    Logging facility for the application.
    """

    DEFAULT_PORT = 514

    TEMPORARY_AVAILABILITY_ERRORS = (socket.error,)

    allow_override = ('host', 'port', 'proto')

    def __init__(self, host=None, port=DEFAULT_PORT, proto='udp'):
        self.host = host
        self.port = port
        self.proto = proto

    def environment(self):
        """
        The environment to provide logging.
        """

        return {
            'SYSLOG_SERVER': self.host,
            'SYSLOG_PORT': str(self.port),
            'SYSLOG_PROTO': self.proto,
        }

    def check_available(self):
        """
        Check whether syslog is available.

        If the protocol is UDP, assume it is available if any of the other
        parameters are set.
        """

        if self.host is None:
            return False

        if self.proto == 'udp':
            return True
        else:
            return try_port(self.host, self.port)

    # pylint:disable=unused-argument
    @classmethod
    def manual(cls, application_id):
        """
        Manually-configured syslog. Will not be available unless parameters
        are overridden in configuration.
        """

        return cls()

    # pylint:disable=unused-argument
    @classmethod
    @transient_provider
    def stdout(cls, application_id):
        """
        Logger printing all the messages to the standard output of Forklift.
        """

        # Adapted from https://gist.github.com/marcelom/4218010
        from forklift.services.satellite import start_satellite
        import socketserver

        class SyslogHandler(socketserver.BaseRequestHandler):
            """
            Handler outputting logging messages received to stdout.
            """
            def handle(self):
                data = self.request[0].strip().decode()
                print(data)

        port = free_port()

        def run_server():
            """
            Run the syslog server.
            """

            server = socketserver.UDPServer(('0.0.0.0', port), SyslogHandler)
            server.serve_forever()

        start_satellite(target=run_server)

        return cls('localhost', port)

    providers = ('manual', 'stdout')

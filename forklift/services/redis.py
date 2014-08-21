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
Redis service
"""

import logging
import socket
from telnetlib import Telnet

from .base import (Service,
                   ensure_container,
                   register,
                   split_host_port,
                   transient_provider)

LOGGER = logging.getLogger(__name__)


@register('redis')
class Redis(Service):
    """
    A Redis service

    This is a single Redis server.
    """

    allow_override = ('host', 'db_index')
    providers = ('localhost', 'container')

    DEFAULT_PORT = 6379

    TEMPORARY_AVAILABILITY_ERRORS = (socket.error,)

    def __init__(self,
                 host=None,
                 db_index=0):
        # FIXME: we don't support multiple redis servers yet
        self.host = host
        self.db_index = db_index

    def environment(self):
        """
        The environment to access Redis
        """

        return {
            'REDIS_HOSTS': self.host,
            'REDIS_DB_INDEX': str(self.db_index),
        }

    def check_available(self):
        """
        Check whether Redis is available
        """

        # pylint:disable=invalid-name
        nc = Telnet(*split_host_port(self.host, self.DEFAULT_PORT))

        try:
            nc.write(b'PING')
            nc.read_until(b'PONG\n',
                          timeout=1)
        finally:
            nc.close()

        return True

    # pylint:disable=unused-argument
    @classmethod
    def localhost(cls, application_id):
        """
        The default Redis provider
        """

        return cls(host='localhost:{port}'.format(port=cls.DEFAULT_PORT))

    @classmethod
    @transient_provider
    def container(cls, application_id):
        """
        Redis provided by a container
        """

        container = ensure_container(
            image='dockerfile/redis',
            port=cls.DEFAULT_PORT,
            application_id=application_id,
        )

        instance = cls(
            host='localhost:{port}'.format(port=container.port),
        )

        # pylint:disable=attribute-defined-outside-init
        instance.container_info = container
        return instance

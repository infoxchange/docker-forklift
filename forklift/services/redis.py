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
from telnetlib import Telnet

from .base import (
    register,
    URLNameDescriptor,
    URLService,
)

LOGGER = logging.getLogger(__name__)


@register('redis')
class Redis(URLService):
    """
    A Redis service

    This is a single Redis server.
    """

    allow_override = URLService.allow_override + ('db_index',)
    db_index = URLNameDescriptor()

    providers = ('localhost', 'container')

    CONTAINER_IMAGE = 'redis'

    DEFAULT_PORT = 6379

    def __init__(self, host, db_index=0):
        # FIXME: we don't support multiple redis servers yet
        super().__init__('redis://{host}/{db_index}'.format(
            host=host,
            db_index=db_index,
        ))

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
        nc = Telnet(self.host, self.port)

        try:
            nc.write(b'PING')
            nc.read_until(b'PONG\n',
                          timeout=1)
        finally:
            nc.close()

        return True

    @classmethod
    def localhost(cls, application_id):
        """
        The default Redis provider
        """

        return cls(host='localhost:{port}'.format(port=cls.DEFAULT_PORT))

    @classmethod
    def from_container(cls, application_id, container):
        """
        Redis provided by a container.
        """

        return cls(
            host='{host}:{port}'.format(**container.__dict__),
        )

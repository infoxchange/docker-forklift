#
# Copyright 2015  Infoxchange
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

from .base import (
    ProviderNotAvailable,
    URLNameDescriptor,
    URLHostInfoDescriptor,
    URLService,
    port_open,
    register,
    split_host_port,
)

LOGGER = logging.getLogger(__name__)


@register('amqp')
class RabbitMQ(URLService):
    """
    A RabbitMQ/AMQP service
    """
    CONTAINER_IMAGE = 'rabbitmq'
    DEFAULT_PORT = 5672

    hosts = URLHostInfoDescriptor(default_port=DEFAULT_PORT, joiner=tuple)
    vhost = URLNameDescriptor()

    allow_override = URLService.allow_override + ('vhost',)
    allow_override_list = URLService.allow_override_list + ('hosts',)

    providers = ('localhost', 'container')

    def environment(self):
        """Environment for AMQP"""

        return {
            'AMQP_URLS': self.url_string(),
        }

    def check_available(self):
        """Check the service is available"""
        for host in self.hosts:
            if port_open(*split_host_port(host, self.DEFAULT_PORT)):
                return True

        raise ProviderNotAvailable("RabbitMQ not available: none of the hosts "
                                   "are up")

    @classmethod
    def localhost(cls, application_id):
        """RabbitMQ on the local machine"""
        return cls(urls=('amqp://localhost:{port}/{vhost}/'.format(
            port=cls.DEFAULT_PORT,
            vhost=application_id),))

    @classmethod
    def from_container(cls, application_id, container):
        """RabbitMQ as a container"""

        return cls(urls=('amqp://guest:guest@{c.host}:{c.port}//'.format(
            c=container),))

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
Memcache service.
"""

from itertools import chain, repeat

from .base import (
    ensure_container,
    Service,
    port_open,
    register,
    split_host_port,
    transient_provider,
)


@register('memcache')
class Memcache(Service):
    """
    Memcache service for the application.
    """

    allow_override = ('key_prefix', 'host')
    allow_override_list = ('hosts',)
    providers = ('localhost', 'container')

    DEFAULT_PORT = 11211

    def __init__(self,
                 key_prefix='',
                 hosts=None):

        self.key_prefix = key_prefix
        self.hosts = hosts or []

    def environment(self):
        """
        The environment to access Memcache
        """

        return {
            'MEMCACHE_HOSTS': '|'.join(self.hosts),
            'MEMCACHE_PREFIX': self.key_prefix,
        }

    def available(self):
        """
        Check whether memcache is available

        Do this by connecting to the socket. At least one host must be up
        """

        if not self.hosts:
            return False

        for host in self.hosts:
            if port_open(*split_host_port(host, self.DEFAULT_PORT)):
                return True

        return False

    @property
    def host(self):
        """
        The (pipe separated) hosts for the Memcache service.
        """

        return '|'.join(
            split_host_port(host, self.DEFAULT_PORT)[0]
            for host in self.hosts
        )

    @host.setter
    def host(self, host):
        """
        Set the host to access Memcache at.
        """
        ports = chain(
            (
                split_host_port(h, self.DEFAULT_PORT)[1]
                for h in self.hosts
            ),
            repeat(self.DEFAULT_PORT),
        )
        self.hosts = [
            '{0}:{1}'.format(h, p)
            for h, p in zip(host.split('|'), ports)
        ]

    @classmethod
    def localhost(cls, application_id):
        """
        The default memcached provider
        """

        return cls(key_prefix=application_id,
                   hosts=['localhost:{0}'.format(cls.DEFAULT_PORT)])

    @classmethod
    @transient_provider
    def container(cls, application_id):
        """
        Memcached provided by a container.
        """

        container = ensure_container(
            image='fedora/memcached',
            port=cls.DEFAULT_PORT,
            application_id=application_id,
        )

        instance = cls(
            key_prefix=application_id,
            hosts=['localhost:{0}'.format(container.port)],
        )
        # pylint:disable=attribute-defined-outside-init
        instance.container_info = container
        return instance

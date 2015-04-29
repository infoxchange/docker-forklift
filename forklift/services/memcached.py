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

from .base import (
    ProviderNotAvailable,
    URLHostInfoDescriptor,
    URLNameDescriptor,
    URLService,
    port_open,
    register,
    split_host_port,
)


@register('memcache')
class Memcache(URLService):
    """
    Memcache service for the application.
    """

    DEFAULT_PORT = 11211

    CONTAINER_IMAGE = 'memcached'

    allow_override = URLService.allow_override + ('key_prefix',)
    allow_override_list = URLService.allow_override_list + ('hosts',)
    key_prefix = URLNameDescriptor()
    hosts = URLHostInfoDescriptor(default_port=DEFAULT_PORT, joiner=tuple)

    providers = ('localhost', 'container')

    def __init__(self,
                 key_prefix='',
                 hosts=None):

        super().__init__(
            'memcache://{host}:{port}/{key_prefix}'.format(
                host=host,
                port=port,
                key_prefix=key_prefix,
            )
            for host, port in (
                split_host_port(h, self.DEFAULT_PORT)
                for h in hosts
            )
        )

    def environment(self):
        """
        The environment to access Memcache
        """

        return {
            'MEMCACHE_HOSTS': '|'.join(self.hosts),
            'MEMCACHE_PREFIX': self.key_prefix,
        }

    def check_available(self):
        """
        Check whether memcache is available

        Do this by connecting to the socket. At least one host must be up
        """

        for host in self.hosts:
            if port_open(*split_host_port(host, self.DEFAULT_PORT)):
                return True

        raise ProviderNotAvailable("Memcached not available: none of the hosts"
                                   " are up")

    @classmethod
    def localhost(cls, application_id):
        """
        The default memcached provider
        """

        return cls(key_prefix=application_id,
                   hosts=['localhost:{0}'.format(cls.DEFAULT_PORT)])

    @classmethod
    def from_container(cls, application_id, container):
        """
        Memcached provided by a container.
        """

        return cls(
            key_prefix=application_id,
            hosts=['{host}:{port}'.format(**container.__dict__)],
        )

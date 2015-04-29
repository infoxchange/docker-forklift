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
Elasticsearch service.
"""

import json
import http.client
import logging
import os
import urllib.parse
import urllib.request

from forklift.base import open_root_owned
from .base import (cache_directory,
                   container_name_for,
                   ProviderNotAvailable,
                   pipe_split,
                   replace_part,
                   register,
                   URLNameDescriptor,
                   URLService,
                   transient_provider)

LOGGER = logging.getLogger(__name__)


try:
    # pylint:disable=undefined-variable,invalid-name
    CONNECTION_ISSUES_ERROR = ConnectionError
except NameError:
    # pylint:disable=invalid-name
    CONNECTION_ISSUES_ERROR = urllib.error.URLError


@register('elasticsearch')
class Elasticsearch(URLService):
    """
    Elasticsearch service for the application.
    """

    allow_override = URLService.allow_override + ('index_name',)

    providers = ('localhost', 'container')

    CONTAINER_IMAGE = 'elasticsearch'

    DEFAULT_PORT = 9200

    index_name = URLNameDescriptor()

    TEMPORARY_AVAILABILITY_ERRORS = \
        URLService.TEMPORARY_AVAILABILITY_ERRORS + (
            CONNECTION_ISSUES_ERROR,
            http.client.HTTPException,
            ValueError
        )
    PERMANENT_AVAILABILITY_ERRORS = (urllib.request.URLError,)

    def __init__(self, index_name, urls):
        super().__init__(tuple(
            urllib.parse.urljoin(url, index_name)
            for url in pipe_split(urls)
        ))

    def environment(self):
        """
        The environment to access Elasticsearch.
        """

        hosts = '|'.join(
            replace_part(url, path='').geturl()
            for url in self.urls
        )
        index_name = self.urls[0].path[1:]

        return {
            'ELASTICSEARCH_INDEX_NAME': index_name,
            'ELASTICSEARCH_URLS': hosts,
        }

    def check_available(self):
        """
        Check whether Elasticsearch is available at a given URL.
        """

        if not self.urls:
            return False

        for url in self.urls:
            url = replace_part(url, path='')
            es_response = urllib.request.urlopen(url.geturl())
            es_status = json.loads(es_response.read().decode())
            if es_status['status'] != 200:
                raise ProviderNotAvailable(
                    ("Provider '{}' is not yet available: HTTP response "
                     "{}\n{}").format(self.__class__.__name__,
                                      es_status['status'],
                                      es_status['error'])
                )

        return True

    @classmethod
    def localhost(cls, application_id):
        """
        The Elasticsearch environment on the local machine.
        """
        return cls(index_name=application_id,
                   urls=('http://localhost:9200',))

    @classmethod
    def ensure_container(cls, application_id, **kwargs):
        """
        Ensure an Elasticsearch container.
        """

        kwargs.setdefault('data_dir', '/data')
        return super().ensure_container(application_id, **kwargs)

    @classmethod
    def from_container(cls, application_id, container):
        """
        The Elasticsearch service provided by the container.
        """

        return cls(
            index_name=application_id,
            urls=('http://{host}:{port}'.format(**container.__dict__),),
        )

    @classmethod
    @transient_provider
    def container(cls, application_id):
        """
        Elasticsearch provided by a container.
        """

        image_name = cls.CONTAINER_IMAGE
        container_name = container_name_for(image_name, application_id)
        cache_dir = cache_directory(container_name)

        if not os.path.exists(cache_dir):
            LOGGER.debug("Creating cache directory '%s'", cache_dir)
            os.makedirs(cache_dir)

        config_path = os.path.join(cache_dir, 'elasticsearch.yml')
        LOGGER.debug("Writing ElasticSearch config to '%s'", config_path)
        with open_root_owned(config_path, 'w') as config:
            print(
                """
                path:
                    data: /data/data
                    logs: /data/log
                """,
                file=config,
            )

        return super().container(application_id)

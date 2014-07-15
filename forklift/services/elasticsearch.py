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
import socket
import urllib.request

from os.path import join

from forklift.base import open_root_owned
from .base import (cache_directory,
                   container_name_for,
                   ensure_container,
                   log_service_settings,
                   ProviderNotAvailable,
                   pipe_split,
                   register,
                   Service,
                   transient_provider)

LOGGER = logging.getLogger(__name__)


try:
    # pylint:disable=undefined-variable,invalid-name
    CONNECTION_ISSUES_ERROR = ConnectionError
except NameError:
    # pylint:disable=invalid-name
    CONNECTION_ISSUES_ERROR = urllib.error.URLError


@register('elasticsearch')
class Elasticsearch(Service):
    """
    Elasticsearch service for the application.
    """

    allow_override = ('index_name', 'host')
    allow_override_list = ('urls',)

    TEMPORARY_AVAILABILITY_ERRORS = (CONNECTION_ISSUES_ERROR,
                                     http.client.HTTPException,
                                     ProviderNotAvailable,
                                     socket.error,
                                     ValueError)
    PERMANENT_AVAILABILITY_ERRORS = (urllib.request.URLError,)

    def __init__(self, index_name, urls):
        self.index_name = index_name
        self._url_array = []
        self.urls = urls

        log_service_settings(
            LOGGER, self,
            'index_name', 'url_string'
        )

    def environment(self):
        """
        The environment to access Elasticsearch.
        """

        return {
            'ELASTICSEARCH_INDEX_NAME': self.index_name,
            'ELASTICSEARCH_URLS': self.url_string(),
        }

    def url_string(self):
        """
        All URLs joined as a string.
        """
        return '|'.join(url.geturl() for url in self.urls)

    @property
    def urls(self):
        """
        The (pipe separated) URLs to access Elasticsearch at.
        """

        return self._url_array

    @urls.setter
    def urls(self, urls):
        """
        Set the URLs to access Elasticsearch at.
        """

        self._url_array = [
            urllib.parse.urlparse(url) if isinstance(url, str) else url
            for url in pipe_split(urls)
        ]

    @property
    def host(self):
        """
        The (pipe separated) hosts for the Elasticsearch service.
        """

        return '|'.join(url.hostname for url in self._url_array)

    @host.setter
    def host(self, host):
        """
        Set the host to access Elasticsearch at.
        """

        self.urls = [
            # pylint:disable=protected-access
            url._replace(
                netloc='{host}:{port}'.format(host=host, port=url.port))
            for url in self.urls
        ]

    def check_available(self):
        """
        Check whether Elasticsearch is available at a given URL.
        """

        if not self.urls:
            return False

        for url in self.urls:
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
    @transient_provider
    def container(cls, application_id):
        """
        Elasticsearch provided by a container.
        """

        image_name = 'dockerfile/elasticsearch'
        container_name = container_name_for(image_name, application_id)
        cache_dir = cache_directory(container_name)

        if not os.path.exists(cache_dir):
            LOGGER.debug("Creating cache directory '%s'", cache_dir)
            os.makedirs(cache_dir)

        config_path = join(cache_dir, 'elasticsearch.yml')
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

        container = ensure_container(
            image=image_name,
            port=9200,
            application_id=application_id,
            data_dir='/data',
        )

        instance = cls(
            index_name=application_id,
            urls=('http://localhost:{0}'.format(container.port),),
        )
        instance.wait_until_available()
        # pylint:disable=attribute-defined-outside-init
        instance.container_info = container
        return instance

    providers = ('localhost', 'container')

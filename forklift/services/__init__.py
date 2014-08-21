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
Services that can be provided to running applications.
"""

from .base import register, Service

# pylint:disable=unused-import
from .elasticsearch import Elasticsearch
from .email import Email
from .memcached import Memcache
from .postgres import PostgreSQL, PostGIS
from .proxy import Proxy
from .syslog import Syslog
from .redis import Redis

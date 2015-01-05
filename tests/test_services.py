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
Tests for services provided by Forklift.
"""

import unittest

import socket
import socketserver
import threading
import tempfile
from time import sleep
from urllib.parse import urlparse

import forklift.services
import forklift.services.base as base
from forklift.base import free_port

from tests.base import redirect_stream


class ElasticsearchTestCase(unittest.TestCase):
    """
    Test Elasticsearch service.
    """

    def test_host(self):
        """
        Test host get/set.
        """

        service = forklift.services.Elasticsearch(
            'index',
            ('http://alpha:9200|http://beta:9200',))

        self.assertEqual(service.urls, (
            urlparse('http://alpha:9200/index'),
            urlparse('http://beta:9200/index'),
        ))
        self.assertEqual(service.environment(), {
            'ELASTICSEARCH_URLS': 'http://alpha:9200|http://beta:9200',
            'ELASTICSEARCH_INDEX_NAME': 'index',
        })

        service.host = 'other'

        self.assertEqual(service.urls, (
            urlparse('http://other:9200/index'),
        ))
        self.assertEqual(service.environment(), {
            'ELASTICSEARCH_URLS': 'http://other:9200',
            'ELASTICSEARCH_INDEX_NAME': 'index',
        })

        service = forklift.services.Elasticsearch(
            'index',
            ('http://localhost:9200',))

        self.assertEqual(service.urls, (
            urlparse('http://localhost:9200/index'),
        ))
        self.assertEqual(service.host, 'localhost')

        service = forklift.services.Elasticsearch(
            'index',
            ('http://alpha:9200',
             'http://beta:9200'))

        self.assertEqual(service.urls, (
            urlparse('http://alpha:9200/index'),
            urlparse('http://beta:9200/index'),
        ))
        self.assertEqual(service.environment(), {
            'ELASTICSEARCH_URLS': 'http://alpha:9200|http://beta:9200',
            'ELASTICSEARCH_INDEX_NAME': 'index',
        })


class MemcacheTestCase(unittest.TestCase):
    """
    Test Memcache service.
    """

    def test_host(self):
        """
        Test host get/set.
        """

        service = forklift.services.Memcache(
            'index',
            ['alpha', 'beta:11222'])

        self.assertEqual(service.hosts, (
            'alpha',
            'beta:11222',
        ))

        service.host = 'other'

        self.assertEqual(service.hosts, (
            'other',
        ))

        service = forklift.services.Memcache(
            'index',
            ['localhost', 'localhost:22111', 'alpha', 'beta:11222'])
        service.host = '2.2.2.2|3.3.3.3|gamma|delta'
        self.assertEqual(service.hosts, (
            '2.2.2.2', '3.3.3.3', 'gamma', 'delta'
        ))


class SyslogTestCase(unittest.TestCase):
    """
    Test Syslog service.
    """

    def test_stdout(self):
        """
        Test printing to stdout with the fallback Syslog provider.
        """

        with tempfile.NamedTemporaryFile() as tmpfile:
            with redirect_stream(tmpfile.file.fileno()):
                syslog = forklift.services.Syslog.stdout('fake_app')
                self.assertTrue(syslog.available())
                env = syslog.environment()

                import logging
                from logging.handlers import SysLogHandler

                handler = SysLogHandler(
                    address=(env['SYSLOG_SERVER'], int(env['SYSLOG_PORT'])),
                    socktype=socket.SOCK_DGRAM
                    if env['SYSLOG_PROTO'] == 'udp'
                    else socket.SOCK_STREAM,
                )

                handler.handle(logging.LogRecord(
                    name='logname',
                    level=logging.INFO,
                    pathname='/fake/file',
                    lineno=314,
                    msg="Logging %s",
                    args="message",
                    exc_info=None,
                ))
                handler.close()

                # Give the server a chance to process the message
                sleep(1)

            with open(tmpfile.name) as saved_output:
                log = saved_output.read()
                self.assertEqual("<14>Logging message\x00\n", log)


class EmailTestCase(unittest.TestCase):
    """
    Test email service.
    """

    def test_stdout(self):
        """
        Test printing to stdout with the fallback provider.
        """

        with tempfile.NamedTemporaryFile() as tmpfile:
            with redirect_stream(tmpfile.file.fileno()):
                email = forklift.services.Email.stdout('fake_app')

                self.assertTrue(email.available())
                env = email.environment()

                import smtplib

                smtp = smtplib.SMTP(host=env['EMAIL_HOST'],
                                    port=env['EMAIL_PORT'])
                smtp.sendmail(
                    from_addr='forklift@example.com',
                    to_addrs=('destination@example.com',),
                    msg='Email message',
                )
                smtp.quit()

                # Give the server a chance to process the message
                sleep(1)

            with open(tmpfile.name) as saved_output:
                log = saved_output.read().splitlines()
                self.assertEqual([
                    '---------- MESSAGE FOLLOWS ----------',
                    'Email message',
                    '------------ END MESSAGE ------------',
                ], log)


class BaseTestCase(unittest.TestCase):
    """
    Test base services functions.
    """

    def test_port_open(self):
        """
        Test port_open.
        """

        class DummyHandler(socketserver.BaseRequestHandler):
            """
            A do-nothing handler.
            """

            def handle(self):
                pass

        class DummyServer(socketserver.ThreadingMixIn,
                          socketserver.TCPServer):
            """
            A do-nothing server.
            """

            pass

        port = free_port()
        self.assertFalse(base.port_open('localhost', port))

        server = DummyServer(('0.0.0.0', port), DummyHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()

        try:
            self.assertTrue(base.port_open('localhost', port))
        finally:
            server.shutdown()


class MockLogger(object):
    """
    A mock for Python logger
    """

    def __init__(self):
        self.logs = {}

    # pylint:disable=missing-docstring, invalid-name
    def isEnabledFor(self, *args):
        return True

    def debug(self, fstring, *args):
        self.logs.setdefault('debug', []).append(fstring % args)

    def info(self, fstring, *args):
        self.logs.setdefault('info', []).append(fstring % args)

    def warning(self, fstring, *args):
        self.logs.setdefault('warning', []).append(fstring % args)

    def error(self, fstring, *args):
        self.logs.setdefault('error', []).append(fstring % args)

    def critical(self, fstring, *args):
        self.logs.setdefault('critical', []).append(fstring % args)


class SettingsLogTestCase(unittest.TestCase):
    """
    Test the log_service_settings function
    """
    def setUp(self):
        self.logger = MockLogger()

    def test_basic(self):
        """
        Check that basic logging of properties works
        """
        setattr(self, 'containers', 'pretty great')
        setattr(self, 'score', 9001)

        base.log_service_settings(self.logger, self,
                                  'containers', 'score')
        self.assertEqual(self.logger.logs, {
            'debug': [
                'SettingsLogTestCase containers: pretty great',
                'SettingsLogTestCase score: 9001',
            ],
        })

    def test_callable(self):
        """
        Check that if attrs are callable, they are correctly called to get
        the value
        """
        setattr(self, 'the_callable', lambda: 'the value')
        setattr(self, 'not_callable', 9001)

        base.log_service_settings(self.logger, self,
                                  'the_callable', 'not_callable')
        self.assertEqual(self.logger.logs, {
            'debug': [
                'SettingsLogTestCase the_callable: the value',
                'SettingsLogTestCase not_callable: 9001',
            ],
        })

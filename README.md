Forklift - when you need to handle just one container
=====================================================

Utilities to develop a containerised application.

The standard containers at InfoXchange require a number of environment
variables to run properly. With Forklift, they can be inferred automatically
and/or specified in the codebase.

Furthermore, it is often necessary to experiment within a running container.
Forklift includes a special 'sshd' mode to start the SSH daemon instead of the
original command, so that one can run arbitary commands inside.

Installation
------------

    sudo pip install docker-forklift

Or in a virtualenv:

    pip install docker-forklift

Warning: Forklift requires Python 3, and you should use the corresponding `pip`
to install, for example, `pip-3.2` on Debian and `pip3` on Ubuntu
(`sudo apt-get install python3-pip`). If unsure, check that `pip --version`
reports being `python 3`.

Running Forklift
----------------

The basic invocation is:

    forklift APPLICATION ARGUMENT...

What happens is:

* The configuration files are being searched for a list of services to provide
to the command.
* For all of those services, an available provider is searched for.
* The found services, along with any additional configured environment, are
passed to the command as environment variables.

For example, if the project specifies:

    services:
        - postgresql

Forklift will check if the PostgreSQL server is running on the local machine,
and pass the database URL to the application.

Docker
------

Forklift can run commands directly or Docker containers. By default, if the
application given is an existing file (e.g. `./manage.py`), it is run directly.
Otherwise it is assumed to be a Docker image to create a container from.
The environment is passed to the application in either case.

To override the choice, set `driver` parameter to either `docker` or `direct`.

Docker driver has specific parameters:

* `rm`: Automatically remove containers after they've stopped.
* `privileged`: Run containers in privileged mode.
* `interactive`: Run containers in interactive mode (`-i -t`).
* `storage`: Run the container with `/storage` mounted as a volume under the
specified path.
* `mount-root`: Bind mount the root directory of the container filesystem to
the specified path.

### SSH daemon mode

Forklift can set up an SSH server inside the container, passing in all the
environment and adding the user public key. To use this mode, pass `sshd` as
the command (e.g. `forklift ubuntu sshd`).

The following additional options apply in SSH daemon mode:

* `user` - the user to set up for SSH in the container, defaults to `app`.
* `identity` - the public key file to authorise logging in as. Can be specified
as the full path or as a file in `~/.ssh`.
* `host-uid` - for ease to use with `mount-root`, the UID of the user inside
the container is changed to the one of the host user; override if needed.

When running in SSH daemon mode, Forklift starts the container in the
background and prints a command to SSH to it. It is up to the user to stop
the container when no longer needed.

Services and environment
------------------------

The following environment is always available to the running application:

* `ENVIRONMENT`: `dev_local`
* `DEVNAME`: the current user name
* `SITE_DOMAIN` and `SITE_PROTOCOL`: The URL where the application will be
accessible to the outside world if it listens on port 8000 locally.
* Any environment variables from configured services.
* All variables under `environment` (e.g. `environment.FOO` will be passed in
as `FOO`).

The services to provide to the application are taken from the `services` array
in the configuration file. The following services are known to Forklift:

### PostgreSQL

Provides access to the database. The environment variable, `DB_DEFAULT_URL`,
contains a [Database URL][dj-database-url] for the application to use.

By default, Forklift checks if there is a PostgreSQL server running on the
machine, and if yes, provides the application with its details, taking the
current directory name for the database name.

The following parameters can be overridden: `host`, `port`, `user`, `password`,
`name`.

### Elasticsearch

Provides an URL to access Elasticsearch at as environment variables
`ELASTICSEARCH_URLS` (the `|`-separated list of URLs to try at round robin)
and `ELASTICSEARCH_INDEX_NAME` (the index to use).

By default, the localhost is checked for a running instance of Elasticsearch
and if successful, the current directory name is provided to use as the index.

The following parameters can be overridden: `urls`, `index_name`.

### HTTP Proxy

Provides an HTTP proxy as an URL in `HTTP_PROXY`.

The following parameters can be overridden: `host`, `port`.

### Email (SMTP)

Provides an MTA for the application to connect to.

Defaults to `localhost` port 25.

The following parameters can be overridden: `host`, `port`.

### Logging (syslog)

Provides a syslog instance to log events to.

If not overridden, Forklift will start a daemon to print out all messages to
standard output and provide its address to the application.

The following parameters can be specified: `host`, `port`, `proto` (`tcp` or
`udp`).

Configuration
-------------

Forklift has a hierarchy of configuration options. For example, `services`
parameter is an array of services the application need, `environment` is a
dictionary of extra environment variables to provide, `postgresql` overrides
options for PostgreSQL service, etc.

Every parameter value is searched, in order, in the following locations:

* Command line, e.g. `--driver direct` or `--postgres.port 5433` (note the
nested parameter syntax).
* User per-project configuration file in `forklift/PROJECT.yaml` inside the
[XDG configuration directory][xdg] (usually `$HOME/.config`), where
`PROJECT` is the base name of the current directory.
* Global user configuration file in `forklift/_default.yaml` in the same
directory.
* Project configuration file - `forklift.yaml` in the current directory.

The project configuration file is a place to store settings which the project
always needs, such as a list of required services, and is intended to be
checked into the version control system. (As such, the sensitive settings such
as passwords should not go here.) For example, a project depending on a
database might have:

    services:
      - postgres

User configuration files allow people to override project settings to adapt it
to their local setup. For example, if the PostgreSQL database server on a
particular machine runs on port 5433, the `_default.yaml` can contain:

    postgres:
      port: 5433

This setting will be applied to all projects which are run through Forklift,
as long as they use a PostgreSQL database. An exotic setting only a specific
project needs can be overridden in a per-project user configuration file, for
example, `foo.yaml`:

    environment:
      # Only foo project needs this other database connection
      DB_ANOTHER_URL: postgres://alice:rabbit@test.server/foo_test_db

Finally, the command line options can be used to quickly alter settings while
developing.

[dj-database-url]: https://github.com/kennethreitz/dj-database-url
[xdg]: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

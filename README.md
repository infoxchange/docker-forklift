Forklift - when you need to handle just one container
=====================================================

Utilities to develop a containerised application.

The standard containers at InfoXchange require a number of environment
variables to run properly. With Forklift, they can be inferred automatically
and/or specified in the codebase.

Furthermore, it is often necessary to experiment within a running container.
Forklift includes a special 'sshd' mode to start the SSH daemon instead of the
original command, so that one can run arbitary commands inside.

Running Forklift
----------------

The basic invocation is:

    forklift <application> <arguments>...

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

Docker vs. direct run
---------------------

Forklift can run commands directly or Docker containers. By default, if the
application given is an existing file (e.g. `./manage.py`), it is run directly.
Otherwise it is assumed to be a Docker image to create a container from.
The environment is passed to the application in either case.

To override the choice, set `executioner` parameter to either `docker` or
`direct`.

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

The following parameters can be overridden: `url`, `index_name`.

Configuration
-------------

Forklift has a hierarchy of configuration options. For example, `services`
parameter is an array of services the application need, `environment` is a
dictionary of extra environment variables to provide, `postgresql` overrides
options for PostgreSQL service, etc.

Every parameter value is searched, in order, in the following locations:

* Command line, e.g. `--executioner direct` or `--postgres.port 5433` (note the
nested parameter syntax).
* User configuration file in `forklift/PROJECT.yaml`, where `PROJECT` is the
base name of the current directory, inside the
[XDG configuration directory][xdg] (usually `$HOME/.config`).
* Project configuration file - `forklift.yaml` in the current directory.

This allows granular overriding of the (hopefully useful) Forklift defaults.

[dj-database-url]: https://github.com/kennethreitz/dj-database-url
[xdg]: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

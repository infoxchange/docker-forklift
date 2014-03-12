Forklift - when you need to handle just one container
=====================================================

Utilities to develop a containerised application.

The standard containers at InfoXchange require a number of environment
variables to run properly. With Forklift, they can be inferred automatically
and/or specified in the codebase.

Furthermore, it is often necessary to experiment within a running container.
Forklift includes a special 'sshd' mode to start the SSH daemon instead of the
original command, so that one can run arbitary commands inside.

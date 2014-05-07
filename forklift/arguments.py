"""
Argument parsing utilities.
"""

from argparse import Namespace


def argument_factory(add_argument, name):
    """
    A factory to prepend all argument names with a prefix.
    """

    def wrapped(*args, **kwargs):
        """
        Prepend all argument names with a prefix before adding the argument.
        """

        assert all(option[:2] == '--' for option in args)
        option_names = [
            '--{0}.{1}'.format(name, option[2:])
            for option in args
        ]
        return add_argument(*option_names, **kwargs)

    return wrapped


def convert_to_args(conf, prefix=None):
    """
    Convert hierarchical configuration dictionary to argparse arguments.

    'environment' at root level is a special case: if it is a hash,
    it is converted into an array of VAR=VALUE pairs.
    """

    args = []
    conf = conf or {}
    prefix = prefix or ()

    if not prefix and 'environment' in conf:
        environment = conf['environment']
        if isinstance(environment, dict):
            conf['environment'] = [
                '{0}={1}'.format(k, v)
                for k, v in environment.items()
            ]

    for key, value in conf.items():
        arg_prefix = prefix + (key,)
        if isinstance(value, dict):
            args.extend(convert_to_args(value, arg_prefix))
        else:
            if not isinstance(value, (list, tuple)):
                value = (value,)

            if len(value) > 0:
                args.append('--' + '.'.join(arg_prefix))
                for val in value:
                    args.append(str(val))

    return args


def project_args(args, prefix):
    """
    Return only keys in the object having the specified prefix, stripping
    the prefix.
    """

    pairs = vars(args).items()
    strip_len = len(prefix) + 1

    return Namespace(**dict(
        (key[strip_len:], value)
        for key, value in pairs
        if key.startswith(prefix + '.')
    ))

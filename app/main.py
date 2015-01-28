import sys
import argparse
import commands

__version__ = (0, 2, 0, 'alpha', 3)

def fmt_version(type='long', v=__version__):
    """ format the version in long or short form """
    if type == 'long':
        return "{}.{}.{}-{}.{}".format(*v)
    elif type == 'short':
        return "{}.{}.{}".format(*v[:3])
    elif type == 'major':
        return "{}".format(v[0])
    else:
        raise NameError("unknown version format type {}".format(type))

def main():
    """
    Main command-line execution loop.

    """

    parser = argparse.ArgumentParser(
        description='Herd Enables Rapid Deployment. A devops management tool.')
    parser.add_argument('--version', dest='version', action='store_const',
                         const=True, help='Print the version and exit.')

    parser.add_argument('command', nargs='?', help='herd command to execute')
    parser.add_argument('command_args', nargs='*',
                         help='arguments for the command')

    args = parser.parse_args()

    # if the version flag is present just print the version and exit
    if args.version:
        print "herd version", fmt_version()
        sys.exit()

    allowed_commands = ['deploy', 'trivial']
    if args.command in allowed_commands:
        # don't allow any arguments to include illegal characters
        for illegal in ['&', ';']:
            try:
                assert reduce(lambda a, b: a and b,
                              map(lambda arg: illegal not in arg,
                                  args.command_args))
            except:
                raise ValueError(
                    "Illegal character '{}' not allowed".format(illegal))

        getattr(commands, args.command)(*args.command_args)
    else:
        print '"{}" is not a valid herd command.'.format(args.command)

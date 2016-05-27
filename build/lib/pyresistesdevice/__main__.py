# -*- coding: utf-8 -*-
'''
    pyresistesdevice
    ----------------

    The public API and command-line interface to PyResistESDevice package.

    :copyright: Copyright 2015 Lionel Darras and contributors, see AUTHORS.
    :license: GNU GPL v3.

'''
import os
import argparse
import time
import msvcrt
import copy
from datetime import datetime

# Make sure the logger is configured early:
from . import VERSION
from .logger import active_logger
from .device import ResistESDevice
from .compat import stdout


def startacquisition_cmd(args, device):
    '''start acquisition '''

    device.setconfig(args.voltage, args.frequency, args.impuls_nb, args.channels_nb, args.integration_nb)

                                                                            # acquire all measures
    device.acquiremeasures(args.output, args.delim, args.stdoutdisplay, args.datetimedisplay)
    

    

def get_cmd_parser(cmd, subparsers, help, func):
    '''Make a subparser command.'''
    parser = subparsers.add_parser(cmd, help=help, description=help)
    parser.add_argument('--timeout', default=10.0, type=float,
                        help="Connection link timeout")
    parser.add_argument('--debug', action="store_true", default=False,
                        help='Display log')
    parser.add_argument('url', action="store",
                        help="Specify URL for connection link. "
                             "E.g. tcp:iphost:port "
                             "or serial:/dev/ttyUSB0:19200:8N1")
    parser.add_argument('--voltage', default=16.55, type=float,
                           help='voltage of injected signal, V (default: 16.55)')
    parser.add_argument('--frequency', default=976.5625, type=float,
                           help='frequency of injected signal, kHz (default: 0.98kHz)')
    parser.add_argument('--impuls_nb', default=1, type=int,
                           help='external impulsions number triggering measure (default: 1)')
    parser.add_argument('--channels_nb', default=1, type=int,
                           help='channels number to measure (default: 1)')
    parser.add_argument('--integration_nb', default=1, type=int,
                           help='number of values transmitted at computer in 1s (default: 0 (manual command with key touch))')
    parser.set_defaults(func=func)
    return parser


def main():
    '''Parse command-line arguments and execute ResistESDevice command.'''

    parser = argparse.ArgumentParser(prog='pyResistESDevice',
                                     description='Communication tools for '
                                                 'Resistivimeter Electro-Static '
                                                 'Device')
    parser.add_argument('--version', action='version',
                         version='PyResistESDevice version %s' % VERSION,
                         help='Print PyResistESDevice version number and exit.')

    subparsers = parser.add_subparsers(title='The PyResistESDevice commands')
    # startacquisition command
    subparser = get_cmd_parser('startacquisition', subparsers,
                               help='Start acquisition.',
                               func=startacquisition_cmd)
    subparser.add_argument('--output', action="store", default=stdout,
                           type=argparse.FileType('w'),
                           help='Filename where output is written (default: standard out')
    subparser.add_argument('--delim', action="store", default=";",
                           help='CSV char delimiter (default: ";"')
    subparser.add_argument('--stdoutdisplay', action="store_true", default=False,
                           help='Display on the standard out if defined output is a file')
    subparser.add_argument('--datetimedisplay', action="store_true", default=False,
                           help='Display date and time before fields on the standard out and output file')

    
    # Parse argv arguments
    try:
        args = parser.parse_args()
        try:            
            if args.func:
                isfunc = True
        except:
            isfunc = False

        if (isfunc == True):
            if args.debug:
                active_logger()
                device = ResistESDevice.from_url(args.url, args.timeout)
                args.func(args, device)
            else:
                try:                
                    device = ResistESDevice.from_url(args.url, args.timeout)
                    args.func(args, device)
                except Exception as e:
                    parser.error('%s' % e)
        else:
            parser.error("No command")

                    
    except Exception as e:
        parser.error('%s' % e)
        

if __name__ == '__main__':
    main()

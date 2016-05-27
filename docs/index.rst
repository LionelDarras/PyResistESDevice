==========================================================================
PyResistesDevice : Communication with an Electro-Static Resistivimeter.
==========================================================================

.. module:: pyresistesdevice

About
-----

This project was conducted by `UMR5133-Archéorient`_ (FR) and `UMR7619-Métis`_ (FR) laboratories.

.. _`UMR5133-Archéorient`: http://www.archeorient.mom.fr/
.. _`UMR7619-Métis`: http://www.metis.upmc.fr/fr
	
Description
-----------

PyResistESDevice is a python project which aims to allow the communication with
an electro-static resistivimeter device developped by UMR7619-Metis Laboratory.

The main features include collecting of measures.

The tool can be used in your python scripts, or in command line mode to collect data in CSV files.

**Note:** PyResistESDevice uses the `PyLink <http://pypi.python.org/pypi/PyLink>`_ lib, offers a universal communication interface with File-Like API.

--------
Examples
--------

We init communication by giving the device URL.


::

  On Linux :
  >>> from pyresistesdevice import ResistESDevice
  >>> device = ResistESDevice.from_url('serial:/dev/ttyUSB0:38400:8N1')
  or, on Windows :
  >>> device = ResistESDevice.from_url('serial:COM10:38400:8N1')

To set the device configuration, use:

::

  >>> device.setconfig(voltage, frequency, impuls_nb, channels_nb,
      integration_nb)

To start measures acquisition, use :

::

  >>> device.acquiremeasures("outputfile.csv", delim=';')

During this acquisition, it is possible to get a manual measure pushing a key on keyboard,
and it is possible to interrupt the acquisition with "Ctrl" + "C" keys.

--------
Features
--------

* Collecting real-time data in a CSV file
* Comes with a command-line script
* Compatible with Python 3.x


------------
Installation
------------

Download the zip file "PyResistESDevice-vx.y" and unzip it.

Then, you can install now PyResistESDevice with this command:

.. code-block:: console

    $ python setup.py install

Note : On this first version, PyResistESDevice only works on Windows System because of key touch detection used.
It will be operational on others Operating Systems on latest versions.

------------------
Command-line usage
------------------

PyResistESDevice has a command-line script that interacts with the device.

.. code-block:: console

  $ pyresistesdevice -h
  usage: pyresistesdevice [-h] [--version] {startacquisition} ...

  Communication tools for Resistivimeter Electro-Static Device

  optional arguments:
    -h, --help            Show this help message and exit
    --version             Print ResistESDevice’s version number and exit.

  The PyResistESDevice commands:
      startacquisition    Start acquisition

Startacquisition
----------------

The `startacquisition` command start the acquisition of measures from device.

.. code-block:: console

    $ pyresistesdevice startacquisition -h
    usage: pyresistesdevice startacquisition[-h] [--timeout TIMEOUT]
					    [--debug]
					    [--voltage VOLTAGE]
                                            [--frequency FREQUENCY]
					    [--impuls_nb IMPULS_NB]
        				    [--channels_nb CHANNELS_NB]
					    [--integration_nb INTEGRATION_NB]
					    [--output OUTPUT]
                                            [--delim DELIM]
					    [--stdoutdisplay]
					    url

    Start acquisition.

    positional arguments:
      url                  Specifiy URL for connection link.
                           E.g. tcp:iphost:port or
                           serial:/dev/ttyUSB0:19200:8N1

    optional arguments:
      -h, --help            Show this help message and exit
      --timeout TIMEOUT     Connection link timeout (default: 10.0)
      --debug               Display log (default: False)
      --voltage VOLTAGE     voltage of injected signal, V (default: 16.55)
      --frequency FREQUENCY frequency if injected signal, kHz
			    (default: 0.98kHz)
      --impuls_nb IMPULS_NB external impulsions number triggering measure
                            (default: 1)
      --channels_nb CHANNELS_NB
			    channels number to measure (default: 1)
      --integration_nb INTEGRATION_NB
			    number of valuestransmitted at computer in 1s
			    (default: 0(manual command with key touch))
      --output OUTPUT       Filename where output is written
			    (default: standard out)
      --delim DELIM         CSV char delimiter (default: ";")
      --stdoutputdisplay    Display on the standard out if define output
                            is a file (default: False)
      --datetimedisplay     Display date and time before fields on the
			    standard out and output file (default: False)


**Example**

.. code-block:: console

    $ pyresistesdevice startacquisition serial:COM1:115200:8N1
    count;rec. batt. voltage(mV);em. batt. voltage(mV);phase current(mA);
    quad. current(mA);phase potential(mV) (ch0);quad. potential(mV) (ch0);
    phase resistivity(kOhm.m) (ch0);quad. resistivity(kOhm.m) (ch0)
    0;12522;12331;10310.916907;
    9932.555428;2837.073281;1848.752480;0.025554;-0.004893
    0;12435;12340;10480.518199;
    9893.429889;2752.634697;2499.727383;0.028374;-0.000548


Debug mode
----------

You can use debug option if you want to print log and see the flowing data.

.. code-block:: console

    $ pyresistesdevice startacquisition serial:COM5:115200:8N1
      --voltage 16.85 --debug
    2016-02-23 16:01:16,070 INFO: new <SerialLink serial:COM5:115200:8N1>
                                  was initialized
    2016-02-23 16:01:16,080 INFO: Check parameters : 16.850000 976.562500
                                  1 1 1
    2016-02-23 16:01:16,080 INFO: Check voltage parameter: OK
                                  (16.550000 <= 16.850000 <= 196.510000)
    2016-02-23 16:01:16,080 INFO: Check voltage parameter: GOOD CONVERSION
                                  (16.850000, FA)
    2016-02-23 16:01:16,080 INFO: Check frequency parameter: OK
                                  (0.000000 <= 976.562500 <= 3125.000000)
    2016-02-23 16:01:16,080 INFO: Check frequency parameter: GOOD CONVERSION
                                  (976.562500, 00080000)
    2016-02-23 16:01:16,080 INFO: Check impuls_nb parameter: OK (1 <= 127)
    2016-02-23 16:01:16,080 INFO: Check channels_nb parameter: OK (1 <= 255)
    2016-02-23 16:01:16,080 INFO: Check integration_nb parameter: OK
                                  (1 <= 16383)
    2016-02-23 16:01:16,080 INFO: Configuration frame (10 bytes): F5 03 00
                                  00 20 00 01 01 01 00
    2016-02-23 16:01:16,080 INFO: Try send : F5 03 00 00 20 00 01 01 01 00
    2016-02-23 16:01:16,090 INFO: Write : <F5 03 00 00 20 00 01 01 01 00>
    2016-02-23 16:01:16,190 INFO: Read : <B0 80 90 61 FE 6B E5 79 09 1A B0>
    2016-02-23 16:01:16,210 ERROR: Check ACK: BAD (b'\xf5\x03\x00\x00 \x00
                                  \x01\x01\x01\x00', b'\xb0\x80\x90a\xfek
                                  \xe5y\t\x1a\xb0')
    pyResistESDevice: error: No valid acknowledgement.
    2016-02-23 16:01:16,080 INFO: Connection <SerialLink
                                  serial:COM5:115200:8N1> was closed

.. _api:

-------------
API reference
-------------

.. autoclass:: ResistESDevice
    :members: from_url

    .. automethod:: send(data, wait_ack=None, timeout=None)
    .. automethod:: setconfig(voltage, frequency, impuls_nb, channels_nb, integration_nb, timeout=None)
    .. automethod:: acquiremeasures(output=None, delim=';', stdoutdisplay=False, datetimedisplay=False)


    calculating and converting functions :

    .. automethod:: topotentialrealvalue(potentialcodedvalue)
    .. automethod:: tocurrentrealvalue(currentcodedvalue)
    .. automethod:: toresistivityvalue(phasecurrentvalue, quadcurrentvalue, phasepotentialvalue, quadpotentialvalue)


    functions to code to configuration frame and to decode measure frames :

    .. automethod:: _from_measureframe(measureframe)
    .. automethod:: _to_configframe(voltage, frequency, impuls_nb, channels_nb, integration_nb)


    constants used :

    .. autoattribute:: INJVOLT_MIN
    .. autoattribute:: INJVOLT_MAX
    .. autoattribute:: INJFREQ_MIN
    .. autoattribute:: INJFREQ_MAX
    .. autoattribute:: RI

.. autoexception:: pyresistesdevice.device.BadConfigParamException

.. autoexception:: pyresistesdevice.device.BadAckException

---------------------
Feedback & Contribute
---------------------

Your feedback is more than welcome. Write email to the
`PyResistESDevice mailing list`_.

.. _`PyResistESDevice mailing list`: lionel.darras@mom.fr

.. include:: ../CHANGES.rst

****************************
Mopidy-PulseAudio
****************************

.. image:: https://pypip.in/version/Mopidy-PulseAudio/badge.png?latest
    :target: https://pypi.python.org/pypi/Mopidy-PulseAudio/
    :alt: Latest PyPI version

.. image:: https://pypip.in/download/Mopidy-PulseAudio/badge.png
    :target: https://pypi.python.org/pypi/Mopidy-PulseAudio/
    :alt: Number of PyPI downloads

.. image:: https://travis-ci.org/liamw9534/mopidy-pulseaudio.png?branch=master
    :target: https://travis-ci.org/liamw9534/mopidy-pulseaudio
    :alt: Travis CI build status

.. image:: https://coveralls.io/repos/liamw9534/mopidy-pulseaudio/badge.png?branch=master
   :target: https://coveralls.io/r/liamw9534/mopidy-pulseaudio?branch=master
   :alt: Test coverage

`Mopidy <http://www.mopidy.com/>`_ extension for PulseAudio server management.

Installation
============

Install by running::

    pip install Mopidy-PulseAudio

Or, if available, install the Debian/Ubuntu package from `apt.mopidy.com
<http://apt.mopidy.com/>`_.


Configuration
=============

PulseAudio
-----------

For bluetooth support ensure the module ``module-bluetooth-discover`` is loaded.

Extension
---------

Add the following section to your Mopidy configuration file following installation::

    [audio]
    output = pulsesink device=mopidy

    [pulseaudio]
    enabled = true
    name = mopidy
    auto_sources = default
    auto_sinks = default

The audio configuration option ``output`` must be configured for ``pulsesink`` with the ``device``
property set to the same value as configured under ``name`` for pulseaudio.  Note that the pulseaudio extension
creates a sink for mopidy during start-up.

The ``auto_sources`` and ``auto_sinks`` settings allows all named sources to be connected to
all named sinks.  The configurations are a list with two special values permitted:

- ``default``: the source/sink selected is the pulseaudio default source/sink
    - note: default source is always the sink monitor connected to mopidy.
- ``all``: all source/sinks are selected
    - note: Monitor source/sinks are filtered out


Project resources
=================

- `Source code <https://github.com/liamw9534/mopidy-pulseaudio>`_
- `Issue tracker <https://github.com/liamw9534/mopidy-pulseaudio/issues>`_
- `Download development snapshot <https://github.com/liamw9534/mopidy-pulseaudio/archive/master.tar.gz#egg=mopidy-pulseaudio-dev>`_


Changelog
=========


v0.2.0 (UNRELEASED)
----------------------------------------

- Create networked audio sinks e.g., RTP, TCP

v0.1.0
----------------------------------------

Supports the following features:

- Connect/disconnect mopidy to/from audio sinks via HTTP API
- Connect any arbitrary audio source to an audio sink via HTTP API
- Detect new bluetooth audio sources/sinks (A2DP)
- Auto-connect feature for discovered sources and sinks
- Zeroconf publish and discovery
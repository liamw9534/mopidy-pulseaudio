from __future__ import unicode_literals

import logging
import pykka
import pypulseaudio
import gobject
import threading

from mopidy import service
from mopidy.utils.jsonrpc import private_method

logger = logging.getLogger(__name__)

PULSEAUDIO_SERVICE_NAME = 'pulseaudio'


class PulseAudioManager(pykka.ThreadingActor, service.Service):
    """
    PulseAudioManager allows access to a pulseaudio server
    in order to connect to and configure pulseaudio services
    in conjunction with mopidy.

    It implements a mopidy Service and posts events to any classes
    mixing in the ServiceListener interface.

    Some of the use-cases supported are:

    - Connect/disconnect mopidy to/from audio sinks
    - Connect any arbitrary audio source to an audio sink
    - Detect new bluetooth audio sources/sinks (A2DP)
    - Auto-connect feature for discovered sources and sinks
    - Create networked audio sinks e.g., RTP, TCP
    """
    name = PULSEAUDIO_SERVICE_NAME
    public = True
    sources = {}
    sinks = {}
    event_sources = {}
    refresh = 1
    pulse = None

    def __init__(self, config, core):
        super(PulseAudioManager, self).__init__()
        self.config = dict(config['pulseaudio'])

    def _deregister_event_source(self, source):
        tag = self.event_sources.pop(source, None)
        if (tag is not None):
            gobject.source_remove(tag)

    def _deregister_event_sources(self):
        for source in self.event_sources.keys():
            self._deregister_event_source(source)

    def _register_refresh_timeout(self):
        tag = gobject.timeout_add(int(self.refresh * 1000),
                                  self._refresh_timeout_callback)
        self.event_sources['timeout'] = tag

    def _refresh_timeout_callback(self):
        if (not self.lock.acquire(False)):
            return False
        self._refresh_sources()
        self._refresh_sinks()
        self._refresh_connections()
        self._scan_and_activate_bluetooth_a2dp()
        self._refresh_auto_connections()
        self._register_refresh_timeout()
        self.lock.release()
        return False

    def _find_module_by_name(self, name):
        modules = self.pulse.get_module_info_list()
        for m in modules:
            if (name == m['name']):
                return m

    def _load_null_sink(self):
        # Create a null sink using 'name' config attribute if one does
        # not already exist.  The mopidy audio subsystem will need to be
        # configured to use a pulse sink with the same name as part of
        # the mopidy audio config
        sink_names = [i['name'] for i in self.pulse.get_sink_info_list()]
        if (self.config['name'] not in sink_names):
            module_args = { 'sink_name': self.config['name'] }
            self.pulse.load_module('module-null-sink', module_args)
            self.pulse.set_default_source(self.config['name'] + '.monitor')

    def _load_bluetooth(self):
        # First check to see if bluetooth module exists and (re)load it
        m = self._find_module_by_name('module-bluetooth-discover')
        if (m):
            self.pulse.unload_module(m['index'])
        self.pulse.load_module('module-bluetooth-discover')

    def _load_zeroconf(self):
        # This allows us to see published audio devices on other
        # mopidy servers, and will also publish our own devices
        self.pulse.load_module('module-zeroconf-discover')
        self.pulse.load_module('module-zeroconf-publish')

    def _load_loopback(self, source, sink):
        connection = {'source': source, 'sink': sink}
        # Do not allow the same connection to be established more than once
        for index in self.connections.keys():
            if (self.connections[index] == connection):
                return index
        index = self.pulse.load_module('module-loopback', connection).pop()
        self.connections[index] = connection
        return index

    def _refresh_sinks(self):
        sinks = self.pulse.get_sink_info_list()
        sink_names = [s['name'] for s in sinks]
        for s in sinks:
            if (s['name'] not in self.sinks):
                self.sinks[s['name']] = s
                service.ServiceListener.send('pulseaudio_sink_added', service=self.name,
                                             sink=s)
        for s in self.sinks.keys():
            if (s not in sink_names):
                k = self.sinks.pop(s)
                service.ServiceListener.send('pulseaudio_sink_removed', service=self.name,
                                             sink=k)

    def _refresh_sources(self):
        sources = self.pulse.get_source_info_list()
        source_names = [s['name'] for s in sources]
        for s in sources:
            if (s['name'] not in self.sources):
                self.sources[s['name']] = s
                service.ServiceListener.send('pulseaudio_source_added', service=self.name,
                                             source=s)
        for s in self.sources.keys():
            if (s not in source_names):
                k = self.sources.pop(s)
                service.ServiceListener.send('pulseaudio_source_removed', service=self.name,
                                             source=k)

    def _scan_and_activate_bluetooth_a2dp(self):
        cards = self.pulse.get_card_info_list()
        for c in cards:
            for p in c['profiles']:
                if (p['name'] == 'a2dp' and c['active_profile'] != 'a2dp'):
                    self.pulse.set_card_profile_by_name(c['name'], 'a2dp')

    def _refresh_connections(self):
        self.connections = {}
        modules = self.pulse.get_module_info_list()
        for m in modules:
            if (m['name'] == 'module-loopback'):
                self.connections[m['index']] = m['argument']

    def _refresh_auto_connections(self):

        # Build the auto-connection list of sources and sinks
        sources_config = []
        for i in self.config['auto_sources']:
            if (i == 'default'):
                sources_config.append(self.pulse.get_server_info().pop()['default_source_name'])
            elif (i == 'all'):
                sources_config.extend([k for k in self.sources if 'monitor' not in k])
                sources_config.append(self.pulse.get_server_info().pop()['default_source_name'])
            else:
                sources_config.append(i)
        sinks_config = []
        for i in self.config['auto_sinks']:
            if (i == 'default'):
                sinks_config.append(self.pulse.get_server_info().pop()['default_sink_name'])
            elif (i == 'all'):
                sinks_config.extend([k for k in self.sinks if k != self.config['name']])
            else:
                sources_config.append(i)

        # Clean-up any stale connections
        for c in self.connections:
            if (self.connections[c]['source'] not in self.sources or
                self.connections[c]['sink'] not in self.sinks):
                self.pulse.unload_module(c)

        # Establish new connections (if any)
        connections = [self.connections[c] for c in self.connections]
        for i in sources_config:
            for j in sinks_config:
                if ({'source': i, 'sink': j} not in connections):
                    self._load_loopback(i, j)

    @private_method
    def on_start(self):
        """
        Activate the pulse audio service
        """
        if (self.pulse):
            return

        self.lock = threading.Lock()
        self.pulse = pypulseaudio.PulseAudio(app_name=self.config['name'])
        self.pulse.connect()
        self._load_null_sink()
        self._load_bluetooth()
        self._load_zeroconf()

        # Notify listeners
        self.state = service.ServiceState.SERVICE_STATE_STARTED
        service.ServiceListener.send('service_started', service=self.name)
        logger.info('PulseAudioManager started')

        # Initiate refresh timer
        self._refresh_timeout_callback()
        
        # Scan for any existing source/sink connections and
        # establish default source/sink connection
        self.connect()

    @private_method
    def on_stop(self):
        """
        Put the pulse audio service into idle mode.
        """
        if (not self.pulse):
            return
        self._deregister_event_sources()
        for c in self.connections:
            self.disconnect(c)
        self.pulse.disconnect()

        # Notify listeners
        self.state = service.ServiceState.SERVICE_STATE_STOPPED
        service.ServiceListener.send('service_stopped', service=self.name)
        logger.info('PulseAudioManager stopped')

        self.pulse = None

    @private_method
    def on_failure(self, *args):
        pass

    @private_method
    def stop(self, *args, **kwargs):
        return pykka.ThreadingActor.stop(self, *args, **kwargs)

    def set_property(self, name, value):
        if (name in self.config):
            self.config[name] = value
            service.ServiceListener.send('service_property_changed',
                                         service=self.name,
                                         props={ name: value })
            self.on_stop()
            self.on_start()

    def get_property(self, name):
        if (name is None):
            return self.config
        else:
            try:
                value = self.config[name]
                return { name: value }
            except:
                return None

    def enable(self):
        """
        Enable the service
        """
        if (self.pulse is None):
            self.on_start()
        logger.info('PulseAudioManager enabled')

    def disable(self):
        """
        Disable the service
        """
        if (self.pulse):
            self.on_stop()
        logger.info('PulseAudioManager disabled')

    def get_sources(self):
        """
        Get a list of audio sources.
        """
        self.lock.acquire()
        sources = [i['name'] for i in self.pulse.get_source_info_list()]
        self.lock.release()
        return sources

    def get_sinks(self):
        """
        Get a list of audio sinks.
        """
        self.lock.acquire()
        sinks = [i['name'] for i in self.pulse.get_sink_info_list()]
        self.lock.release()
        return sinks

    def connect(self, source=None, sink=None):
        """
        Establish a new source/sink connection
        
        :param source: source name or use mopidy.monitor source if None
        :type source: None or string
        :param sink: sink name or use default system sink if None
        :type sink: None or string
        :return: unique connection identifier
        :rtype: integer
        """
        if (source is None):
            source = self.config['name'] + '.monitor'
        if (sink is None):
            sink = self.pulse.get_server_info().pop()['default_sink_name']
        self.lock.acquire()
        index = self._load_loopback(source, sink)
        self.lock.release()
        return index

    def get_connections(self):
        """
        Return a dict of existing connections.
        """
        return self.connections

    def disconnect(self, connection):
        """
        Remove an existing source/sink connection
        """
        self.connections.pop(connection)
        self.lock.acquire()
        self.pulse.unload_module(connection)
        self.lock.release()
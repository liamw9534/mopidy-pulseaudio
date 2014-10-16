from __future__ import unicode_literals

import gobject

import pygst
pygst.require('0.10')
import gst  # noqa


class PulseAudioSink(gst.Bin):
    def __init__(self, device):
        super(PulseAudioSink, self).__init__()
        pulse = gst.element_factory_make('pulsesink')
        pulse.set_property('device', device)
        pulse.set_property('sync', False)
        queue = gst.element_factory_make('queue')
        self.add_many(queue, pulse)
        gst.element_link_many(queue, pulse)
        pad = queue.get_pad('sink')
        ghost_pad = gst.GhostPad('sink', pad)
        self.add_pad(ghost_pad)

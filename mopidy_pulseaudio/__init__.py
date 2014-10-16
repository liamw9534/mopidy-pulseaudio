from __future__ import unicode_literals

import os

from mopidy import config, ext, exceptions

__version__ = '0.1.0'


class Extension(ext.Extension):

    dist_name = 'Mopidy-PulseAudio'
    ext_name = 'pulseaudio'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['name'] = config.String()
        schema['auto_sources'] = config.List()
        schema['auto_sinks'] = config.List()
        schema['attach_audio_sink'] = config.Boolean()
        return schema

    def validate_environment(self):
        try:
            import pypulseaudio         # noqa
        except ImportError as e:
            raise exceptions.ExtensionError('Unable to find pypulseaudio module', e)

    def setup(self, registry):
        from .actor import PulseAudioManager
        registry.add('frontend', PulseAudioManager)

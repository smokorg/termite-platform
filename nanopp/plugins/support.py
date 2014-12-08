#    This file is part of Nano Plugins Platform
#    Copyright (C) 2014 Pavle Jonoski
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = 'pavle'

import logging
import re

"""
Plugin structure:
 <plugin_root>:
    + PLUGIN.MF - Plugin manifest


PLUGIN.MF structure:

Pligin-Id: <plugin_id> - string, must be unique
Version: <major>.<minor>.<patch>
Plugin-Classes: <fully-qualified-classname>,...
Requires: <RequiresEntrySpec>,...
Exports: <ExportsEntrySpec>,...
Requires-Plugins: <RequiresEntrySpec>,...

Example:

Plugin-Id: nanopp.interactive-shell
Version: 0.1.1
Plugin-Classes: nanopp.interactive.ShellPlugin,nanopp.interactive.TelnetPlugin
Requires: nanopp.* [0.0.1, 1.0);
Exports: nanopp.remote.*(1.0.0); nanopp.tools(1.0.0)
Requires-Plugins: nanopp.network-support
"""

logger = logging.getLogger('nanopp.plugins.support')


class Entry:

    def __init__(self, entry_name, is_package=False):
        self.name = entry_name
        self.is_package = is_package


class ExportsEntry(Entry):

    def __init__(self, entry_name, export_version, is_package=False):
        Entry.__init__(self, entry_name, is_package)
        self.version = export_version


def check_min_version(version, min_version, incl):
    if min_version is None:
        return True
    else:
        if incl:
            return version >= min_version
        else:
            return version > min_version


def check_max_version(version, max_version, incl):
    if max_version is None:
        return True
    else:
        if incl:
            return version <= max_version
        else:
            return version < max_version


def normalize_version(version_tpl):
    version, incl = version_tpl if isinstance(version_tpl, tuple) else (version_tpl, False)
    return normalize_version_string(version), incl


def normalize_version_string(version):
    if version is None:
        return None
    vrs = version.split('.')

    if len(vrs) < 3:
        n = 3 - len(vrs)
        while n:
            vrs.append('0')
            n -= 1
        version = '.'.join(vrs)

    return version


class RequiresEntry(Entry):

    @staticmethod
    def from_string(entry_string):
        pass

    def __init__(self, entry_name, version_range, is_package=False, is_plugin=False):
        Entry.__init__(self, entry_name, is_package)
        self.is_plugin = is_plugin
        if version_range is None or len(version_range) == 0:
            version_range = [(None, False), (None, False)]
        if len(version_range) < 2:
            version_range.append((None, False))

        self.version_range = [normalize_version(version_range[0]), normalize_version(version_range[1])]

    def version_in_range(self, version):
        min_version, min_inclusive = self.version_range[0]
        max_version, max_inclusive = self.version_range[1]

        return check_min_version(version, min_version, min_inclusive) and \
            check_max_version(version, max_version, max_inclusive)


class PluginManifest:

    def __init__(self):
        self.id = None
        self.version = None
        self.plugin_classes = []
        self.requires = []
        self.requires_plugins = []
        self.exports = []

    def __str__(self, *args, **kwargs):
        return "<PluginManifest> id=%s, version=%s" % (self.id, self.version)


class PluginManifestBuilder:

    def __init__(self):
        self._id = None
        self._version = None
        self._plugin_classes = []
        self._requires = []
        self._requires_plugins = []
        self._exports = []

    def id(self, id):
        self._id = id
        return self

    def version(self, version):
        self._version = version
        return self

    def plugin_class(self, cls):
        self._plugin_classes.append(cls)
        return self

    def plugin_classes(self, classes):
        self._plugin_classes = classes
        return self

    def requires(self, require_entry):
        self._requires.append(require_entry)
        return self

    def requires_plugins(self, require_entry):
        self._requires_plugins.append(require_entry)
        return self

    def exports(self, exports_entry):
        self._exports.append(exports_entry)
        return self

    def build(self):
        manifest = PluginManifest()
        manifest.id = self._id
        manifest.version = self._version
        manifest.plugin_classes = self._plugin_classes
        manifest.requires = self._requires
        manifest.requires_plugins = self._requires_plugins
        manifest.exports = self._exports

        return manifest


class PluginResource:

    def __init__(self):
        pass

    def get_manifest(self):
        pass

    def read_resource(self, resource_path):
        pass


class PluginManifestParser:

    ENTRY_SEP = ';'
    COMMENT = "#"
    RGX_PLUGIN_ENTRY = "^(?P<block>[^:]+):(?P<content>.*)"
    RGX_EXPORT_ENTRY = '^(?P<export>[\\w\\.]+\\s?(\\[(?P<version>[\\w\\.])\\])?'
    RGX_IMPORT_ENTRY = ''
    BLOCKS = {
        "PLUGIN-ID": {
            "content_handler": "read_plugin_id",
            "property": "id"
        },
        "VERSION": {
            "content_handler": "read_plugin_version",
            "property": "version"
        },
        "PLUGIN-CLASSES": {
            "content_handler": "read_plugin_classes",
            "property": "plugin_classes"
        },
        "REQUIRES": {
            "content_handler": "read_requires",
            "property": "requires"
        },
        "EXPORTS": {
            "content_handler": "read_exports",
            "property": "exports"
        },
        "REQUIRES-PLUGINS": {
            "content_handler": "read_requires_plugins",
            "property": "requires_plugins"
        }
    }

    def __init__(self, comment=COMMENT):
        self.comment = comment
        self.block_re = re.compile(PluginManifestParser.RGX_PLUGIN_ENTRY)
        self.blocks = {}

    def parse(self, manifest_stream):
        block = None
        content = ''
        builder = PluginManifestBuilder()
        while True:
            line = manifest_stream.readline()
            if not line:
                break
            line = line.strip()
            if line and line[0] == self.comment:
                continue
            
            m = self.block_re.match(line)
            if m:
                if block is not None:
                    self.on_block(block.strip(), content or '', builder)
                block = m.group('block')
                content = m.group('content')
            else:
                content += line.strip()
        return builder.build()

    def on_block(self, block, content, manifest_builder):
        block_config = PluginManifestParser.BLOCKS.get(block.upper())
        read_method = getattr(self, block_config['content_handler']) if block_config else None
        builder_method = getattr(manifest_builder, block_config['property']) if block_config else None
        content_entity = self.read_block(block, content, read_method)
        if builder_method:
            builder_method(content_entity)

    def read_block(self, block, content, read_method):
        if read_method:
            return read_method(content)
        return self.read_unknown_block(block, content)

    def read_plugin_id(self, content):
        return content.strip()

    def read_plugin_version(self, content):
        return content.strip()

    def read_plugin_classes(self, content):
        pass

    def read_requires(self, content):
        pass

    def read_exports(self, content):
        pass

    def read_requires_plugins(self, content):
        pass

    def read_unknown_block(self, block, content):
        logger.warn("Unknown block [%s] in manifest. Content: %s" % (block, content))
    
    def get_requires_entry(self, entry_str):
        pass
        
    def get_exports_entry(self, entry_str):
        pass
__author__ = 'pavle'

import logging
import sys
from logging import DEBUG

sys.path.append("../..")
logging.basicConfig(level=DEBUG)


import unittest
from io import StringIO


from nanopp.plugins.support import PluginManifestParser




class TestPluginManifestParser(unittest.TestCase):

    def setUp(self):
        self.PLUGIN_MF_STRING = """
        Plugin-Id: test.plugin
        Version: 0.1.2.TEST
        Plugin-Classes: test.class.One;
                        test.class.Two
        Requires: test.pkg [0.2.3, 0.2.5); test.pkg2 (1,7); other.pkg [1.a, 3.4.5]
        Exports: test.plugin [1.0.0]; test.plugin.module[1.0.0]
        Requires-Plugins: plugin1 [1.0];
                            plugin2 (1.0, 2.0);
        """

    def test_parse(self):
        parser = PluginManifestParser()
        manifest = parser.parse(StringIO(self.PLUGIN_MF_STRING))
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.id, "test.plugin")
        self.assertEqual(manifest.version, "0.1.2.TEST")
        self.assertIsNotNone(manifest.plugin_classes)
        self.assertEqual(len(manifest.plugin_classes), 2, "Expected 2 plugin classes")
        self.assertEqual(len(manifest.exports), 2, "Expected 2 exports")
        self.assertEqual(len(manifest.requires), 3, "Expected 3 requires entries")
        self.assertEqual(len(manifest.requires_plugins), 2, 'Expected 2 requires_plugins entries')
    
        

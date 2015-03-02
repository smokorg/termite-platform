# This file is part of Nano Plugins Platform
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

"""
Test
"""

import logging
from nanopp import metadata
from nanopp.dependencies import DependenciesManager
from nanopp.loader import ClassProtocolHandler, PlatformPluginsFinder, register_finder
from nanopp.plugins.support import PluginLoaderHandler, plugin_references_from_location
from nanopp.resources import BaseResourceLoader
from nanopp.tools import Proxy


class Plugin:
    """Base class for all Plugins.
    
    This is the entry point in the plugin itself. Each plugin MUST expose
    at least one implementation of Plguin.
    
    """

    STATE_UNINSTALLED = 0x0
    """ The plugin is loaded but the installation has not yet taken place or
    it has been uninstalled.
    """

    STATE_INSTALLED = 0x1
    """The plugin is installed on the platform.
    
    At this point all dependencies for the plugin had been resolved and satisfied.
    """

    STATE_ACTIVE = 0x2
    """ The plugin has been successfully activated.
    
    At this point, the call to Plugin.activate(...) has been made and no errors 
    were detected.
    """

    STATE_DEACTIVATED = 0x3
    """ The plugin has been deactivated, but it is still available on the platform.
    """

    STATE_DISPOSED = 0x4
    """ The plugin is ready to be removed from the platform.
    
    This point may have been reached by calling PluginManager.dispose(...) or
    it may be a result of an error during installation (such as dependencies that
    had not been satisfied).
    
    The plugin will be completely removed from the platform on the next garbage
    collection cycle.
    """

    def activate(self):
        pass

    def deactivate(self):
        pass

    def on_state_change(self, state):
        pass


class PluginContainer:
    def __init__(self, plugin_ref, resource_loader, plugin_manager):
        self.loader = resource_loader
        self.plugin_ref = plugin_ref
        self.plugin_manager = plugin_manager
        self.plugin_id = None
        self.manifest = None
        self.dependencies = []
        self.plugin_hooks = []
        self.plugin_state = None
        self.plugin = None
        self.version = None
        self.logger = logging.getLogger('nanopp.platform.PluginContainer')

    def load(self):
        if self.plugin_state == Plugin.STATE_DISPOSED:
            raise PluginLifecycleException("Plugin already disposed")

        self.plugin = self.loader.load('plugin:' + self.plugin_ref)
        self.manifest = self.plugin.get_manifest()
        self.plugin_id = self.manifest.id
        self.version = self.manifest.version
        self.plugin_state = Plugin.STATE_UNINSTALLED

    def install(self):
        if self.plugin_state is not Plugin.STATE_UNINSTALLED:
            raise PluginLifecycleException("Cannot install plugin. Invalid state: %s" % str(self.plugin_state))
        try:
            self.resolve_dependencies()
            self.create_hooks()
            self.plugin_state = Plugin.STATE_INSTALLED
            self.notify_state_change(Plugin.STATE_INSTALLED)
        except Exception as e:
            self.plugin_state = Plugin.STATE_DISPOSED
            raise e

    def create_hooks(self):
        manifest = self.plugin.get_manifest()
        for hook_class_name in manifest.plugin_classes:
            hook_class = self.loader.load('class:' + hook_class_name)
            hook_inst = hook_class()
            if not isinstance(hook_inst, Plugin):
                hook_inst = Proxy(target=hook_inst)
            self.plugin_hooks.append(hook_inst)

    def resolve_dependencies(self):
        pass

    def dispose_dependencies(self):
        pass

    def activate(self):
        if self.plugin_state is not Plugin.STATE_INSTALLED and self.plugin_state is not Plugin.STATE_DEACTIVATED:
            raise PluginLifecycleException("Cannot activate plugin. Invalid state: %s" % str(self.plugin_state))
        try:
            for hook in self.plugin_hooks:
                hook.activate()
            self.plugin_state = Plugin.STATE_ACTIVE
            self.notify_state_change(Plugin.STATE_ACTIVE)
        except Exception as e:
            self.logger.error("Plugin activation error: %s", e)
            self.plugin_state = Plugin.STATE_DEACTIVATED
            self.notify_state_change(Plugin.STATE_DEACTIVATED)

    def deactivate(self):
        if self.plugin_state is not Plugin.STATE_ACTIVE:
            raise PluginLifecycleException("Cannot deactivate plugin. Invalid state: %s" % str(self.plugin_state))

        for hook in self.plugin_hooks:
            try:
                hook.deactivate()
            except Exception as e:
                self.logger.error("Deactivation error in hook %s. Error: %s", hook, e)
        self.plugin_state = Plugin.STATE_DEACTIVATED
        self.notify_state_change(Plugin.STATE_DEACTIVATED)

    def uninstall(self):
        if self.plugin_state not in [Plugin.STATE_DEACTIVATED, Plugin.STATE_INSTALLED]:
            raise PluginLifecycleException("Cannot uninstall plugin. Invalid state: %s" % str(self.plugin_state))
        self.plugin_state = Plugin.STATE_UNINSTALLED
        self.notify_state_change(Plugin.STATE_UNINSTALLED)

    def dispose(self):
        if self.plugin_state is not Plugin.STATE_UNINSTALLED:
            raise PluginLifecycleException("Cannot dispose plugin. Invalid state: %s" % str(self.plugin_state))
        self.plugin_state = Plugin.STATE_DISPOSED
        self.plugin_hooks = None
        self.dispose_dependencies()
        self.plugin = None

    def notify_state_change(self, state):
        for hook in self.plugin_hooks:
            try:
                hook.on_state_change(state)
            except Exception as e:
                self.logger.error('Error on state change in hook: %s. Error: %s', hook, e)

    def get_environ(self):
        return {'__platform__': 'Nanopp'}

    def state(self):
        if not self.plugin:
            return self.plugin.state
        return None


class Platform:
    STATE_INITIALIZING = 'initializing'
    STATE_ACTIVE = 'active'
    STATE_SHUTTING_DOWN = 'shutting-down'

    def __init__(self, config):
        self.log = logging.getLogger('nanopp.platform.Platform')
        self.log.info("Nano Platform %s initializing", metadata.version)
        self.config = config
        self.resource_loader = self.create_resource_loader()
        self.plugins_finder = self.create_plugin_finder()
        self.plugins_manager = PluginManager(self.resource_loader, self.plugins_finder)
        self.state = Platform.STATE_INITIALIZING

        # the init wa successful
        self.success_init()

    def start(self):
        # locate all plugins
        # load all plugins
        # install all plugins
        # activate all plugins
        self.log.debug('Platform starting')
        self.load_all_plugins()
        self.install_all_plugins()
        self.activate_all_plugins()
        self.log.info('Platform started')

    def shutdown(self):
        self.log.info('Platform shutting down...')
        self.deactivate_all_plugins()
        self.uninstall_all_plugins()
        self.deactivate_all_plugins()
        self.plugins_manager.gc()
        self.log.info('Platform shutdown complete.')

    # helper methods

    def load_all_plugins(self):
        locations = self.config.get('platform', 'plugins-dir', fallback='').split(',') or []
        self.log.info('Loading plugins from these locations: %s' % locations)
        all_refs = []
        for location in locations:
            all_refs = all_refs + plugin_references_from_location(location)
        self.log.info('%d plugins' % len(all_refs))
        for ref in all_refs:
            self.plugins_manager.add_plugin(ref)
        self.log.info('Plugins loaded')

    def install_all_plugins(self):
        self.log.debug('Installing all plugins...')
        self.plugins_manager.install_all_plugins()
        self.log.info('All plugins installed')

    def activate_all_plugins(self):
        self.log.debug('Activating all plugins...')
        for plugin_container in self.plugins_manager.get_all_plugins():
            self.log.info('Activating [%s - version %s]' % (plugin_container.plugin_id, plugin_container.version))
            try:
                self.plugins_manager.activate_plugin(plugin_container.plugin_id)
            except Exception:
                self.log.exception('Failed to activate plugin: [%s - version %s]' % (plugin_container.plugin_id,
                                                                                     plugin_container.version))
                self.plugins_manager.deactivate_plugin(plugin_container.plugin_id)
        self.log.info('Plugins activated')

    def deactivate_all_plugins(self):
        self.log.debug('Deactivating all plugins...')
        for plugin_container in self.plugins_manager.get_all_plugins():
            if plugin_container.plugin_state is Plugin.STATE_ACTIVE:
                self.log.debug('Deactivating [%s - version %s]' % (plugin_container.plugin_id,
                                                                   plugin_container.version))
                try:
                    self.plugins_manager.deactivate_plugin(plugin_container.plugin_id)
                    self.log.info('Deactivated [%s - version %s]' % (plugin_container.plugin_id,
                                                                     plugin_container.version))
                except Exception:
                    self.log.exception('Failed to deactivate plugin %s' % plugin_container)
        self.log.info('All Plugins deactivated')

    def uninstall_all_plugins(self):
        self.log.debug('Uninstalling all plugins...')
        for plugin_container in self.plugins_manager.get_all_plugins():
            if plugin_container.plugin_state is Plugin.STATE_INSTALLED or \
               plugin_container.plugin_state is Plugin.STATE_DEACTIVATED:
                self.log.debug('Uninstalling [%s - version %s]' % (plugin_container.plugin_id,
                                                                   plugin_container.version))
                try:
                    self.plugins_manager.uninstall_plugin(plugin_container.plugin_id)
                    self.log.info('Uninstalled [%s - version %s]' % (plugin_container.plugin_id,
                                                                     plugin_container.version))
                except Exception:
                    self.log.exception('Failed to uninstall plugin %s' % plugin_container)
        self.log.info('All Plugins uninstalled')

    def destroy_all_plugins(self):
        self.log.debug('Disposing all plugins...')
        for plugin_container in self.plugins_manager.get_all_plugins():
            if plugin_container.plugin_state is Plugin.STATE_UNINSTALLED:
                self.log.debug('Disposing [%s - version %s]' % (plugin_container.plugin_id,
                                                                plugin_container.version))
                try:
                    self.plugins_manager.deactivate_plugin(plugin_container.plugin_id)
                    self.log.info('Disposed [%s - version %s]' % (plugin_container.plugin_id,
                                                                  plugin_container.version))
                except Exception:
                    self.log.exception('Failed to dispose plugin %s' % plugin_container)
        self.log.info('All Plugins disposed')

    def create_resource_loader(self):
        resource_loader = BaseResourceLoader()
        plugin_handler = PluginLoaderHandler(resource_loader)
        class_handler = ClassProtocolHandler(resource_loader)
        resource_loader.add_handler('plugin', plugin_handler)
        resource_loader.add_handler('class', class_handler)
        return resource_loader

    def create_plugin_finder(self):
        pf = PlatformPluginsFinder(self.get_restricted_modules_list())
        return pf

    def get_restricted_modules_list(self):
        return self.config.get('platform', 'restricted-modules', fallback='').split(',') or []

    def success_init(self):
        register_finder(self.plugins_finder)
        self.log.info('Registered path finder: %s' % self.plugins_finder)


class PluginManager:
    def __init__(self, resource_loader, plugin_finder):
        self.log = logging.getLogger('nanopp.platform.PluginManager')
        self.resource_loader = resource_loader
        self.plugin_finder = plugin_finder
        self.modules_dependencies = DependenciesManager()
        self.plugins_dependencies = DependenciesManager()
        self.plugins_by_ref = {}
        self.plugins_by_id = {}
        self.all_exports = {}
        self.all_requires = {}
        self.dependencies_built = False

    def add_plugin(self, plugin_ref):
        if self.plugins_by_ref.get(plugin_ref):
            raise Exception('Plugin with reference %s already added' % plugin_ref)
        pc = PluginContainer(plugin_ref, self.resource_loader, self)
        pc.load()
        if self.plugins_by_id.get(pc.plugin_id):
            self.reload_plugin(pc.plugin_id, pc)
        else:
            self.plugins_by_ref[plugin_ref] = pc
            self.plugins_by_id[pc.plugin_id] = pc
            self.__build_dependecies__(pc)

    def reload_plugin(self, plugin_id, plugin_container):
        old_plugin = self.plugins_by_id[plugin_id]
        del self.plugins_by_id[plugin_id]
        del self.plugins_by_ref[old_plugin.plugin_ref]
        if self.dependencies_built:
            self.__cleanup_dependencies__(old_plugin)
        self.__build_dependecies__(plugin_container)

    def install_plugin(self, plugin_id):
        # 1. Load the plugin resource
        # 2. Add to dependencies manager
        # 2. Register Finder/Loader for this particular plugin
        # 3. Load the main plugin classes
        plugin = self.get_plugin(plugin_id)
        if not self.dependencies_manager.all_dependencies_satisfied(plugin_id):
            raise Exception('Not all dependencies satisfied for plugin: %s' % plugin_id)
        self.plugin_finder.add_plugin(plugin)
        plugin.install()
        self.__mark_available__(plugin)

    def activate_plugin(self, plugin_id):
        plugin = self.get_plugin(plugin_id)
        plugin.activate()

    def deactivate_plugin(self, plugin_id):
        plugin = self.get_plugin(plugin_id)
        if plugin.plugin_state is Plugin.STATE_ACTIVE:
            plugin.deactivate()

    def uninstall_plugin(self, plugin_id):
        plugin = self.get_plugin(plugin_id)
        plugin.uninstall()

    def gc(self):
        pass

    def install_all_plugins(self):
        self.log.debug('Installing all plugins...')
        install_order = self.dependencies_manager.get_install_order()
        self.log.info('Installing plugins in the following order: %s' % install_order)
        for p_id in install_order:
            self.log.info('Installing plugin: %s' % p_id)
            self.install_plugin(p_id)
        self.log.info('Plugins installed')

    def get_all_plugins(self):
        return [pr for p, pr in self.plugins_by_id.items()]

    def get_plugin(self, plugin_id):
        plugin = self.plugins_by_id.get(plugin_id)
        if not plugin:
            raise Exception('Plugin with id %s is not registered' % plugin_id)
        return plugin

    def __build_dependecies__(self, plugin_container):
        plugin_id = plugin_container.plugin_id
        dependencies = []
        for imp in plugin_container.manifest.requires:
            satisfied = False
            self.all_requires[imp] = plugin_container
            for export, p_c in self.all_exports.items():
                if export.satisfies(imp):
                    dependencies.append(p_c.plugin_id)
                    satisfied = True
                    break
            if not satisfied:
                raise UnsatisfiedDependencyException(
                    'Required module <%s> stated in plugin [%s] cannot be satisfied.' % (imp, plugin_id))

        for plugin_dep in plugin_container.manifest.requires_plugins:
            req_plugin = self.__locate_plugin_for_import__(plugin_dep)
            if not req_plugin:
                raise UnsatisfiedDependencyException('Required plugin <%s> is not available' % plugin_dep)
            dependencies.append(req_plugin.plugin_id)

        self.dependencies_manager.add_dependency(plugin_id, dependencies, plugin_container)

    def __build_plugin_dependencies__(self, plugin_container):
        plugin_id = plugin_container.plugin_id
        dependencies = []
        for imp in plugin_container.manifest.requires_plugins:
            pass
        
    def __build_modules_dependencies__(self, plugin_container):
        pass
    
    def __release_plugin_dependencies__(self, plugin_container):
        pass
        
    def __release_modules_dependencies__(self, plugin_container):
        pass
        
    
    def build_dependencies(self):
        # load all exports
        for plugin_id, pc in self.plugins_by_id.items():
            for export in pc.manifest.exports:
                self.all_exports[export] = pc

        # FIXME: This could not possibly be worse
        for plugin_id, pc in self.plugins_by_id.items():
            self.__build_dependecies__(pc)

    def __cleanup_dependencies__(self, plugin_container):
        for export in plugin_container.manifest.exports:
            if self.all_exports.get(export):
                del self.all_exports[export]
        for imp in plugin_container.requires:
            if self.all_requires.get(imp):
                del self.all_requires[imp]
        self.dependencies_manager.delete_dependency(plugin_container.plugin_id)

    def __locate_plugin_for_import__(self, imp):
        for plugin_id, plugin_container in self.plugins_by_id.items():
            if imp.name == plugin_id and imp.version_in_range(plugin_container.manifest.version):
                return plugin_container
        return None

    def __mark_available__(self, plugin_container):
        self.dependencies_manager.mark_available(plugin_container.plugin_id)
        #for exp in plugin_container.manifest.exports:
        #    self.dependencies_manager.mark_available(exp.name)


class PlatformException(Exception):
    pass


class PluginLifecycleException(PlatformException):
    pass


class UnsatisfiedDependencyException(PlatformException):
    pass

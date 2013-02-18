# -*- coding: utf-8 -*-

r"""

Plugins for the mirbuild framework
==================================

The mir plugin
--------------

The mir plugin for mirbuild contains some utility classes that are not generic
enough to include them in mirbuild, but common enough within MIR that they
deserve to be in a central place.

There's a plugin class that automatically generates support files for MIR thrift
services. In your build.py, you can use it like this::

  from mirbuild.plugins.mir import *

  service = ThriftService('uriresolver')
  service.init.add_extra_arguments('--pool', '$RESOURCE_POOLSIZE')
  service.init.add_shell_command('reload', 'reload')

You also have to register that plugin object with the project ::

  project.add_plugin(service)

at some point before calling the run() method.

Multiple plugins of the same or different kinds can be added to a project.
A more elaborate example might look like this::

  for svc in 'global-tags similar-artists similar-tracks album-recs'.split():
      service = ThriftService('eclipse-' + svc,
                              binary = 'eplaylistd',
                              user = 'eplaylistd',
                              package = 'lastfm-eclipse-plugin-' + svc)
      service.init.add_extra_arguments('--pool', '$RESOURCE_POOLSIZE')
      service.init.add_shell_command('reload-plugin', 'reload plugin')
      service.init.add_shell_command('reload-catalogue', 'reload catalogue')
      project.add_plugin(service)

If your service sticks to some naming conventions, the first example given
above should actually be sufficient.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'

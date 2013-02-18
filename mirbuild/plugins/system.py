# -*- coding: utf-8 -*-

r"""
System plugins for mirbuild

General plugins for system related tasks.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'CreateUser CreateGroup CreateDirectory'.split()

import mirbuild.plugin

class CreateUser(mirbuild.plugin.Plugin):
    def __init__(self, user, group = 'users', home = None, desc = None, package = None, allow_login = False):
        self.__user = user
        self.__group = group
        self.__home = home
        self.__desc = desc
        self.__package = package
        self.__allow_login = allow_login

    def pre_package(self, project):
        project.packager.create_user(self.__user, group = self.__group, home = self.__home,
                                     desc = self.__desc, package = self.__package,
                                     allow_login = self.__allow_login)

class CreateGroup(mirbuild.plugin.Plugin):
    def __init__(self, group, package = None):
        self.__group = group
        self.__package = package

    def pre_package(self, project):
        project.packager.create_group(self.__group, package = self.__package)

class CreateDirectory(mirbuild.plugin.Plugin):
    def __init__(self, directory, user, group, mode = 0755, package = None):
        self.__directory = directory
        self.__user = user
        self.__group = group
        self.__mode = mode
        self.__package = package

    def pre_package(self, project):
        project.packager.create_dir(self.__directory, user = self.__user, group = self.__group,
                                    mode = self.__mode, package = self.__package)


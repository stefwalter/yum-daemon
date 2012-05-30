#!/usr/bin/python3 -tt
#coding: utf-8
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# (C) 2012 - Tim Lauridsen <timlau@fedoraproject.org>

"""
This is a Python 3.x client API for the yum-daemon Dbus Service

This module gives a simple pythonic interface to doing Yum package action using the 
yum-daemon Dbus service.

It use async call to the yum-daemon, so signal can be catched and a Gtk gui dont get unresonsive

Usage: (Make your own subclass based on :class:`yumdaemon3.YumDaemonClient` and overload the signal handlers)::


    from yumdaemon3 import YumDaemonClient
    
    class MyClient(YumDaemonClient):
    
        def __init(self):
            YumDaemonClient.__init__(self)
            # Do your stuff here
            
        def on_UpdateProgress(self,name,frac,fread,ftime):
            # Do your stuff here
            pass
    
        def on_TransactionEvent(self,event):
            # Do your stuff here
            pass
    
        def on_RPMProgress(self, package, action, te_current, te_total, ts_current, ts_total):
            # Do your stuff here
            pass
        

"""

import json
import sys
import re
import weakref

from gi.repository import GLib, Gio, GObject

DAEMON_ORG = 'org.baseurl.Yum'
DAEMON_INTERFACE = DAEMON_ORG+'.Interface'

DBUS_ERR_RE = re.compile('^GDBus.Error:([\w\.]*): (.*)$')

class YumDaemonError(Exception):
    'Error from the backend'

class AccessDeniedError(YumDaemonError):
    'User press cancel button in policykit window'

class YumLockedError(YumDaemonError):
    'The Yum daemon is locked'

class YumTransactionError(YumDaemonError):
    'The yum transaction failed'
    
class DBus:
    '''
    Helper class to work with GDBus in a easier way
    '''
    def __init__(self, conn):
        self.conn = conn

    def get(self, bus, obj, iface=None):
        if iface is None:
            iface = bus
        return Gio.DBusProxy.new_sync(
            self.conn, 0, None, bus, obj, iface, None
        )

    def get_async(self, callback, bus, obj, iface=None):
        if iface is None:
            iface = bus
        Gio.DBusProxy.new(
            self.conn, 0, None, bus, obj, iface, None, callback, None
        )

class WeakMethod:
    '''
    helper class to work with a weakref class method
    '''
    def __init__(self, inst, method):
        self.proxy = weakref.proxy(inst)
        self.method = method

    def __call__(self, *args):
        return getattr(self.proxy, self.method)(*args)


# Get the system bus
system = DBus(Gio.bus_get_sync(Gio.BusType.SYSTEM, None))

    
    
class YumDaemonClient:
    '''
    A class to communicate with the yumdaemon DBus services in a easy way
    '''

    def __init__(self):
        self.daemon = self._get_daemon() 
        print("daemon version : ",self.daemon.GetVersion())

    def _get_daemon(self):
        ''' Get the daemon dbus proxy object'''
        try:
            proxy = system.get( DAEMON_ORG, "/", DAEMON_INTERFACE)
            proxy.GetVersion() # Get daemon version, to check if it is alive        
            proxy.connect('g-signal', WeakMethod(self, '_on_g_signal')) # Connect the Dbus signal handler
            return proxy
        except Exception as err:
            self._handle_dbus_error(err)

    def _on_g_signal(self, proxy, sender, signal, params):
        '''
        DBUS signal Handler
        :param proxy: DBus proxy
        :param sender: DBus Sender
        :param signal: DBus signal
        :param params: DBus signal parameters
        '''
        args = params.unpack() # unpack the glib variant
        if signal == "UpdateProgress":
            self.on_UpdateProgress(*args)
        elif signal == "TransactionEvent":
            self.on_TransactionEvent(*args)
        elif signal == "RPMProgress":
            self.on_RPMProgress(*args)
        else:
            print("Unhandled Signal : "+signal," Param: ",args)

    def on_UpdateProgress(self,name,frac,fread,ftime):
        if name.startswith('repomd'):
            print("repo metadata : %.2f" % frac)
        elif "/" in name:
            repo,file = name.split("/")
            print("getting %s from %s repository : %.2f" % (file,repo,frac))
        else:
            print("downloading : %s %s" % (name,frac))

    def on_TransactionEvent(self,event):
        print("TransactionEvent : %s" % event)

    def on_RPMProgress(self, package, action, te_current, te_total, ts_current, ts_total):
        print("RPMProgress : %s %s" % (action, package))
            
            
    def _handle_dbus_error(self, err):            
        '''
        Parse error from service and raise python Exceptions
        :param err:
        :type err:
        '''
        exc, msg = self._parse_error()
        if exc == DAEMON_ORG+'.AccessDeniedError':
            raise AccessDeniedError(msg)
        elif exc == DAEMON_ORG+'.YumLockedError':
            raise YumLockedError(msg)
        elif exc == DAEMON_ORG+'.YumTransactionError':
            raise YumTransactionError(msg)
        elif exc == DAEMON_ORG+'.YumNotImplementedError':
            raise YumTransactionError(msg)
        else:
            raise YumDaemonError(str(err))
            
    def _parse_error(self):
        '''
        parse values from a DBus releated exception
        '''
        (type, value, traceback) = sys.exc_info()
        res = DBUS_ERR_RE.match(str(value))
        if res:
            return res.groups()
        return "",""       

    def _return_handler(self, obj, result, user_data):
        '''
        Async DBus call, return handler
        :param obj:
        :type obj:
        :param result:
        :type result:
        :param user_data:
        :type user_data:
        '''
        if isinstance(result, Exception):
            #print(result)
            user_data['result'] = None
            user_data['error'] = result
        else:
            user_data['result'] = result
            user_data['error'] = None
        user_data['main_loop'].quit()
        
    def _get_result(self, user_data):
        '''
        Get return data from async call or handle error
        :param user_data:
        :type user_data:
        '''
        if user_data['error']: # Errors
            self._handle_dbus_error(user_data['error'])
        else:
            return user_data['result']
        
    def _run_dbus_async(self, cmd, *args):
        '''
        Make an async call to a DBus method in the yumdaemon service
        :param cmd: method to run
        :type cmd: string
        '''
        main_loop = GObject.MainLoop()
        data = {'main_loop': main_loop}
        func = getattr(self.daemon,cmd)
        func(*args, result_handler=self._return_handler, user_data=data, timeout=60000)
        data['main_loop'].run()
        result = self._get_result(data)
        return result      
        

    def _run_dbus_sync(self, cmd, *args):
        '''
        Make a sync call to a DBus method in the yumdaemon service
        :param cmd:
        :type cmd:
        '''
        func = getattr(self.daemon,cmd)
        return func(*args)
    
    
    def Lock(self):
        '''
        Get the yum lock, this give exclusive access to the daemon and yum
        this must always be called before doing other actions
        '''
        try:
            self.daemon.Lock()
        except Exception as err:
            self._handle_dbus_error(err)

    def Unlock(self):
        '''
        Release the yum lock
        '''
        try:
            self.daemon.Unlock()
        except Exception as err:
            self._handle_dbus_error(err)
        
        
    def GetPackageObjects(self, pkg_filter, fields):
        '''
        Get a list of pkg list for a given package filter  
        each pkg list contains [pkg_id, field,....] where field is a atrribute of the package object  
        Ex. summary, size etc.
        
        :param pkg_filter: package filter ('installed','available','updates','obsoletes','recent','extras')
        :type pkg_filter: string
        :param fields: yum package objects attributes to get.
        :type fields: list of strings
        '''
        result = self._run_dbus_async('GetPackageObjects','(sas)',pkg_filter, fields)
        return json.loads(result)
    

    def GetRepositories(self, repo_filter):
        '''        
        Get a list of repository ids where name matches a filter
        
        :param repo_filter: filter to match
        :return: list of repo id's
        '''
        result = self._run_dbus_async('GetRepositories','(s)',repo_filter)
        return [str(r) for r in result]


    def GetRepo(self, repo_id):
        '''
        Get a dictionary of information about a given repo id.
        
        :param repo_id: repo id to get information from
        :return: dictionary with repo info 
        '''
        result = json.loads(self._run_dbus_async('GetRepo','(s)',repo_id))
        return result

    

    def GetConfig(self, setting):
        '''
        Read a config setting from yum.conf
        :param setting: setting to read
        :type setting: string
        '''
        result = json.loads(self._run_dbus_async('GetConfig','(s)',setting))
        return result
            

    def GetAttribute(self, pkg_id, attr):
        '''
        get yum package attribute (description, filelist, changelog etc)

        :param pkg_id: pkg_id to get attribute from
        :param attr: name of attribute to get
        '''
        result = self._run_dbus_async('GetAttribute','(ss)',pkg_id, attr)
        if result == ':none': # illegal attribute
            result = None
        elif result == ':not_found': # package not found
            result = None # FIXME: maybe raise an exception
        else:
            result = json.loads(result)
        return result

    def GetUpdateInfo(self, pkg_id):
        '''
        Get Updateinfo for a package
        
        :param pkg_id: pkg_id to get update info from
        '''
        result = self._run_dbus_async('GetUpdateInfo','(s)',pkg_id)
        return json.loads(result)

    def GetPackages(self, pkg_filter):
        '''
        Get a list of pkg ids for a given filter (installed, updates ..)
        
        :param pkg_filter: package filter ('installed','available','updates','obsoletes','recent','extras')
        :type pkg_filter: string
        :return: list of pkg_id's
        :rtype: list of strings
        '''
        return self._run_dbus_async('GetPackages','(s)',pkg_filter)


    def GetPackagesByName(self, name, newest_only=True):
        '''
        Get a list of pkg ids for starts with name
        
        :param name: name prefix to match
        :type name: string
        :param newest_only: show only the newest match or every match.
        :type newest_only: boolean
        :return: list of pkg_is's
        '''
        return self._run_dbus_async('GetPackagesByName','(sb)',name, newest_only)


    def ClearTransaction(self):
        '''
        Clear the current transaction
        '''
        return self._run_dbus_async('ClearTransaction')



    def GetTransaction(self):
        '''
        Get the current transaction
        
        :return: the current transaction
        '''
        return self._run_dbus_async('GetTransaction')


    def AddTransaction(self, id, action):
        '''
        Add an package to the current transaction 
        
        :param id: package id for the package to add
        :type id: string
        :param action: the action to perform ( install, update, remove, obsolete, reinstall, downgrade, localinstall )
        :type action: string
        '''
        return self._run_dbus_async('AddTransaction','(ss)',id, action)


    def Install(self, pattern):
        '''
        Do a install <pattern string>, same as yum install <pattern string>
         
        :param pattern: package pattern to install
        :type pattern: string
       '''
        return json.loads(self._run_dbus_async('Install','(s)',pattern))


    def Remove(self, pattern):
        '''
        Do a install <pattern string>, same as yum remove <pattern string>
        
        :param pattern: package pattern to remove
        :type pattern: string
        '''
        return json.loads(self._run_dbus_async('Remove','(s)',pattern))


    def Update(self, pattern):
        '''
        Do a update <pattern string>, same as yum update <pattern string>
        
        :param pattern: package pattern to update
        :type pattern: string

        '''
        return json.loads(self._run_dbus_async('Update','(s)',pattern))


    def Search(self, fields, keys, match_all):
        '''
        Search for packages where keys is matched in fields
        
        :param fields: yum po attributes to search in
        :type fields: list of strings
        :param keys: keys to search for
        :type keys: list of strings
        :param match_all: match all keys or only one
        :type match_all: boolean
        :return: list of pkg_id's
        '''
        return self._run_dbus_async('Search','(asasb)',fields, keys, match_all)


    def GetGroups(self):
        '''
        Get list of Groups
        '''
        return json.loads(self._run_dbus_async('GetGroups'))


    def Reinstall(self, pattern):
        '''
        Do a reinstall <pattern string>, same as yum reinstall <pattern string>
        
        :param pattern: package pattern to reinstall
        :type pattern: string
        
        '''
        return json.loads(self._run_dbus_async('Reinstall','(s)',pattern))


    def Downgrade(self, pattern):
        '''
        Do a install <pattern string>, same as yum remove <pattern string>
        
        :param pattern: package pattern to downgrade
        :type pattern: string
        '''
        return json.loads(self._run_dbus_async('Downgrade','(s)',pattern))



    def BuildTransaction(self):
        '''
        Get a list of pkg ids for the current availabe updates
        '''
        return self._run_dbus_async('BuildTransaction')


    def RunTransaction(self):
        '''
        Get a list of pkg ids for the current availabe updates
        '''
        self._run_dbus_async('RunTransaction')

    
    def Exit(self):
        ''' End the daemon'''
        self._run_dbus_async('Exit')
    

        
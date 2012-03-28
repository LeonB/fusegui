import sys
import os
import subprocess
import ConfigParser
import re
import logging
import logging.handlers
import time
import filesystems
import time
import copy
import gobject
import dbusserver
from dbus.mainloop.glib import DBusGMainLoop
from threading import Timer

class ConfigSection(object):
    config_options = []
    config_values = {}

    def __init__(self):
        self.set_options(self.__class__)

    def get_config_options(self):
        config_options = []
        if self.config_options:
            config_options.extend(self.config_options)
        if self.config_parent:
            config_options.extend(self.config_parent.get_config_options())
        config_options = list(set(config_options))
        return config_options

    def __getattr__(self, attr):
        """_getattr__ only works for stuff not in __dict__"""
        if attr not in self.config_options:
            return getattr(object, attr)

        if attr in self.config_values:
            return self.config_values[attr]

        # if attr == 'host':
        #   print '---------------------------------------'
        #   print '__class__: %s' % self.__class__
        #   print self.config_parent.__class__
        #   print 'attr: %s' % (attr in self.config_parent.config_options)
        #   print self.config_parent.config_options

        if self.config_parent and attr in self.config_parent.config_options:
            return getattr(self.config_parent, attr)

        if attr in self.config_options and not self.config_parent:
            return None

        # print 'key %s: zzzzz' % attr
        # print self.config_values

        # raise AttributeError("type object '%s' has no attribute '%s'" % (self.__class__.__name__, attr))
        return getattr(object, attr)

    def set_options(self, cls):
        if hasattr(cls, 'config_options'):
            self.config_options = copy.copy(getattr(cls, 'config_options'))
        else:
            self.config_options = []

        if hasattr(cls, 'config_values'):
            self.config_values = copy.copy(getattr(cls, 'config_values'))
        else:
            self.config_values = {}

        if hasattr(cls, 'config_parent'):
            self.config_parent = copy.copy(getattr(cls, 'config_parent'))
        else:
            self.config_parent = None

    # def get(self, key):
    #   if key not in self.config_options:
    #       return getattr(self, key)

    #   if key in self.config_values:
    #       return self.config_values[key]

    #   if self.config_parent:
    #       return self.config_parent.get(key)

    #   print 'key %s: zzzzz' % key
    #   print self.config_values

    # def set(self, key, value):
    #   self.config_values[key] = value

    def set_config_parent(self, parent):
        self.config_parent = parent
        for config_item in self.config_options:
            parent.config_options.append(config_item)

class FilesystemConfig(ConfigSection):
    def __init__(self, type):
        ConfigSection.__init__(self)
        module = type
        cls_name = module[:1].upper() + module[1:]

        __import__('fusegui.filesystems.' + module)
        cls = getattr(getattr(filesystems, module), cls_name)
        self.set_options(cls)

class Config(ConfigSection):
    config_options = [
        'basepath'
    ]

    def __init__(self, logger=None, file='defaults.cfg'):
        self.sites = []
        self.filesystems = {}
        self.instance = None
        self.logger = logger
        ConfigSection.__init__(self)
        self.parser = ConfigParser.ConfigParser()
        self.parser.readfp(open(file))

        if self.parser.has_section('Global'):
            for k,v in self.parser.items('Global'):
                setattr(self, k, v)

        section_re = re.compile('^Site (.*)$')  
        for section in self.parser.sections():
            match = section_re.match(section)
            if not match:
                continue

            name = match.groups(0)[0]
            site = Site()
            site.name = name
            site.config = self
            site.logger = self.logger
            site.set_config_parent(self)
            for k,v in self.parser.items('Site %s' % name):
                site.config_values[k] = v

            if site.type not in self.filesystems:
                fs_config = FilesystemConfig(site.type)
                fs_config.set_config_parent(self)
                section_title = 'Filesystem %s' % site.type
                if self.parser.has_section(section_title):
                    for k,v in self.parser.items(section_title):
                        fs_config.config_values[k] = v
                self.filesystems[site.type] = fs_config
            site.set_config_parent(self.filesystems[site.type])

            for config_option in self.filesystems[site.type].config_options:
                if config_option not in site.config_options:
                    site.config_options.append(config_option)

            # self.filesystems['sshfs'].ssh_protocol = 1
            # print self.filesystems['sshfs'].ding
            # site.ssh_protocol = 3
            # print "site.name: %s" % site.name
            # print "site.host: %s" % site.host
            # print "site.type: %s" % site.type
            # print "site.timeout: %s" % site.timeout
            # print "self.basepath: %s" % self.basepath
            # print "site.fuse_mountdir: %s" % site.fuse_mountdir
            # print "filesystem.ssh_protocol: %s" % self.filesystems[site.type].ssh_protocol
            # print "site.ssh_protocol: %s" % site.ssh_protocol

            self.sites.append(site)

    @classmethod
    def getInstance(cls):
        return cls.instance

    def get_site(self, site_name):
        if self.logger: self.logger.error("site_name: %s" % site_name)
        for site in self.sites:
            if site_name == site.name:
                return site

    @property
    def basepath(self,):
        return self.__getattr__('basepath')
    
    @basepath.setter
    def basepath(self, value):
        self.config_values['basepath'] = os.path.expandvars(os.path.expanduser(value))

    @property
    def fuse_mountdir(self,):
        return self.__getattr__('fuse_mountdir')
    
    @fuse_mountdir.setter
    def fuse_mountdir(self, value):
        self.config_values['fuse_mountdir'] = os.path.expandvars(os.path.expanduser(value))

class Filesystem(object):
    logger = None

    def ismounted(self, site):
        return os.path.ismount(site.basepath)

    def mount(self, site):
        """Load type plugin and use that mount() method"""
        self.mkmountpoint(site)
        args = self.cmd_args(site)
        if self.logger: self.logger.error("mount args: %s" % args)
        p = subprocess.Popen(args)
        result = p.wait()
        if result == 0:
            return True
        
        return False

    def mkmountpoint(self, site):
        if not os.path.isdir(site.basepath):
            os.mkdir(site.basepath)

    def unmount(self, site):
        args = ['/bin/fusermount', '-u', '-z',  site.basepath]
        p = subprocess.Popen(args)
        result = p.wait()
        if result == 0:
            return True
        
        return False

class Site(ConfigSection, gobject.GObject):
    config_options = [
        'name',
        'type',
        'timeout',
        'fuse_mountdir',
        'remote_basepath',
        'host',
        'username',
        'password',
    ]

    config_values = {
        'type': 'sshfs',
        'remote_basepath': '/',
        'timeout': 60 #in seconds
    }

    timer = None

    __gsignals__ = {
        "accessed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        "mounted": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        "unmounted": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    def __init__(self):
        super(Site, self).__init__()
        gobject.GObject.__init__(self)

    def update_accesstime(self):
        self.last_accessed = time.time()
        if self.logger: self.logger.error('last_accessed for site %s updated to: %s' % (self.name, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_accessed))))
        self.emit('accessed')
        self.set_timer()
        return self.last_accessed

    def set_timer(self):
        if self.timer:
            self.timer.cancel()
        if self.logger: self.logger.error('Setting timer with timeout: %s' % self.timeout)
        self.timer = Timer(self.timeout, self.timed_out)
        self.timer.start()

    def timed_out(self):
        if self.logger: self.logger.error('Unmounting %s due to timeout' % self.name)
        self.unmount()

    # def get_filesystem(self):
    #   module = self.type
    #   cls = module[:1].upper() + module[1:]

    #   __import__('fusegui.filesystems.' + module)
    #   filesystem = getattr(getattr(filesystems, module), cls)()
        
    #   filesystem.set_config_parent(self.config_parent)
    #   for k,v in self.config.config.items('Filesystem %s' % cls.lower()):
    #       filesystem.set(k, v)
    #   return filesystem

    @property
    def filesystem(self):
        if not 'filesystem' in self.__dict__:
            module = self.type
            cls = module[:1].upper() + module[1:]

            try:
                __import__('fusegui.filesystems.' + module)
            except ImportError:
                return None

            self.__dict__['filesystem'] = getattr(getattr(filesystems, module), cls)()
            self.__dict__['filesystem'].config = self.config
        return self.__dict__['filesystem']

    @property
    def host(self):
        """Wrong attributes called in this won't raise an exception"""
        host = self.__getattr__('host')
        if not host:
            host = self.name
        return host
        
    @host.setter
    def host(self, value):
        """A getter always needs a setter (or else it will be readonly)"""
        self.config_values['host'] = value

    @property
    def basepath(self):
        return self.fuse_mountdir + os.sep + self.name

    @property
    def ismounted(self):
        if 'ismounted' not in self.__dict__:
            self.__dict__['ismounted'] = self.filesystem.ismounted(self)
        return self.__dict__['ismounted']

    def mount(self):
        self.mount_starttime = time.time()
        if self.filesystem.mount(self):
            self.set_timer()
            self.__dict__['ismounted'] = True
            self.emit('mounted')
            return True
        return False

    def unmount(self):
        if self.logger: self.logger.error('Trying to umount %s' % self.name)
        if self.filesystem.unmount(self):
            self.__dict__['ismounted'] = False
            self.emit('unmounted')
            return True
        return False

    def __del__(self):
        if self.logger: self.logger.error('destroying site!!')
        if self.ismounted():
            self.unmount()

class Logger(object):
    instance = None

    class StdoutFilter(logging.Filter):
        def filter(self, record):
            return record.levelno < logging.ERROR

    def __init__(self, **kwargs):
        self.logger = logging.getLogger("FuseGUI")
        self.logger.setLevel(logging.DEBUG)

        slh = logging.handlers.SysLogHandler(address='/dev/log', facility=logging.handlers.SysLogHandler.LOG_MAIL)
        slh.setFormatter(logging.Formatter('%(name)s[%(process)d]: %(message)s'))
        slh.setLevel(logging.__getattribute__(kwargs['log_level'].upper()))
        self.logger.addHandler(slh)

        if not kwargs['quiet']:
            she = logging.StreamHandler(sys.stderr)
            she.setLevel(logging.ERROR)
            self.logger.addHandler(she)

            sho = logging.StreamHandler(sys.stdout)
            sho.setLevel(40-kwargs['verbosity']*10)
            sho.addFilter(self.StdoutFilter())
            self.logger.addHandler(sho)

    @classmethod
    def getInstance(cls):
        return cls.instance

    def debug(self, msg, *args, **kwargs):
        return self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        return self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        return self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        return self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        return self.logger.critical(msg, *args, **kwargs)

class Director(object):
    dbus_objects = {}

    def run(self):
        if self.logger: self.logger.error('Starting Director')

        config = self.config
        DBusGMainLoop(set_as_default=True)

        for site in config.sites:
            if self.logger: self.logger.error("adding %s to dbus server" % site.name)
            self.dbus_objects[site.name] = dbusserver.Site(site)

        mainloop = gobject.MainLoop()

        try:
            mainloop.run()
        except KeyboardInterrupt:
            pass
        
        if self.logger: self.logger.error('Stopping mainloop of Director')
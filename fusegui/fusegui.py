import sys
import os, stat, errno
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
import threading
import fuse

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

        if self.config_parent and attr in self.config_parent.config_options:
            return getattr(self.config_parent, attr)

        if attr in self.config_options and not self.config_parent:
            return None

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
        'timeout': 600 #in seconds
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
        self.timer = threading.Timer(self.timeout, self.timed_out)
        self.timer.start()

    def timed_out(self):
        if self.logger: self.logger.error('Unmounting %s due to timeout' % self.name)
        self.unmount()

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

class FuseFilesystem(fuse.LoggingMixIn, fuse.Operations):
    logger = None
    config = None

    def __init__(self):
        self.rwlock = threading.Lock()

    def _stat_to_dict(self, st):
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                    'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def get_real_path(self, path):
        return self.config.fuse_mountdir + path

    def get_site(self, path):
        if path[:len(self.config.fuse_mountdir)] != self.config.fuse_mountdir:
            return

        if path == self.config.fuse_mountdir + os.sep:
            return None

        site_name = path[len(self.config.fuse_mountdir):]
        site_name = site_name.lstrip(os.path.sep).split(os.path.sep)[0]

        if self.logger: self.logger.debug('site_name: %s' % site_name)
        for site in self.config.sites:
            if site.name == site_name:
                return site


    ### Start filesystem methodss ###

    def getattr(self, path, fh=None):
        if self.logger: self.logger.error("getattr: %s" % path)
        path = self.get_real_path(path)
        if self.logger: self.logger.error('path: %s' % path)
        site = self.get_site(path)

        if not site:
            if self.logger: self.logger.debug('getattr: no site found for %s' % path)
            return self._stat_to_dict(os.lstat(path))
        else:
            if site and not site.ismounted and path == site.basepath:
                if not os.path.isdir(site.basepath):
                    os.mkdir(site.basepath)
                return self._stat_to_dict(os.lstat(path))
            elif site and not site.ismounted:
                if self.logger: self.logger.error("Trying to mount %s" % site.basepath)
                p = site.mount()
                if self.logger: self.logger.error('p: %s' % p)
            else:
                self.logger.debug('getattr: site already mounted')

            site.update_accesstime()
            return self._stat_to_dict(os.lstat(path))

    def readlink(self, path):
        if self.logger: self.logger.error("readlink: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        return os.readlink(path)

    def open(self, path, flags):
        if self.logger: self.logger.error("open: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        return os.open(path, flags)

    def read(self, path, size, offset, fh):
        if self.logger: self.logger.error("read: %s" % path)
        site = self.get_site(path)
        if site: site.update_accesstime()

        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.read(fh, size)

    def readdir(self, path, offset):
        if self.logger: self.logger.error("readdir: %s" % path)

        # If not a subdirector: return all sitenames as directory
        if path == '/':
            return ['.', '..'] + map(lambda x: x.name, self.config.sites)

        path = self.get_real_path(path)
        site = self.get_site(path)
        if self.logger: self.logger.error("site: %s" % site)
        if site and not site.ismounted:
            site.mount()

        if self.logger: self.logger.error("site.basepath: %s" % site.basepath)
        for e in os.listdir(site.basepath):
            self.logger.error('listdir e: %s' % e)
            return os.listdir(path)

    def unlink(self, path):
        if self.logger: self.logger.error("unlink: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.unlink(path)

    def rmdir(self, path):
        if self.logger: self.logger.error("rmdir: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.rmdir(path)

    def symlink(self, path1, path2):
        if self.logger: self.logger.debug("symlink: %s, %s" % (path1, path2))
        path1 = self.get_real_path(path1)
        site1 = self.get_site(path1)
        if site1: site1.update_accesstime()
        path2 = self.get_real_path(path2)
        site2 = self.get_site(path2)
        if site2: site2.update_accesstime()
        os.symlink(path1, path2)

    def rename(self, path1, path2):
        if self.logger: self.logger.debug("rename: %s, %s" % (path1, path2))
        path1 = self.get_real_path(path1)
        site1 = self.get_site(path1)
        if site1: site1.update_accesstime()
        path2 = self.get_real_path(path2)
        site2 = self.get_site(path2)
        if site2: site2.update_accesstime()
        os.rename(path1, path2)

    def link(self, path1, path2):
        if self.logger: self.logger.debug("link: %s, %s" % (path1, path2))
        path1 = self.get_real_path(path1)
        site1 = self.get_site(path1)
        if site1: site1.update_accesstime()
        path2 = self.get_real_path(path2)
        site2 = self.get_site(path2)
        if site2: site2.update_accesstime()
        os.link(path1, "." + path2)

    def chmod(self, path, mode):
        if self.logger: self.logger.debug("chmod: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.chmod(path, mode)

    def chown(self, path, user, group):
        if self.logger: self.logger.error("chown: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.chown(path, user, group)

    def truncate(self, path, len):
        if self.logger: self.logger.debug("truncate: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        f = open(path, "a")
        f.truncate(len)
        f.close()

    def mknod(self, path, mode, dev):
        if self.logger: self.logger.debug("mknod: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.mknod(path, mode, dev)

    def mkdir(self, path, mode):
        if self.logger: self.logger.debug("mkdir: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.mkdir(path, mode)

    def utime(self, path, times):
        if self.logger: self.logger.debug("utime: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        os.utime(path, times)

    def access(self, path, mode):
        if self.logger: self.logger.debug("access: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()

        if not os.access(path, mode):
            return -errno.EACCES

    #def create(self, path, mode, fip):
    def create(self, path, mode):
        if self.logger: self.logger.debug("create: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()
        return os.open(path, os.O_WRONLY | os.O_CREAT, mode)

    def write(self, path, data, offset, fh):
        if self.logger: self.logger.debug("write: %s" % path)
        path = self.get_real_path(path)
        site = self.get_site(path)
        if site: site.update_accesstime()

        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.write(fh, data)

#    This is how we could add stub extended attribute handlers...
#    (We can't have ones which aptly delegate requests to the underlying fs
#    because Python lacks a standard xattr interface.)
#
#    def getxattr(self, path, name, size):
#        val = name.swapcase() + '@' + path
#        if size == 0:
#            # We are asked for size of the value.
#            return len(val)
#        return val
#
#    def listxattr(self, path, size):
#        # We use the "user" namespace to please XFS utils
#        aa = ["user." + a for a in ("foo", "bar")]
#        if size == 0:
#            # We are asked for size of the attr list, ie. joint size of attrs
#            # plus null separators.
#            return len("".join(aa)) + len(aa)
#        return aa

    def statfs(self, path):
        """
        Should return an object with statvfs attributes (f_bsize, f_frsize...).
        Eg., the return value of os.statvfs() is such a thing (since py 2.2).
        If you are not reusing an existing statvfs object, start with
        fuse.StatVFS(), and define the attributes.

        To provide usable information (ie., you want sensible df(1)
        output, you are suggested to specify the following attributes:

            - f_bsize - preferred size of file blocks, in bytes
            - f_frsize - fundamental size of file blcoks, in bytes
                [if you have no idea, use the same as blocksize]
            - f_blocks - total number of blocks in the filesystem
          - f_bfree - number of free blocks
            - f_files - total number of file inodes
            - f_ffree - nunber of free file inodes
        """

        # This really doesn't do anything, it stats self.config.fuse_mountdir
        if self.logger: self.logger.debug("statfs: %s" % path)
        stv = os.statvfs(path)

        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def __del__(self):
        if self.logger: self.logger.error("__del__")
        # Check every site and unmount it if needed
        for site in self.config.sites:
            if self.logger: self.logger.error('%s mounted: %s' % (site.name, site.ismounted))
            if site.ismounted:
                site.unmount()

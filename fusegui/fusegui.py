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

class FuseGUI(object):
	pass

class Config(object):
	def __init__(self):
		self.sites = []
		self.fuse_mountdir = None
		self.basepath = None

		config = ConfigParser.ConfigParser()
		config.readfp(open('defaults.cfg'))

		section_re = re.compile('^Site (.*)$')	
		for section in config.sections():
			match = section_re.match(section)
			if not match:
				continue

			site = Site(match.groups(0)[0])
			self.sites.append(site)
		
		if config.has_section('Global'):
			for k,v in config.items('Global'):
				if hasattr(self, k):
					setattr(self, k, v)

	@property
	def basepath(self):
		return self.__dict__['basepath']

	@basepath.setter
	def basepath(self, value):
		if value:
			value = os.path.expandvars(os.path.expanduser(value))
		self.__dict__['basepath'] = value

	@property
	def fuse_mountdir(self):
		return self.__dict__['fuse_mountdir']

	@fuse_mountdir.setter
	def fuse_mountdir(self, value):
		if value:
			value = os.path.expandvars(os.path.expanduser(value))
		self.__dict__['fuse_mountdir'] = value

	def get_site(self, site_name):
		Logger.getInstance().error("site_name: %s" % site_name)
		for site in self.sites:
			if site.name == site_name:
				return site

class Site(object):
	type = 'sshfs'
	basepath = '~/.fuse/'
	remote_basepath = ''
	timeout = None
	mount_starttime = None

	def __init__(self, name):
		self.name = name
		self.host = self.name
		self.basepath = os.path.expandvars(os.path.expanduser(self.basepath))

		module = self.type
		cls = self.type[0].upper() + self.type[1:]

		__import__('fusegui.filesystems.' + module)
		self.filesystem = getattr(getattr(filesystems, module), cls)

	def mounted(self):
		return self.filesystem.ismounted(self)

	def mount(self):
		self.mount_starttime = time.time()
		return self.filesystem.mount(self)

	def unmount(self):
		return self.filesystem.unmount(self)

	def __del__(self):
		print 'destroying site!!'
		if self.mounted():
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

class Filesystem(object):
	@classmethod
	def ismounted(self, site):
		return os.path.ismount(site.basepath + site.name)

	@classmethod
	def unmount(self, site):
		args = ['/bin/fusermount', '-u', '-z',  site.basepath + site.name]
		p = subprocess.Popen(args)
		p.wait()
		os.rmdir(site.basepath + site.name)
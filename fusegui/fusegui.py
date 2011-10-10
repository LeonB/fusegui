import sys
import os
import ConfigParser
import re
import logging
import logging.handlers
import subprocess
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
	type = 'sftp'
	basepath = '~/.fuse/'
	remote_basepath = ''
	timeout = None

	def __init__(self, name):
		self.name = name
		self.host = self.name
		self.basepath = os.path.expandvars(os.path.expanduser(self.basepath))

	def mounted(self):
		# Logger.getInstance().error(self.basepath + self.name)
		# Logger.getInstance().error(os.path.ismount(self.basepath + self.name))
		return os.path.ismount(self.basepath + self.name)

	def mount(self):
		"""Load type plugin and use that mount() method"""
		if not os.path.isdir(self.basepath + self.name):
			os.mkdir(self.basepath + self.name)
		args = ['/usr/bin/sshfs', self.host + ':' + self.remote_basepath, 
								self.basepath + self.name]
		# Logger.getInstance().error("args: %s" % args)
		p = subprocess.Popen(args)
		return p.wait()

	def unmount(self):
		args = ['/bin/fusermount', '-u', '-z',  self.basepath + self.name]
		p = subprocess.Popen(args)
		p.wait()
		os.rmdir(self.basepath + self.name)

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

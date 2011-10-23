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

class ConfigSection(object):
	def __init__(self):
		self.set_options(self.__class__)

	def set_options(self, cls):
		if hasattr(cls, 'config_options'):
			self.config_options = getattr(cls, 'config_options')
		else:
			self.config_options = []

		if hasattr(cls, 'config_values'):
			self.config_values = getattr(cls, 'config_values')
		else:
			self.config_values = {}

		if hasattr(cls, 'config_parent'):
			self.config_parent = getattr(cls, 'config_parent')
		else:
			self.config_parent = None

	def get(self, key):
		if key not in self.config_options:
			return getattr(self, key)

		if key in self.config_values:
			return self.config_values[key]

		if self.config_parent:
			return self.config_parent.get(key)

		print 'key %s: zzzzz' % key
		print self.config_values

	def set(self, key, value):
		self.config_values[key] = value

	def set_config_parent(self, parent):
		self.config_parent = parent
		for config_item in self.config_options:
			parent.config_options.append(config_item)

class FilesystemConfig(ConfigSection):
	def __init__(self, type):
		module = type
		cls_name = module[:1].upper() + module[1:]

		__import__('fusegui.filesystems.' + module)
		cls = getattr(getattr(filesystems, module), cls_name)
		self.set_options(cls)

		

class Config(ConfigSection):
	config_options = [
		'basepath'
	]
	sites = []
	filesystems = {}

	def __init__(self):
		ConfigSection.__init__(self)
		self.parser = ConfigParser.ConfigParser()
		self.parser.readfp(open('defaults.cfg'))

		if self.parser.has_section('Global'):
			for k,v in self.parser.items('Global'):
				self.set(k, v)

		section_re = re.compile('^Site (.*)$')	
		for section in self.parser.sections():
			match = section_re.match(section)
			if not match:
				continue

			name = match.groups(0)[0]
			site = Site()
			site.name = name
			site.set_config_parent(self)
			for k,v in self.parser.items('Site %s' % name):
				site.set(k, v)

			if site.get('type') not in self.filesystems:
				fs_config = FilesystemConfig(site.get('type'))
				fs_config.set_config_parent(self)
				section_title = 'Filesystem %s' % site.get('type')
				if self.parser.has_section(section_title):
					for k,v in self.parser.items(section_title):
						fs_config.set(k, v)
				self.filesystems[site.get('type')] = fs_config
			site.set_config_parent(self.filesystems[site.get('type')])

			for config_option in self.filesystems[site.get('type')].config_options:
				if config_option not in site.config_options:
					site.config_options.append(config_option)

			self.filesystems['sshfs'].set('ssh_protocol', 1)
			site.set('ssh_protocol', 3)
			print "site.name: %s" % site.get('name')
			print "site.host: %s" % site.get('host')
			print "site.type: %s" % site.get('type')
			print "site.timeout: %s" % site.get('timeout')
			print "self.basepath: %s" % self.get('basepath')
			print "site.fuse_mountdir: %s" % site.get('fuse_mountdir')
			print "filesystem.ssh_protocol: %s" % self.filesystems[site.get('type')].get('ssh_protocol')
			print "site.ssh_protocol: %s" % site.get('ssh_protocol')
			import sys
			sys.exit(12)

			self.sites.append(site)

	def get_site(self, site_name):
		Logger.getInstance().error("site_name: %s" % site_name)
		for site in self.sites:
			if site.name == site_name:
				return site

class Filesystem(object):
	def ismounted(self, site):
		return os.path.ismount(site.basepath + os.sep + site.name)

	def mount(self, site):
		"""Load type plugin and use that mount() method"""
		self.mkmountpoint(site)
		args = self.cmd_args(site)
		p = subprocess.Popen(args)
		return p.wait()

	def mkmountpoint(self, site):
		if not os.path.isdir(site.basepath + os.sep + site.name):
			os.mkdir(site.basepath + os.sep + site.name)

	def unmount(self, site):
		args = ['/bin/fusermount', '-u', '-z',  site.basepath + os.sep + site.name]
		p = subprocess.Popen(args)
		p.wait()
		os.rmdir(site.basepath + os.sep + site.name)

class Site(ConfigSection):
	config_options = [
		'type',
		'timeout',
		'fuse_mountdir',
		'host',
	]

	# def get_filesystem(self):
	# 	module = self.get('type')
	# 	cls = module[:1].upper() + module[1:]

	# 	__import__('fusegui.filesystems.' + module)
	# 	filesystem = getattr(getattr(filesystems, module), cls)()
		
	# 	filesystem.set_config_parent(self.config_parent)
	# 	for k,v in self.config.config.items('Filesystem %s' % cls.lower()):
	# 		filesystem.set(k, v)
	# 	return filesystem

	def mounted(self):
		return self.filesystem.ismounted(self)

	def mount(self):
		self.mount_starttime = time.time()
		return self.filesystem.mount(self)

	def unmount(self):
		return self.filesystem.unmount(self)

	# def __del__(self):
	# 	# print 'destroying site!!'
	# 	# if self.mounted():
	# 	# 	self.unmount()

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
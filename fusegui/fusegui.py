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

	def __getattr__(self, attr):
		"""_getattr__ only works for stuff not in __dict__"""
		if attr not in self.config_options:
			return getattr(object, attr)

		if attr in self.config_values:
			return self.config_values[attr]

		# if attr == 'host':
		# 	print '---------------------------------------'
		# 	print '__class__: %s' % self.__class__
		# 	print self.config_parent.__class__
		# 	print 'attr: %s' % (attr in self.config_parent.config_options)
		# 	print self.config_parent.config_options

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

	# def get(self, key):
	# 	if key not in self.config_options:
	# 		return getattr(self, key)

	# 	if key in self.config_values:
	# 		return self.config_values[key]

	# 	if self.config_parent:
	# 		return self.config_parent.get(key)

	# 	print 'key %s: zzzzz' % key
	# 	print self.config_values

	# def set(self, key, value):
	# 	self.config_values[key] = value

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
	sites = []
	filesystems = {}
	instance = None

	def __init__(self):
		ConfigSection.__init__(self)
		self.parser = ConfigParser.ConfigParser()
		self.parser.readfp(open('defaults.cfg'))

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
			site.set_config_parent(self)
			for k,v in self.parser.items('Site %s' % name):
				setattr(site, k, v)

			if site.type not in self.filesystems:
				fs_config = FilesystemConfig(site.type)
				fs_config.set_config_parent(self)
				section_title = 'Filesystem %s' % site.type
				if self.parser.has_section(section_title):
					for k,v in self.parser.items(section_title):
						setattr(fs_config, k, v)
				self.filesystems[site.type] = fs_config
			site.set_config_parent(self.filesystems[site.type])

			for config_option in self.filesystems[site.type].config_options:
				if config_option not in site.config_options:
					site.config_options.append(config_option)

			self.filesystems['sshfs'].ssh_protocol = 1
			site.ssh_protocol = 3
			print "site.name: %s" % site.name
			print "site.host: %s" % site.host
			print "site.type: %s" % site.type
			print "site.timeout: %s" % site.timeout
			print "self.basepath: %s" % self.basepath
			print "site.fuse_mountdir: %s" % site.fuse_mountdir
			print "filesystem.ssh_protocol: %s" % self.filesystems[site.type].ssh_protocol
			print "site.ssh_protocol: %s" % site.ssh_protocol

			self.sites.append(site)
		import sys
		sys.exit(12)

	@classmethod
	def getInstance(cls):
		return cls.instance

	def get_site(self, site_name):
		Logger.getInstance().error("site_name: %s" % site_name)
		for site in self.sites:
			if site_name == site.name:
				return site

class Filesystem(object):
	def ismounted(self, site):
		return os.path.ismount(site.config.basepath + os.sep + site.name)

	def mount(self, site):
		"""Load type plugin and use that mount() method"""
		self.mkmountpoint(site)
		args = self.cmd_args(site)
		p = subprocess.Popen(args)
		return p.wait()

	def mkmountpoint(self, site):
		if not os.path.isdir(site.config.basepath + os.sep + site.name):
			os.mkdir(site.config.basepath + os.sep + site.name)

	def unmount(self, site):
		args = ['/bin/fusermount', '-u', '-z',  site.config.basepath + os.sep + site.name]
		p = subprocess.Popen(args)
		p.wait()
		os.rmdir(site.config.basepath + os.sep + site.name)

class Site(ConfigSection):
	config_options = [
		'type',
		'timeout',
		'fuse_mountdir',
		'host',
	]

	# def get_filesystem(self):
	# 	module = self.type
	# 	cls = module[:1].upper() + module[1:]

	# 	__import__('fusegui.filesystems.' + module)
	# 	filesystem = getattr(getattr(filesystems, module), cls)()
		
	# 	filesystem.set_config_parent(self.config_parent)
	# 	for k,v in self.config.config.items('Filesystem %s' % cls.lower()):
	# 		filesystem.set(k, v)
	# 	return filesystem

	@property
	def filesystem(self):
		if not 'filesystem' in self.__dict__:
			module = self.type
			cls = module[:1].upper() + module[1:]

			__import__('fusegui.filesystems.' + module)
			self.__dict__['filesystem'] = getattr(getattr(filesystems, module), cls)()
			self.__dict__['filesystem'].config = self.config
		return self.__dict__['filesystem']

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
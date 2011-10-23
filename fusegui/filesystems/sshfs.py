import fusegui
import os
import subprocess

class Sshfs(fusegui.Filesystem):
	config_options = [
		'ssh_protocol',
		'commandline_args'
	]

	def cmd_args(self, site):
		return ['/usr/bin/sshfs', site.host + ':' + site.remote_basepath, 
			site.config.basepath + os.sep + site.name]
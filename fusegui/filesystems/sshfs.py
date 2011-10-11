import fusegui
import os
import subprocess

class Sshfs(fusegui.Filesystem):
	def cmd_args(self, site):
		return ['/usr/bin/sshfs', site.host + ':' + site.remote_basepath, 
			site.basepath + os.sep + site.name]
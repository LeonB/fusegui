import fusegui
import os
import subprocess

class Sshfs(fusegui.Filesystem):

	@classmethod
	def mount(self, site):
		"""Load type plugin and use that mount() method"""
		if not os.path.isdir(site.basepath + site.name):
			os.mkdir(site.basepath + site.name)
		args = ['/usr/bin/sshfs', site.host + ':' + site.remote_basepath, 
								site.basepath + site.name]
		p = subprocess.Popen(args)
		return p.wait()
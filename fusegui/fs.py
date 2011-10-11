#!/usr/bin/env python

# @todo: make something like _fix_path()?
# @todo: gnome-keyring integration (password, gnome-keyring, just try (ssh key))
# @todo: timeout (and keep it with site?)

import os, stat, errno
import fuse
from fuse import Fuse

fuse.fuse_python_api = (0, 2)

class MountDir(Fuse):
    def getattr(self, path):
        if self.logger: self.logger.error("getattr: %s" % path)
        
        if path == '/':
            return os.lstat("." + path)
        else:
            redir_path = self.config.fuse_mountdir + path
            if self.logger: self.logger.error("redir_path: %s" % redir_path)
            site = self.config.get_site(path.lstrip(os.path.sep).split(os.path.sep)[0])
            if self.logger: self.logger.error('site: %s' % site)

            # als path == '/$site' dan niet getattr'en maar iets anders...?
            if site and not site.mounted() and path == '/%s' % site.name:
                return os.lstat("./")
            elif site and not site.mounted():
                if self.logger: self.logger.error("Trying to mount %s" % site.basepath + os.sep + site.name)
                p = site.mount()
                if self.logger: self.logger.error('p: %s' % p)

            return os.lstat(redir_path)

    def readlink(self, path):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path

        return os.readlink(path)

    def readdir(self, path, offset):
        if self.logger: self.logger.error("readdir: %s" % path)

        if path == '/':
            for site in self.config.sites:
                yield fuse.Direntry(site.name)
        else:
            site = self.config.get_site(path.lstrip(os.path.sep).split(os.path.sep)[0])
            if site and not site.mounted():
                p = site.mount()

            for e in os.listdir(self.config.fuse_mountdir + path):
                self.logger.error('listdir e: %s' % e)
                yield fuse.Direntry(e)

    def unlink(self, path): 
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
            
        os.unlink(path)

    def rmdir(self, path):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
            
        os.rmdir(path)

    def symlink(self, path, path1):
        if path1 == '/':
            path1 = './'
        else:
            path1 = self.config.fuse_mountdir + path
            
        os.symlink(path, path1)

    def rename(self, path, path1):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path

        if path1 == '/':
            path1 = './'
        else:
            path1 = self.config.fuse_mountdir + path1

        os.rename(path, path1)

    def link(self, path, path1):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path

        os.link(path, "." + path1)

    def chmod(self, path, mode):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
            
        os.chmod(path, mode)

    def chown(self, path, user, group):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
            
        os.chown(path, user, group)

    def truncate(self, path, len):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
            
        f = open(path, "a")
        f.truncate(len)
        f.close()

    def mknod(self, path, mode, dev):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
        os.mknod(path, mode, dev)

    def mkdir(self, path, mode):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path

        os.mkdir(path, mode)

    def utime(self, path, times):
        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path
            
        os.utime(path, times)

#    The following utimens method would do the same as the above utime method.
#    We can't make it better though as the Python stdlib doesn't know of
#    subsecond preciseness in acces/modify times.
#  
#    def utimens(self, path, ts_acc, ts_mod):
#      os.utime("." + path, (ts_acc.tv_sec, ts_mod.tv_sec))

    def access(self, path, mode):
        if self.logger: self.logger.error("access: %s" % path)

        if path == '/':
            path = './'
        else:
            path = self.config.fuse_mountdir + path

        if not os.access(path, mode):
            return -errno.EACCES

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

    def statfs(self):
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

        return os.statvfs(".")

    def fsinit(self):
        # os.chdir(self.root)
        if self.logger: self.logger.error("fsinit")

    def fsdestroy(self, data = None):
        # del self.config.sites #make sure __del__ is called
        for site in self.config.sites:
            if site.mounted():
                site.unmount()
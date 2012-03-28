from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
import os, stat, errno
import fusegui

class Mountdir(LoggingMixIn, Operations):
    logger = None
    config = None

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

    def __del__(self):
        if self.logger: self.logger.error("__del__")
        # Check every site and unmount it if needed
        for site in self.config.sites:
            if self.logger: self.logger.error('%s mounted: %s' % (site.name, site.ismounted))
            if site.ismounted:
                site.unmount()
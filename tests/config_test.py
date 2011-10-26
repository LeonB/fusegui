import fusegui
import unittest
import os

class ConfigTest(unittest.TestCase):

    def setUp(self):
        self.config = fusegui.Config('tests/test.cfg')
        fusegui.Logger.instance = fusegui.Logger(log_level='error', quiet=True, verbosity=40)

    def testGlobalConfig(self):
        config = self.config
        self.assertEqual(config.timeout, '3600')
        self.assertEqual(config.basepath, os.path.expanduser('~/sites'))
        self.assertEqual(config.fuse_mountdir, os.path.expanduser('~/.fuse'))
        self.assertEqual(config.type, 'sshfs')

    def testSshfsConfig(self):
        fs = self.config.filesystems['sshfs']
        self.assertEqual(fs.timeout, '360')
        self.assertEqual(fs.ssh_protocol, '2')

        try:
            fs.ding
            self.fail( "Should have raised an exception" )
        except Exception, e:
            self.assertEquals(e.__class__, AttributeError)

    def testVerySimpleSite(self):
        site = self.config.get_site('verysimple')
        self.assertEqual(self.config.type, site.type)
        self.assertEqual(site.name, site.host)
        self.assertEqual(site.timeout, self.config.filesystems[site.type].timeout)
        self.assertEqual(site.ssh_protocol, self.config.filesystems[site.type].ssh_protocol)
        self.assertEqual(site.username, None)
        self.assertEqual(site.password, None)

        self.assertRaises(AttributeError, getattr, site, 'doesnotexist')
        self.assertEqual(getattr(site, 'username'), None)
        try:
            site.doesnotexist
            self.fail( "Should have raised an exception" )
        except Exception, e:
            self.assertEquals(e.__class__, AttributeError)

    def testSimpleSite(self):
        site = self.config.get_site('simple')
        self.assertEqual(self.config.type, site.type)
        self.assertNotEqual(site.name, site.host)
        self.assertEqual(site.host, 'simple.com')
        self.assertEqual(site.timeout, self.config.filesystems[site.type].timeout)
        self.assertEqual(site.ssh_protocol, self.config.filesystems[site.type].ssh_protocol)
        self.assertEqual(site.username, None)
        self.assertEqual(site.password, None)

        try:
            site.doesnotexist
            self.fail( "Should have raised an exception" )
        except Exception, e:
            self.assertEquals(e.__class__, AttributeError)

    def testAdvancedSite(self):
        site = self.config.get_site('advanced')
        self.assertEqual(self.config.type, site.type)
        self.assertNotEqual(site.name, site.host)
        self.assertEqual(site.host, 'www.kernel.org')
        self.assertEqual(site.timeout, self.config.filesystems[site.type].timeout)
        self.assertEqual(site.ssh_protocol, '1')
        self.assertEqual(site.username, 'linus')
        self.assertEqual(site.password, 'torvalds')

        try:
            site.doesnotexist
            self.fail( "Should have raised an exception" )
        except Exception, e:
            self.assertEquals(e.__class__, AttributeError)

        self.assertEqual(site.remote_basepath, 'public_html')
        self.assertEqual(site.commandline_args, '-o blaat -o pietje=ditje?')

if __name__ == "__main__":
    unittest.main()
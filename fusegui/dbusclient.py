import dbus
import re
import os

class Site(object):
    bus = None
    site = None
    properties = []

    @classmethod
    def get_by_name(cls, site_name, bus):
        try:
            return Site(site_name, bus)
        except dbus.exceptions.DBusException:
            return None

    def __init__(self, site_name, bus):
        dbus_path = '/org/fusegui/sites/%s' % re.sub('[^a-zA-Z0-9]', '_', site_name)
        site = bus.get_object('org.fusegui', dbus_path)

        for k, v in site.GetAll('org.fusegui.site').items():
            #self.properties.append(property)
            if v.__class__ == dbus.String:
                v = v.encode('ascii')
            if v.__class__ == dbus.Int32:
                v = int(v)
            setattr(self, k, v)

        "Adding signal receiver for %s" % site_name
        bus.add_signal_receiver(self.site_mount_status_changed, 
            dbus_interface=dbus.PROPERTIES_IFACE, 
            signal_name="PropertiesChanged", 
            bus_name="org.fusegui", 
            path=dbus_path)

        self.bus = bus
        self.site = site

    # def __getattr__(self, attr):
    #     if attr in self.properties:
    #         return self.site.Get('org.fusegui.site', attr)

    #     return object.__getattr__(attr)

    def site_mount_status_changed(self, interface_name, changed_properties,
                          invalidated_properties):
        print 'site_mount_status_changed!!'
        self.ismounted = changed_properties['ismounted']

    def update_accesstime(self):
        return self.site.update_accesstime()
        
    def mount(self):
        return self.site.mount()
        
    def unmount(self):
        return self.site.unmount()

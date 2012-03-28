import dbus
import dbus.service
import re

class DBUSObjectWithProperties(dbus.service.Object):
    """Properties stuff"""
    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        return self.GetAll(interface_name)[property_name]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name == 'org.fusegui.site':
            attributes = {}
            for attribute in self.attributes:
                value = getattr(self, attribute)
                if value == None: value = ''
                attributes[attribute] = value
            return attributes
        else:
            raise dbus.exceptions.DBusException(
                'com.example.UnknownInterface',
                'The Foo object does not implement the %s interface'
                    % interface_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ssv')
    def Set(self, interface_name, property_name, new_value):
        setattr(self, property_name, new_value)
        self.PropertiesChanged(interface_name,
            { property_name: new_value }, [])

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        pass

class Site(DBUSObjectWithProperties):
    def __init__(self, site):
        self.site = site
        self.attributes = site.get_config_options()
        self.attributes.append('ismounted')
        path = '/org/fusegui/sites/%s' % re.sub('[^a-zA-Z0-9]', '_', site.name)
        bus_name = dbus.service.BusName('org.fusegui', bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, path)

        self.site.connect('mounted', self.site_mount_status_changed)
        self.site.connect('unmounted', self.site_mount_status_changed)

    def __getattr__(self, attr):
        if attr in self.attributes:
            return getattr(self.site, attr)

        return getattr(DBUSObjectWithProperties, attr)

    def site_mount_status_changed(self, site):
        print 'mount status changed to: %s' % site.ismounted
        self.PropertiesChanged('org.fusegui.site',
            { 'ismounted': site.ismounted }, [])

    @dbus.service.method('org.fusegui.site')
    def update_accesstime(self):
        return self.site.update_accesstime()

    # @dbus.service.method('org.fusegui.site')
    # def ismounted(self):
    #     return self.site.ismounted()
        
    @dbus.service.method('org.fusegui.site')
    def mount(self):
        return self.site.mount()
        
    @dbus.service.method('org.fusegui.site')
    def unmount(self):
        return self.site.unmount()

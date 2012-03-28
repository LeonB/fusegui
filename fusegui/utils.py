import threading
import multiprocessing
import gobject
import time

class Thread(threading.Thread):
	"""Thread class with a stop() method. The thread itself has to check
	regularly for the stopped() condition."""

	def __init__(self):
		super(Thread, self).__init__()
		self.stop_request = threading.Event()

	def stop(self):
		self.stop_request.set()

class Process(multiprocessing.Process, gobject.GObject):
    __gsignals__ = {
        "started": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        "stopped": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, *args, **kwargs):
        multiprocessing.Process.__init__(self, *args, **kwargs)
        gobject.GObject.__init__(self)
        self.stop_request = multiprocessing.Event()

    # def start(self):
    #     def _start():
    #         def _start2():
    #             print '_start2'
    #             multiprocessing.Process.start(self)
    #             self.emit('started')
    #             self.join()
    #             self.stop_request.set()

    #         t = threading.Thread(target=_start2)
    #         print 'starting thread 2'
    #         t.start()

    #         self.stop_request.wait()

    #         self.emit('stopped')

    #     print 'starting thread 1'
    #     self.t = threading.Thread(target=_start)
    #     print 'starting thread'
    #     self.t.start()
    #     print 'thread started'

    def start(self):
        def _start():
            multiprocessing.Process.start(self)
            self.emit('started')
            self.join()
            self.emit('stopped')

        print 'starting thread 1'
        self.t = threading.Thread(target=_start)
        print 'starting thread'
        self.t.start()
        print 'thread started'

    def stop(self):
        self.stop_request.set()
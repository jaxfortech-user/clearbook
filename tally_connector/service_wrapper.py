"""
Clearbook Tally Connector — Windows Service Wrapper.
Installs and runs the connector as a Windows service using pywin32.

Usage (run as Administrator):
  python service_wrapper.py install
  python service_wrapper.py start
  python service_wrapper.py stop
  python service_wrapper.py remove
"""

import asyncio
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

from connector import run_connector


class TallyConnectorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ClearbookTallyConnector"
    _svc_display_name_ = "Clearbook Tally Connector"
    _svc_description_ = (
        "Maintains a persistent WebSocket tunnel between TallyPrime "
        "and the Clearbook cloud platform."
    )

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        asyncio.run(run_connector())


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Called by the Windows Service Manager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TallyConnectorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Called from command line: install / start / stop / remove
        win32serviceutil.HandleCommandLine(TallyConnectorService)
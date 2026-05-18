
import win32com.client
import logging
import time
from datetime import datetime

class NativeWMIHandler:
    def __init__(self, target_ip, username, password):
        self.target_ip = target_ip
        self.username = username
        self.password = password
        self.locator = None
        self.service = None

    def connect(self, namespace="root\\cimv2"):
        """Establishes connection to WMI namespace."""
        try:
            self.locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
            # ConnectServer(Server, [Namespace], [User], [Password], [Locale], [Authority], [SecurityFlags], [objwbemNamedValueSet])
            self.service = self.locator.ConnectServer(self.target_ip, namespace, self.username, self.password)
            self.service.Security_.ImpersonationLevel = 3 # Impersonate
            return True
        except Exception as e:
            # `e` may be a pywintypes.com_error whose args tuple — under
            # specific HRESULTs — can echo the parameter values passed to
            # ConnectServer (including the password). Log only the class name
            # and HRESULT to avoid leaking credentials into the log.
            hresult = getattr(e, "hresult", None)
            logging.error(
                "WMI Connection failed for %s: %s (hresult=%r)",
                self.target_ip, e.__class__.__name__, hresult,
            )
            return False

    def query(self, wql):
        """Executes a WQL query."""
        if not self.service:
             if not self.connect():
                 return []
        try:
            return self.service.ExecQuery(wql)
        except Exception as e:
            logging.error(f"WMI Query failed ({wql}): {e}")
            return []

    def get_services(self):
        """Retrieves services similar to Get-Service."""
        services = []
        # Get-Service fields: Name, DisplayName, Status, StartType
        # WMI Win32_Service fields: Name, DisplayName, State, StartMode
        results = self.query("SELECT Name, DisplayName, State, StartMode FROM Win32_Service")
        
        for s in results:
            status_map = {"Running": "Running", "Stopped": "Stopped"} # Simplify or map exact
            # Powershell 'Status' enum: Stopped, StartPending, StopPending, Running, ContinuePending, PausePending, Paused
            # WMI 'State': Stopped, Start Pending, Stop Pending, Running, Continue Pending, Pause Pending, Paused, Unknown
            
            services.append({
                "Name": s.Name,
                "DisplayName": s.DisplayName,
                "Status": s.State, # Used by frontend?
                "StartType": s.StartMode
            })
        return services

    def get_system_info_raw(self):
        """Retrieves extensive system info matching get_system_info.ps1 structure."""
        if not self.service:
            if not self.connect():
                return {"error": "Conection Failed"}
        
        info = {}
        
        # 1. OS
        try:
            os_list = self.query("SELECT Caption, Version, LastBootUpTime, InstallDate, Organization FROM Win32_OperatingSystem")
            if os_list:
                os_obj = os_list[0]
                info["OS"] = os_obj.Caption
                info["OS_Version"] = os_obj.Version
                info["LastBootUpTime"] = self._parse_wmitime(os_obj.LastBootUpTime)
                info["InstallDate"] = self._parse_wmitime(os_obj.InstallDate)
                
                # Uptime
                lb_dt = self._wmitime_to_dt(os_obj.LastBootUpTime)
                if lb_dt:
                    diff = datetime.now() - lb_dt
                    info["Uptime"] = {
                        "uptime_days": diff.days,
                        "uptime_hours": diff.seconds // 3600,
                        "uptime_seconds": int(diff.total_seconds())
                    }
        except Exception as e:
            logging.error(f"WMI OS Info Error: {e}")

        # 2. CPU
        try:
            cpu = self.query("SELECT Name FROM Win32_Processor")
            if cpu:
                info["CPU"] = cpu[0].Name
        except Exception as e:
            logging.debug(f"WMI CPU info failed: {e}")

        # 3. RAM
        try:
            cs = self.query("SELECT TotalPhysicalMemory, UserName FROM Win32_ComputerSystem")
            if cs:
                ram_bytes = float(cs[0].TotalPhysicalMemory)
                info["RAM_GB"] = round(ram_bytes / (1024**3), 2)
                info["CurrentUser"] = cs[0].UserName if cs[0].UserName else "N/A"
        except Exception as e:
            logging.debug(f"WMI RAM/ComputerSystem failed: {e}")

        # 4. Disks
        try:
            disks = []
            disk_q = self.query("SELECT DeviceID, VolumeName, Size, FreeSpace FROM Win32_LogicalDisk WHERE DriveType=3")
            for d in disk_q:
                disks.append({
                    "DeviceID": d.DeviceID,
                    "VolumeName": d.VolumeName if d.VolumeName else "",
                    "Total_GB": round(float(d.Size) / (1024**3), 2) if d.Size else 0,
                    "Free_GB": round(float(d.FreeSpace) / (1024**3), 2) if d.FreeSpace else 0
                })
            info["Disks"] = disks
        except Exception as e:
            logging.debug(f"WMI Disks query failed: {e}")

        # 5. Network (Complex logic to match target IP)
        try:
            # We filter by IPEnabled=True, then check IPAddress array
            # We can't query array contains in WQL easily. Fetch all IPEnabled=True
            nics = self.query("SELECT * FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled=TRUE")
            
            target_nic = None
            for nic in nics:
                if nic.IPAddress:
                    # IPAddress is a tuple/list
                    ips = nic.IPAddress
                    if isinstance(ips, tuple) or isinstance(ips, list):
                        if self.target_ip in ips:
                            target_nic = nic
                            break
            
            if target_nic:
                info["SubnetMask"] = target_nic.IPSubnet[0] if target_nic.IPSubnet else "N/A"
                info["Gateway"] = ", ".join(target_nic.DefaultIPGateway) if target_nic.DefaultIPGateway else "N/A"
                info["DNSServers"] = ", ".join(target_nic.DNSServerSearchOrder) if target_nic.DNSServerSearchOrder else "N/A"
                info["DHCPServer"] = target_nic.DHCPServer if hasattr(target_nic, "DHCPServer") else "N/A"
                info["MACAddress"] = target_nic.MACAddress
                
                # Link Speed (Win32_NetworkAdapter)
                # Need Index/InterfaceIndex to match
                try:
                    idx = target_nic.Index
                    adapters = self.query(f"SELECT NetConnectionID, Speed FROM Win32_NetworkAdapter WHERE Index={idx}")
                    if adapters:
                        adapter = adapters[0]
                        info["Interface"] = adapter.NetConnectionID
                        if adapter.Speed:
                            speed = float(adapter.Speed)
                            if speed >= 1e9: info["LinkSpeed"] = f"{round(speed/1e9, 1)} Gbps"
                            elif speed >= 1e6: info["LinkSpeed"] = f"{round(speed/1e6, 0)} Mbps"
                            else: info["LinkSpeed"] = f"{speed} bps"
                except Exception as e:
                    logging.debug(f"WMI NetworkAdapter speed lookup failed: {e}")
        except Exception as e:
            logging.error(f"WMI Net Error: {e}")

        # TeamViewer (Registry) - Skip for now or implement later
        info["TeamViewerID"] = "N/A"
        
        return info

    def _parse_wmitime(self, wmi_time):
        if not wmi_time: return ""
        # Format: 20241022143000.000000-180
        try:
            return f"{wmi_time[0:4]}-{wmi_time[4:6]}-{wmi_time[6:8]}T{wmi_time[8:10]}:{wmi_time[10:12]}:{wmi_time[12:14]}"
        except Exception:
            return wmi_time

    def _wmitime_to_dt(self, wmi_time):
        if not wmi_time: return None
        try:
            # datetime.strptime(wmi_time.split('.')[0], "%Y%m%d%H%M%S")
            return datetime(
                int(wmi_time[0:4]), int(wmi_time[4:6]), int(wmi_time[6:8]),
                int(wmi_time[8:10]), int(wmi_time[10:12]), int(wmi_time[12:14])
            )
        except Exception:
            return None

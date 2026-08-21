"""
src/telemetry/network_collector.py
High-performance Network Telemetry Collector for Windows.
Monitors active network interface via Win32 IP Helper GetAdaptersAddresses,
calculating live downlink/uplink throughput in both Mbps and MB/s.
"""

import ctypes
from ctypes import wintypes
import logging
import sys
import time
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger(__name__)


class SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int)]


class IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
    pass


IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
    ("Length", wintypes.ULONG),
    ("Flags", wintypes.DWORD),
    ("Next", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
    ("Address", SOCKET_ADDRESS),
]


class IP_ADAPTER_ADDRESSES(ctypes.Structure):
    pass


IP_ADAPTER_ADDRESSES._fields_ = [
    ("Length", wintypes.ULONG),
    ("IfIndex", wintypes.DWORD),
    ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.c_void_p),
    ("DnsSuffix", wintypes.LPWSTR),
    ("Description", wintypes.LPWSTR),
    ("FriendlyName", wintypes.LPWSTR),
    ("PhysicalAddress", ctypes.c_byte * 8),
    ("PhysicalAddressLength", wintypes.DWORD),
    ("Flags", wintypes.DWORD),
    ("Mtu", wintypes.DWORD),
    ("IfType", wintypes.DWORD),
    ("OperStatus", wintypes.DWORD),
]


class NetworkCollector:
    """
    Monitors active network interface, calculating downlink and uplink speeds in Mbps and MB/s.
    """

    def __init__(self):
        self.prev_io: Dict[str, Any] = {}
        self.prev_time: float = time.perf_counter()
        self.adapter_cache: Dict[str, Dict[str, Any]] = {}
        self.last_cache_time: float = 0.0
        self._refresh_adapter_metadata()
        try:
            self.prev_io = psutil.net_io_counters(pernic=True) or {}
        except Exception:
            self.prev_io = {}

    def _refresh_adapter_metadata(self) -> None:
        """Queries Win32 IP Helper to resolve hardware descriptions, if_types, and link status."""
        if sys.platform != "win32":
            return

        try:
            iphlpapi = ctypes.windll.iphlpapi
            buf_len = wintypes.ULONG(15000)
            buf = ctypes.create_string_buffer(15000)
            res = iphlpapi.GetAdaptersAddresses(0, 0, None, buf, ctypes.byref(buf_len))
            if res == 111:  # ERROR_BUFFER_OVERFLOW
                buf = ctypes.create_string_buffer(buf_len.value)
                res = iphlpapi.GetAdaptersAddresses(0, 0, None, buf, ctypes.byref(buf_len))

            adapters: Dict[str, Dict[str, Any]] = {}
            if res == 0:
                curr = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
                while curr:
                    a = curr.contents
                    fname = str(a.FriendlyName) if a.FriendlyName else ""
                    desc = str(a.Description) if a.Description else ""
                    iftype = a.IfType
                    oper = a.OperStatus
                    is_up = oper == 1
                    is_virtual = any(
                        k in desc.lower()
                        for k in [
                            "virtual",
                            "vmware",
                            "hyper-v",
                            "loopback",
                            "bluetooth",
                            "tap",
                            "npcap",
                            "wsl",
                            "vpn",
                        ]
                    )
                    if fname:
                        adapters[fname] = {
                            "friendly_name": fname,
                            "description": desc,
                            "if_type": iftype,
                            "is_up": is_up,
                            "is_virtual": is_virtual,
                        }
                    if not a.Next:
                        break
                    curr = a.Next

            self.adapter_cache = adapters
        except Exception as exc:
            logger.debug("Network adapter metadata refresh error: %s", exc)

        self.last_cache_time = time.perf_counter()

    def collect(self) -> Dict[str, Any]:
        """Calculates live throughput deltas and identifies the active adapter."""
        now = time.perf_counter()
        if (now - self.last_cache_time) > 30.0:
            self._refresh_adapter_metadata()

        dt = now - self.prev_time
        if dt <= 0.001:
            dt = 1.0

        try:
            curr_io = psutil.net_io_counters(pernic=True) or {}
        except Exception:
            curr_io = {}

        active_name = "Disconnected"
        is_connected = False
        max_bytes = -1.0
        active_rx_bytes = 0
        active_tx_bytes = 0

        # 1. Identify adapter with highest real traffic
        for nic, c in curr_io.items():
            if nic not in self.prev_io:
                continue
            info = self.adapter_cache.get(
                nic,
                {
                    "friendly_name": nic,
                    "description": nic,
                    "is_virtual": False,
                    "is_up": True,
                },
            )
            if info.get("is_virtual") or not info.get("is_up"):
                continue

            p = self.prev_io[nic]
            rx = max(0, c.bytes_recv - p.bytes_recv)
            tx = max(0, c.bytes_sent - p.bytes_sent)
            total = rx + tx

            if total > max_bytes:
                max_bytes = total
                active_rx_bytes = rx
                active_tx_bytes = tx
                desc = info.get("description")
                active_name = (
                    f"{info['friendly_name']} ({desc})"
                    if desc and desc != info["friendly_name"]
                    else info["friendly_name"]
                )
                is_connected = True

        # 2. If idle, pick the primary connected physical adapter
        if not is_connected:
            for nic, info in self.adapter_cache.items():
                if info.get("is_up") and not info.get("is_virtual") and nic in curr_io:
                    desc = info.get("description")
                    active_name = (
                        f"{info['friendly_name']} ({desc})"
                        if desc and desc != info["friendly_name"]
                        else info["friendly_name"]
                    )
                    is_connected = True
                    break

        # Fallback if psutil found adapters directly but adapter_cache is empty
        if not is_connected and curr_io:
            for nic in curr_io:
                if not any(v in nic.lower() for v in ["loopback", "virtual", "wsl", "bluetooth"]):
                    active_name = nic
                    is_connected = True
                    break

        downlink_mbs = active_rx_bytes / (1024 * 1024 * dt)
        uplink_mbs = active_tx_bytes / (1024 * 1024 * dt)
        downlink_mbps = (active_rx_bytes * 8.0) / (1_000_000.0 * dt)
        uplink_mbps = (active_tx_bytes * 8.0) / (1_000_000.0 * dt)

        self.prev_io = curr_io
        self.prev_time = now

        return {
            "adapter_name": active_name,
            "interface": active_name,
            "connected": is_connected,
            "download_mbps": round(downlink_mbps, 1),
            "upload_mbps": round(uplink_mbps, 1),
            "downlink_mbps": round(downlink_mbps, 1),
            "uplink_mbps": round(uplink_mbps, 1),
            "downlink_mbs": round(downlink_mbs, 2),
            "uplink_mbs": round(uplink_mbs, 2),
        }

    def poll(self) -> Dict[str, Any]:
        """Alias for collect()."""
        return self.collect()

    def get_fallback(self) -> Dict[str, Any]:
        """Returns safe default struct in case of unexpected failure."""
        return {
            "adapter_name": "Disconnected",
            "interface": "Disconnected",
            "connected": False,
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "downlink_mbps": 0.0,
            "uplink_mbps": 0.0,
            "downlink_mbs": 0.0,
            "uplink_mbs": 0.0,
        }

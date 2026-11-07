"""Detect the machine so marsOS can tune itself (especially for older MacBooks)."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

DMI = Path("/sys/class/dmi/id")
MEMINFO = Path("/proc/meminfo")
CPUINFO = Path("/proc/cpuinfo")
DRM = Path("/sys/class/drm")

# product id -> (friendly name, year)
MAC_MODELS = {
    "MacBookPro8,1": ("MacBook Pro (13-inch, 2011)", 2011),
    "MacBookPro8,2": ("MacBook Pro (15-inch, 2011)", 2011),
    "MacBookPro8,3": ("MacBook Pro (17-inch, 2011)", 2011),
    "MacBookAir4,1": ("MacBook Air (11-inch, Mid 2011)", 2011),
    "MacBookAir4,2": ("MacBook Air (13-inch, Mid 2011)", 2011),
    "Macmini5,1": ("Mac mini (2011)", 2011),
    "Macmini5,2": ("Mac mini (2011)", 2011),
    "iMac12,1": ("iMac (21.5-inch, 2011)", 2011),
    "iMac12,2": ("iMac (27-inch, 2011)", 2011),
    "MacBook7,1": ("MacBook (13-inch, 2010)", 2010),
    "MacBookPro9,1": ("MacBook Pro (15-inch, 2012)", 2012),
    "MacBookPro9,2": ("MacBook Pro (13-inch, 2012)", 2012),
    "MacBookAir5,1": ("MacBook Air (11-inch, 2012)", 2012),
    "MacBookAir5,2": ("MacBook Air (13-inch, 2012)", 2012),
}
GPU_VENDORS = {"0x8086": "Intel", "0x1002": "AMD", "0x10de": "NVIDIA", "0x1af4": "Virtual", "0x15ad": "VMware"}


@dataclass
class HardwareInfo:
    vendor: str = ""
    product: str = ""
    ram_mb: int = 0
    cpu: str = ""
    gpus: list[str] = field(default_factory=list)

    @property
    def is_mac(self) -> bool:
        return "apple" in self.vendor.lower()

    @property
    def mac_year(self) -> int | None:
        return MAC_MODELS.get(self.product, ("", None))[1]

    @property
    def friendly(self) -> str:
        if self.product in MAC_MODELS:
            return MAC_MODELS[self.product][0]
        return self.product or "This computer"

    @property
    def ram_gb(self) -> float:
        return round(self.ram_mb / 1024, 1)


def _read(p: Path) -> str:
    try:
        return p.read_text().strip()
    except OSError:
        return ""


def detect(dmi: Path = DMI, meminfo: Path = MEMINFO, cpuinfo: Path = CPUINFO, drm: Path = DRM) -> HardwareInfo:
    ram = 0
    m = re.search(r"MemTotal:\s+(\d+) kB", _read(meminfo))
    if m:
        ram = int(m.group(1)) // 1024
    cpu = ""
    m = re.search(r"model name\s*:\s*(.+)", _read(cpuinfo))
    if m:
        cpu = m.group(1).strip()
    gpus: list[str] = []
    if drm.exists():
        for card in sorted(drm.glob("card[0-9]")):
            v = _read(card / "device" / "vendor")
            if v:
                gpus.append(GPU_VENDORS.get(v.lower(), v))
    return HardwareInfo(_read(dmi / "sys_vendor"), _read(dmi / "product_name"), ram, cpu, gpus)


def recommended_effects(hw: HardwareInfo) -> str:
    """full / balanced / light. A 2011 MacBook (Intel HD 3000, ~4 GB) gets 'balanced'."""
    if hw.ram_mb and hw.ram_mb < 2600:
        return "light"
    if (hw.mac_year and hw.mac_year <= 2013) or (hw.ram_mb and hw.ram_mb < 6000):
        return "balanced"
    return "full"

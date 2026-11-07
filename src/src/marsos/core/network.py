"""Wi-Fi and Bluetooth via NetworkManager / rfkill – no terminal needed by the user."""
from __future__ import annotations
import re
from dataclasses import dataclass

from marsos.core.runner import Runner


@dataclass
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    in_use: bool = False

    @property
    def secured(self) -> bool:
        return bool(self.security) and self.security != "--"

    @property
    def bars(self) -> int:
        return 1 + (self.signal >= 25) + (self.signal >= 50) + (self.signal >= 75)


def split_nmcli(line: str) -> list[str]:
    parts, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch; esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def parse_wifi_list(text: str) -> list[WifiNetwork]:
    best: dict[str, WifiNetwork] = {}
    for line in text.splitlines():
        f = split_nmcli(line)
        if len(f) < 4 or not f[1]:
            continue
        try:
            sig = int(f[2])
        except ValueError:
            continue
        n = WifiNetwork(f[1], sig, f[3], f[0].strip() == "*")
        if n.ssid not in best or n.signal > best[n.ssid].signal or n.in_use:
            best[n.ssid] = n
    return sorted(best.values(), key=lambda n: (not n.in_use, -n.signal))


def list_wifi(r: Runner, rescan: bool = False) -> list[WifiNetwork]:
    res = r.run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list",
                 "--rescan", "yes" if rescan else "auto"], timeout=20)
    return parse_wifi_list(res.stdout) if res.ok else []


def connect(r: Runner, ssid: str, password: str | None) -> tuple[bool, str]:
    if password:
        res = r.run(["nmcli", "--ask", "dev", "wifi", "connect", ssid], input=password + "\n", timeout=60)
    else:
        res = r.run(["nmcli", "dev", "wifi", "connect", ssid], timeout=60)
    if res.ok:
        return True, "Connected"
    msg = res.stdout.lower()
    if "secrets" in msg or "password" in msg or "802-11" in msg:
        return False, "That password didn't work. Please check it and try again."
    return False, "Couldn't connect. Please try again."


def wifi_enabled(r: Runner) -> bool:
    return r.run(["nmcli", "radio", "wifi"]).stdout.strip() == "enabled"


def set_wifi(r: Runner, on: bool) -> None:
    r.run(["nmcli", "radio", "wifi", "on" if on else "off"])


def is_online(r: Runner) -> bool:
    return r.run(["nmcli", "-t", "-f", "CONNECTIVITY", "general"]).stdout.strip() in ("full", "limited", "portal")


def bluetooth_enabled(r: Runner) -> bool:
    out = r.run(["rfkill", "list", "bluetooth"]).stdout
    return bool(out) and "Soft blocked: no" in out


def set_bluetooth(r: Runner, on: bool) -> None:
    r.run(["rfkill", "unblock" if on else "block", "bluetooth"])


def parse_volume(text: str) -> int | None:
    m = re.search(r"Volume:\s*([\d.]+)", text)
    return round(float(m.group(1)) * 100) if m else None


def get_volume(r: Runner) -> int | None:
    return parse_volume(r.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]).stdout)


def set_volume(r: Runner, pct: int) -> None:
    r.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{max(0, min(100, pct))}%"])


def parse_brightness(text: str) -> int | None:
    m = re.search(r",(\d+)%", text)
    return int(m.group(1)) if m else None


def get_brightness(r: Runner) -> int | None:
    return parse_brightness(r.run(["brightnessctl", "-m"]).stdout)


def set_brightness(r: Runner, pct: int) -> None:
    r.run(["brightnessctl", "set", f"{max(5, min(100, pct))}%"])

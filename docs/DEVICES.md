# VERNUX Device Compatibility Notes

Community-maintained notes about Termux and VERNUX behavior on specific devices.

---

## Known OEM Issues (All Devices of This Brand)

### Xiaomi / Redmi / MIUI

**Battery optimization** — MIUI aggressively kills background processes.

Fix: Settings → Battery & performance → App battery saver → Termux → No restrictions

**Storage permission bug** — MIUI optimization can break `/sdcard/` access after setup.

Fix: Settings → Additional Settings → Developer Options → Disable MIUI optimization → Reboot → Run `termux-setup-storage` again

**Versions affected**: MIUI 12, 12.5, 13, HyperOS

---

### OPPO / Realme / ColorOS

**Storage permission** — ColorOS requires manual permission grant.

Fix: Settings → Apps → See all apps → Termux → Permissions → Files and Media → Allow all

**Background processes** — Apps killed when screen off.

Fix: Settings → Battery → Battery Optimization → All apps → Termux → Don't optimize

---

### Vivo / iQOO / VivoUI

**Background processes** — VivoUI aggressively kills background processes.

Fix: i Manager → Battery → High background power consumption → Termux → Allow

---

### Samsung / OneUI

**Battery optimization** — Samsung's Adaptive battery can kill Termux.

Fix: Settings → Apps → Termux → Battery → Unrestricted  
Also: Settings → Battery → Adaptive battery → Off (optional, stronger fix)

**Generally reliable** — OneUI is more Termux-friendly than MIUI/ColorOS.

---

### OnePlus / OxygenOS

Generally well-behaved. Disable battery optimization if long tasks get killed.

---

## Specific Device Notes

*Submit your device via Pull Request. See CONTRIBUTING.md.*

### Template

```markdown
## [Brand Model] (e.g. Xiaomi Redmi Note 12)
- Android version: 13
- Termux version: 0.118.x (from F-Droid)
- VERNUX version: v0.6.0

### Issue
Describe what breaks or behaves unexpectedly.

### Fix
Exact steps to fix it.

### Notes
Any additional context.
```

---

## General Advice for All Android Devices

1. **Install Termux from F-Droid** — the Play Store version is outdated and broken
2. **Disable battery optimization** for Termux before any long task
3. **Run `termux-wake-lock`** before downloads/installs to prevent background kill
4. **Use tmux** for tasks that take longer than 2 minutes — `pkg install tmux && tmux`
5. **Keep Termux notification visible** — Android is less likely to kill visible apps

---

## Termux Versions

VERNUX is tested on Termux 0.118.x and above from F-Droid.

If you're on the Play Store version, features will be broken. Install from F-Droid:  
https://f-droid.org/en/packages/com.termux/

---

*Add your device — open a Pull Request.*

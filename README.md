# VERNUX

> **Turn your Termux terminal into plain English. No commands. No confusion. No giving up.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Termux-green.svg)]()
[![Version](https://img.shields.io/badge/Version-v0.6.0-orange.svg)]()
[![Patterns](https://img.shields.io/badge/Patterns-151-brightgreen.svg)]()
[![Recipes](https://img.shields.io/badge/Recipes-10-brightgreen.svg)]()
[![Free Forever](https://img.shields.io/badge/Free-Forever-brightgreen.svg)]()

---

## What is VERNUX?

VERNUX is a free, open-source natural language interface for Termux on Android. Instead of memorizing bash commands, you describe what you want — VERNUX figures out the command, checks it's safe, warns you about risks, and runs it.

```
VERNUX 🟢 > install python
VERNUX 🟢 > push my project to github
VERNUX 🟢 > why is my storage full
VERNUX 🟢 > compress and share my project folder
VERNUX 🟢 > download youtube video
VERNUX 🟢 > what is grep
VERNUX 🟢 > set up local web server
```

**VERNUX will always be completely free. It cannot be sold. The license enforces this permanently.**

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/DeVenLucaz/Vernux/main/install.sh | bash
```

That's it. The installer:
- Checks Python 3.8+ and git
- Clones VERNUX to `~/vernux/`
- Builds the pattern and package databases
- Profiles your device (RAM, brand, Android version)
- Optionally downloads a local AI model (no internet needed after install)
- Creates a `vernux` command you can run from anywhere

**Requirements:** Android device with [Termux](https://f-droid.org/en/packages/com.termux/) from F-Droid (not Play Store), Python 3.8+

---

## Usage

```bash
vernux                        # start VERNUX
vernux doctor                 # check your full setup (23 checks)
vernux update                 # update VERNUX + refresh data files
vernux stats                  # session summary
vernux config mode learner    # change mode (noob / learner / pro)
vernux explain grep           # explain any bash command
vernux recipes                # list all built-in recipes
vernux --version              # show version
```

Once inside VERNUX, just type what you want:

```
VERNUX 🟢 > install nodejs
VERNUX 🟢 > what is chmod
VERNUX 🟢 > compress my folder
VERNUX 🟢 > push my project to github
VERNUX 🟢 > backup termux to sdcard
VERNUX 🟢 > make termux look good
```

---

## Modes

| Mode | Who It's For | What It Shows |
|---|---|---|
| 🟢 **Noob** | Never used a terminal | Plain English only — no raw commands ever |
| 🟡 **Learner** | Know a little, learning more | Commands shown + explained, undo hints |
| 🔴 **Pro** | Know what you're doing | Fast, raw, minimal friction |

Switch anytime: `vernux config mode pro` or say `change mode learner` inside VERNUX.

---

## Safety

Every command is classified before it runs:

| Level | Meaning | What Happens |
|---|---|---|
| 🟢 Safe | Read-only or low-risk | Runs (Learner/Pro auto, Noob confirms once) |
| 🟡 Caution | Modifies or removes something | Warning shown, you confirm |
| 🔴 Danger | Irreversible or affects important files | Big warning, consequences explained, you confirm |
| ☠️ No-undo | Could destroy your system | Hard stop — type "yes" explicitly or it won't run |

**Protected paths** (`/sdcard/`, `~/.ssh/`, Termux binaries) are never auto-run with dangerous commands.  
**Hard stops** (rm -rf /, fork bombs, dd to disk) are blocked regardless of mode or confirmation.

---

## Recipes

Recipes are verified multi-step workflows. Say one phrase, VERNUX walks you through everything — installing prerequisites, collecting what it needs, running each step in order.

| Say this | What happens |
|---|---|
| `push project to github` | Full wizard: git init, SSH key, remote, push |
| `setup python dev environment` | Python, pip, venv, project structure |
| `download youtube video` | Install yt-dlp + ffmpeg, download to Downloads |
| `make termux look good` | zsh + Oh My Zsh + theme + useful aliases |
| `set up local web server` | Python HTTP server accessible on your network |
| `backup termux to sdcard` | Full Termux backup → your Downloads folder |
| `setup nodejs project` | Node.js + npm + Express + starter server |
| `compress and share folder` | zip + Android share sheet |
| `fix termux storage access` | Diagnose + fix all storage permission issues |
| `update everything` | pkg upgrade + pip + npm + cleanup |

If a step fails mid-recipe, VERNUX shows exactly what completed and what didn't — you don't start over.

---

## Offline Help

VERNUX can explain any bash command, fully offline:

```
VERNUX 🟡 > what is grep
VERNUX 🟡 > explain chmod
VERNUX 🟡 > how does git stash work
VERNUX 🟡 > explain search download
```

60+ commands with mode-aware depth:
- **Noob**: plain English story ("like Ctrl+F but for the terminal")
- **Learner**: flags breakdown + examples
- **Pro**: one-liner + flags reference

---

## Reality Bridge

VERNUX knows about the non-obvious things that break Termux beginners — the gaps between "what Linux docs say" and "what actually happens on Android."

Type a problem in plain English and VERNUX explains the fix:

```
VERNUX 🟢 > permission denied sdcard
VERNUX 🟢 > authentication failed git push  
VERNUX 🟢 > termux stops when screen turns off
VERNUX 🟢 > package not found
VERNUX 🟢 > how do i run a bash script
```

Includes brand-specific notes for Xiaomi (MIUI), OPPO (ColorOS), Samsung, Vivo, and Realme.

---

## Package Intelligence

VERNUX silently fixes wrong package names before installing:

| You type | VERNUX uses |
|---|---|
| `install python` | `pkg install python3` |
| `install node` | `pkg install nodejs` |
| `install gcc` | `pkg install clang` (Termux uses clang) |
| `install mysql` | `pkg install mariadb` |
| `install sudo` | `pkg install tsu` |
| `install youtube-dl` | `pkg install yt-dlp` (youtube-dl is abandoned) |
| `install screen` | `pkg install tmux` |

On low-RAM devices, VERNUX warns before installing heavy packages and suggests lighter alternatives.

---

## Local AI (Optional)

If pattern matching doesn't know how to handle something, VERNUX can fall back to a local AI model — no internet, no API, no cost.

```bash
# Inside VERNUX:
install-model
```

VERNUX picks the right model for your device's RAM:
- **< 2GB**: Qwen2.5-Coder 1.5B Q4 (~1GB download)
- **2–4GB**: Qwen2.5-Coder 1.5B Q6 or 3B Q4
- **4GB+**: Phi-4 Mini Q4/Q6

AI-generated commands always go through safety classification and require your confirmation before running.

Requires llama.cpp: `pkg install llama-cpp`

---

## Requirements

| Requirement | Notes |
|---|---|
| Android | Any version supported by Termux |
| Termux | Install from [F-Droid](https://f-droid.org/en/packages/com.termux/) — NOT Play Store |
| Python | 3.8+ — `pkg install python3` |
| Storage | ~50MB for VERNUX + ~1GB if you want a local AI model |
| Internet | Only for install and `vernux update` — runs fully offline after |

---

## Project Status

| Phase | Name | Status |
|---|---|---|
| 0 | Foundation | ✅ Complete |
| 1 | Core Engine | ✅ Complete |
| 2 | Knowledge Base | ✅ Complete |
| 3 | Recipes | ✅ Complete |
| 4 | Local AI | ✅ Complete |
| **5** | **Polish & Release** | **✅ Complete** |
| 6 | Community | 🔄 Planned |

---

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full guide.

The easiest ways to contribute:
- **Recipes** — submit a multi-step workflow via the recipe submission issue template
- **Device notes** — report Termux quirks on your specific device in [docs/DEVICES.md](docs/DEVICES.md)
- **Bug reports** — use the bug report issue template
- **Pattern suggestions** — open a feature request for tasks not yet covered

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)

VERNUX is free. It will always be free. Modified versions must stay free and open-source under GPL v3.

---

*Built by [@DeVenLucaz](https://github.com/DeVenLucaz/)*  
*If VERNUX helped you, star the repo and share it with someone who needs it.*

# What's New in VERNUX — Plain English Edition

This file explains every update in simple language, no coding knowledge needed.

---

## v0.7.6 — Recipe Preview — 28 May 2026

### What was fixed
- **Recipes were asking "yes or no?" before telling you what they'd do.** When you typed something like "push my project to github", VERNUX would show the recipe name, a one-line description, and "12 steps" — then immediately ask if you want to start. You had no idea what those 12 steps were, or what information it was going to ask you for. Now it shows you the full plan first. You see every step in plain English, and a list of everything it will ask you to type (like your GitHub username, your email, your repo name) — before the yes/no question appears.

---

## v0.7.5 — Bigger Offline Brain — 28 May 2026

### What's new
- **VERNUX now knows 710+ commands offline.** A second community knowledge source called tldr-pages (public domain, maintained by thousands of contributors) was added. It fills in 200+ commands that weren't covered before — including all git sub-commands like `git stash`, `git rebase`, and `git cherry-pick`, plus modern tools like `fzf`, `bat`, `ripgrep`, and Termux-specific commands.
- **The library builds itself automatically.** Before this, you had to run a command manually to download the library. Now it downloads and builds during install, and refreshes automatically every time you run `vernux update`. You don't have to do anything.
- **`vernux update` now shows library status.** The update summary now includes a "Command library refreshed" line so you can see it's working.

---

## v0.7.4 — AI Fallback Fixed — 27 May 2026

### What was fixed
- **`vernux update` was crashing.** Running `vernux update` gave a "NameError: handle_update is not defined" error and quit immediately. The function existed on paper but was never actually written. Fixed — update now works and shows a proper summary of what was refreshed.
- **The AI was printing its entire startup screen into your terminal.** When VERNUX fell back to the local AI, the AI model was printing its own interface — including a big "llama.cpp" banner, a list of commands like `/exit`, `/regen`, `/clear`, and the full system instructions — all directly into the VERNUX output. This was caused by the AI model being an older version that ignored the "stay quiet" flags. Fixed with a two-layer approach: better flags to suppress the UI, plus a smart text cleaner that strips any leftover startup noise before showing you the answer.
- **The AI was ignoring questions like "what is JSON".** When you asked VERNUX something that starts with "what is", "how does", "explain", or similar, it was sending that to the AI with instructions to reply with a bash command only. So either the AI gave a useless command, or the answer got silently thrown away. Fixed — VERNUX now detects that you're asking a question and switches to explanation mode automatically.
- **Answers are now mode-aware.** In Noob mode, you get a plain English answer followed by a "Want to learn more?" suggestion. In Learner mode, you get the explanation plus a related command shown with a breakdown hint. In Pro mode, you get one line and a shortcut — no hand-holding.

---

## v0.7.3 — Pattern Builder — 27 May 2026

### What's new
- **Vernux can now grow its own brain.** There are now tools that let Vernux automatically learn new commands from two big community sources on the internet — one from StackOverflow (thousands of real questions like "how do I search a file?") and one from a community cheatsheet project. It downloads these, reads them, and adds them to its list of things it knows how to do.
- **A review tool was added.** After Vernux learns new things automatically, you (or a contributor) can go through what it learned and clean up any descriptions that are too technical, replacing them with simpler ones.
- **The tools are now properly organised** in one folder so it's easier to find and run them.

---

## v0.7.2 — Smarter "I don't know" — 27 May 2026

### What's new
- **Vernux no longer just gives up.** Before this update, if you typed something Vernux didn't recognise, it would just say it doesn't know. Now, before giving up, it searches its offline command library and tries to find something related to what you asked.
- **It understands natural questions better.** If you type "what does ripgrep do", Vernux now figures out you're asking about `ripgrep` and shows you what it knows about it — even if you didn't type the exact command name.
- **The "I don't know" message is now helpful.** Instead of a dead end, it now suggests what you could try next.

---

## v0.7.1 — Library Polish — 27 May 2026

### What's new
- **New: find related commands.** Type `library related grep` and Vernux shows you all commands in the same family as `grep` — handy for discovering new tools.
- **New: browse by category.** Type `library categories` to see a list of all command categories, like "file", "network", "text", etc.
- **Search results are easier to read.** Each result now shows the category it belongs to, so you can tell at a glance if it's what you need.
- **Fixed: looking up commands was broken in some cases.** Typing `library grep` was accidentally searching for `rep` instead of `grep`. Fixed.
- **Fixed: explain wasn't checking the library properly.** If you asked Vernux to explain something it hadn't seen before, it was skipping the library and going straight to "I don't know". Now it properly checks the library first.

---

## v0.7.0 — Built-in Command Library — 27 May 2026

### What's new
- **Vernux now has an offline reference book.** A database of 500+ Linux/Termux commands is now built into Vernux. It includes what each command does, how to use it, and real examples — and it works with no internet.
- **New `library` command.** You can now type things like `library grep` to look up any command, or `library search find files` to search by description.
- **Explain got smarter.** When you ask Vernux to explain a command, it now checks this new library too — so far more commands get a proper explanation instead of "I don't know".

---

## v0.6.4 — AI Fix — 27 May 2026

### What was fixed
- **The AI was printing a bunch of junk to the screen** when it started up. This was internal startup info that was never meant to be visible. Fixed — it's now hidden.
- **The AI's answers to "what is X" questions were being thrown away.** When you asked something like "what is JSON", the AI would answer, but Vernux was silently discarding the answer because it expected a command, not plain text. Fixed — these answers now show up properly.

---

## v0.6.2 — Download Fix — 26 May 2026

### What was fixed
- **Downloading AI models was silently failing.** The download tool was not following website redirects, so the file never actually arrived. Fixed.
- **Added a backup download method.** If the first download tool fails, it now automatically tries a second one.
- **Broken/incomplete downloads are now cleaned up.** If a download fails halfway, the broken file is now deleted so it doesn't cause confusion later.

---

## v0.6.1 — Command Understanding Fixes — 25 May 2026

### What was fixed
- **"Create a folder called myproject" was making a folder called "called".** Vernux was misreading the word "called" as the folder name. Fixed — it now correctly picks "myproject".
- **File names with dots (like `test.txt`) were being split up.** Vernux was treating `test` and `txt` as separate words. Fixed.
- **"Show storage" was opening the wrong screen.** It was going to storage setup instead of showing storage usage. Fixed.
- **The installer had a broken file path** that caused a "command not found" error on some phones. Fixed.
- **Noob mode was showing raw terminal output** for things like checking free space or running `git status`. Now it translates that into plain sentences.

---

## v0.6.0 — Public Release Ready — 25 May 2026

### What's new
- **Vernux can now update itself.** Just type `vernux update` and it downloads the latest version automatically.
- **A health check system was added.** Type `vernux doctor` and it checks 23 things — your storage, internet, installed packages, AI model, and more — and tells you if anything is wrong.
- **A stats screen was added.** Type `vernux stats` to see a summary of your current session.
- **A full README was written** so new users know how to install and use Vernux.
- **Vernux is now installable with one command** — just paste a curl command and it sets everything up for you.

---

## v0.5.0 — AI Added — 25 May 2026

### What's new
- **Vernux can now use a local AI** as a last resort when it doesn't know how to answer something. The AI runs on your phone — no internet needed.
- **It automatically picks a model that fits your phone's RAM** so it doesn't slow things down.
- **You can download a model** straight from inside Vernux by typing `install-model`.

---

## v0.4.0 — Recipes Added — 25 May 2026

### What's new
- **Recipes are multi-step guides for common tasks.** Things like "set up SSH keys" or "initialise a git repo" — Vernux walks you through each step, checks if you have the right tools installed, and asks for input when needed.
- **10 built-in recipes** are included covering common Termux setups.

---

## v0.3.0 — Knowledge Base — 25 May 2026

### What's new
- **Vernux can now explain commands.** Type `vernux explain grep` and it gives you a description with examples.
- **Android-specific warnings were added.** Vernux now knows about common issues specific to Android brands (Xiaomi, OPPO, Samsung, etc.) and warns you when relevant.
- **Package name fixes.** Some Termux packages have different names than you'd expect. Vernux now knows the correct names for 70+ packages.

---

## v0.2.0 — Core Engine — 25 May 2026

### What's new
- **Vernux can now understand what you're asking** and match it to the right command using keyword matching and fuzzy scoring.
- **A safety system was added.** Every command gets a risk rating (safe / caution / dangerous / destructive) before it runs.
- **Confirmation prompts** are shown before anything risky is executed.

---

## v0.1.0 — Foundation — 25 May 2026

### What's new
- **First version.** Basic project structure set up. Vernux can start up, detect your device (RAM, storage, brand), and accept typed input. No real command matching yet — just the skeleton everything else is built on.

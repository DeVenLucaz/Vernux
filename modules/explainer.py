# =============================================================================
# modules/explainer.py — Command Explainer & Offline Help
# Version: 0.3.0 | Phase 2 — Knowledge Base
# =============================================================================

import re
import os

# ---------------------------------------------------------------------------
# Built-in command dictionary
# 120+ common commands with full mode-aware explanations
# ---------------------------------------------------------------------------

COMMAND_DICT = {
    # --- File & Directory ---
    "ls": {
        "synopsis": "ls [options] [path]",
        "category": "files",
        "noob":    "Lists all the files and folders in the current location — like opening a folder on your phone.",
        "learner": "List directory contents. Common flags: -l (long format), -a (show hidden files), -h (human-readable sizes), -t (sort by time).",
        "pro":     "List directory. Key flags: -la, -lah, -lt, -R (recursive), --color.",
        "examples": ["ls", "ls -la", "ls -lah /sdcard/"],
    },
    "cd": {
        "synopsis": "cd [path]",
        "category": "navigation",
        "noob":    "Changes which folder you're currently in — like tapping into a folder on your phone.",
        "learner": "Change directory. cd ~ goes home, cd .. goes up one level, cd - goes back to previous dir.",
        "pro":     "cd ~, cd .., cd -, cd /path. $OLDPWD for previous.",
        "examples": ["cd ~", "cd ..", "cd myproject", "cd /sdcard/Download"],
    },
    "pwd": {
        "synopsis": "pwd",
        "category": "navigation",
        "noob":    "Shows exactly where you are — prints the full path of the folder you're currently in.",
        "learner": "Print Working Directory. Shows your full current path. Useful when lost or scripting.",
        "pro":     "Print cwd. pwd -P resolves symlinks.",
        "examples": ["pwd"],
    },
    "mkdir": {
        "synopsis": "mkdir [options] dirname",
        "category": "files",
        "noob":    "Creates a new empty folder with the name you choose.",
        "learner": "Make directory. -p creates parent directories too (no error if already exists). -m sets permissions.",
        "pro":     "mkdir -p path/to/deep/dir. mkdir -m 755 dir.",
        "examples": ["mkdir myproject", "mkdir -p src/components/ui"],
    },
    "rm": {
        "synopsis": "rm [options] file",
        "category": "files",
        "noob":    "Permanently deletes a file. There is NO Recycle Bin — once deleted, it's gone forever.",
        "learner": "Remove files. -r removes directories recursively. -f forces (no prompts). NEVER run rm -rf / or rm -rf ~.",
        "pro":     "rm, rm -r, rm -f, rm -rf. No undo. Use trash-cli if you want recovery.",
        "examples": ["rm file.txt", "rm -r oldfolder/", "rm -f *.tmp"],
    },
    "cp": {
        "synopsis": "cp [options] source dest",
        "category": "files",
        "noob":    "Makes a copy of a file or folder. The original stays untouched.",
        "learner": "Copy files. -r for directories (recursive). -p preserves timestamps/permissions. -v shows progress.",
        "pro":     "cp, cp -r, cp -rp, cp -v. cp -a = archive mode (preserve all).",
        "examples": ["cp file.txt backup.txt", "cp -r myfolder/ backup/"],
    },
    "mv": {
        "synopsis": "mv source dest",
        "category": "files",
        "noob":    "Moves a file to a different location, or renames it if you keep it in the same folder.",
        "learner": "Move or rename. If dest is a directory, file goes inside it. If dest is a filename, it renames.",
        "pro":     "mv src dst. mv -n (no overwrite). mv -v (verbose).",
        "examples": ["mv old.txt new.txt", "mv file.txt /sdcard/Download/"],
    },
    "cat": {
        "synopsis": "cat [file]",
        "category": "files",
        "noob":    "Shows the contents of a text file right in the terminal — like opening it to read.",
        "learner": "Concatenate and print files. cat file1 file2 > combined.txt joins files. Use less for long files.",
        "pro":     "cat, cat -n (line numbers), cat -A (show special chars). Pipe: cat file | grep pattern.",
        "examples": ["cat readme.txt", "cat file1 file2 > merged.txt"],
    },
    "less": {
        "synopsis": "less [file]",
        "category": "files",
        "noob":    "Opens a file you can scroll through. Press Q to quit, arrow keys to scroll.",
        "learner": "Scrollable file viewer. q=quit, /=search, n=next match, G=end, g=start. Better than cat for long files.",
        "pro":     "less -N (line nums), less +F (follow mode like tail -f). Pipe: cmd | less.",
        "examples": ["less longfile.txt", "git log | less"],
    },
    "touch": {
        "synopsis": "touch filename",
        "category": "files",
        "noob":    "Creates a new empty file with the name you choose. If it already exists, it just updates its timestamp.",
        "learner": "Create empty file or update timestamps. Commonly used to create placeholder files.",
        "pro":     "touch file. touch -t 202401010000 file (set specific timestamp).",
        "examples": ["touch newfile.txt", "touch index.html style.css"],
    },
    "find": {
        "synopsis": "find [path] [options]",
        "category": "files",
        "noob":    "Searches for files by name anywhere in your folders. Like the search function on your phone.",
        "learner": "Search files. -name '*.py' by name, -type f (files) or d (dirs), -size +1M (over 1MB), -mtime -7 (last 7 days).",
        "pro":     "find . -name '*.py' -exec grep -l 'TODO' {} +. find / -size +100M 2>/dev/null.",
        "examples": ["find . -name '*.py'", "find /sdcard -name '*.mp4'", "find . -type d"],
    },
    "grep": {
        "synopsis": "grep [options] pattern [file]",
        "category": "files",
        "noob":    "Searches inside files for a specific word or phrase — like Ctrl+F but for the terminal.",
        "learner": "Search text. -r (recursive), -i (case insensitive), -n (show line numbers), -l (just filenames), -v (invert match).",
        "pro":     "grep -rn 'pattern' . --include='*.py'. grep -E (extended regex). grep -c (count).",
        "examples": ["grep 'error' log.txt", "grep -rn 'TODO' .", "grep -i 'python' readme.md"],
    },
    "chmod": {
        "synopsis": "chmod [mode] file",
        "category": "permissions",
        "noob":    "Changes who is allowed to read, write, or run a file. Most commonly used to make a script runnable with +x.",
        "learner": "Change permissions. +x=add execute, -x=remove, 755=rwxr-xr-x, 644=rw-r--r--. chmod -R for directories.",
        "pro":     "chmod 755, 644, 600, +x, -R. Numeric: 4=read, 2=write, 1=execute.",
        "examples": ["chmod +x script.sh", "chmod 644 config.json", "chmod -R 755 mydir/"],
    },
    "chown": {
        "synopsis": "chown user[:group] file",
        "category": "permissions",
        "noob":    "Changes who owns a file. Rarely needed in Termux — most files belong to you already.",
        "learner": "Change file ownership. user:group format. -R for recursive. In Termux, usually not needed.",
        "pro":     "chown user:group file. chown -R user:group dir/.",
        "examples": ["chown user file.txt"],
    },
    "ln": {
        "synopsis": "ln [options] target link",
        "category": "files",
        "noob":    "Creates a shortcut to a file. Like a shortcut icon — it points to the real file elsewhere.",
        "learner": "Create links. -s creates a symlink (shortcut). Hard links share the same data. Symlinks can break if target moves.",
        "pro":     "ln -s target link. ln (hard link). readlink -f to resolve.",
        "examples": ["ln -s /sdcard/Download ~/dl"],
    },

    # --- Archives ---
    "zip": {
        "synopsis": "zip [options] archive.zip files",
        "category": "archives",
        "noob":    "Bundles files or folders into a single compressed zip file you can share or back up.",
        "learner": "Create zip archive. -r includes subdirectories. -9 maximum compression. -e encrypt with password.",
        "pro":     "zip -r out.zip dir/. zip -r -9 out.zip . zip -e for encryption.",
        "examples": ["zip -r project.zip myproject/", "zip archive.zip *.txt"],
    },
    "unzip": {
        "synopsis": "unzip [options] archive.zip",
        "category": "archives",
        "noob":    "Unpacks a zip file and puts all the files into a folder.",
        "learner": "Extract zip. -d dir/ extracts to specific folder. -l lists contents without extracting. -o overwrites.",
        "pro":     "unzip file.zip. unzip -d outdir/. unzip -l (list). unzip -o (overwrite).",
        "examples": ["unzip archive.zip", "unzip file.zip -d output/"],
    },
    "tar": {
        "synopsis": "tar [options] archive.tar files",
        "category": "archives",
        "noob":    "Compresses or extracts .tar.gz files — the Linux equivalent of zip files.",
        "learner": "Tape archive. -czf = create+gzip+filename, -xzf = extract+gzip+filename. -v = verbose. -C = destination.",
        "pro":     "tar -czf out.tar.gz dir/. tar -xzf file.tar.gz. tar -xzf file.tar.gz -C /dest/.",
        "examples": ["tar -czf backup.tar.gz myfolder/", "tar -xzf archive.tar.gz"],
    },

    # --- Network ---
    "curl": {
        "synopsis": "curl [options] url",
        "category": "network",
        "noob":    "Downloads files or talks to websites from the terminal. Like a browser but for scripts.",
        "learner": "Transfer data. -O saves with original name. -o filename saves as. -L follows redirects. -s silent mode.",
        "pro":     "curl -O url. curl -L -o file url. curl -X POST -d data url. curl -H 'Header: val'.",
        "examples": ["curl -O https://example.com/file.zip", "curl https://api.github.com/user"],
    },
    "wget": {
        "synopsis": "wget [options] url",
        "category": "network",
        "noob":    "Downloads a file from the internet to your current folder.",
        "learner": "Download files. -O renames output. -c resumes interrupted downloads. -q quiet mode. --limit-rate limits speed.",
        "pro":     "wget url. wget -O file url. wget -c url (resume). wget -r (recursive).",
        "examples": ["wget https://example.com/file.zip", "wget -O myfile.zip https://example.com/download"],
    },
    "ping": {
        "synopsis": "ping [options] host",
        "category": "network",
        "noob":    "Tests if your internet is working by sending a signal to a server and waiting for a reply.",
        "learner": "Send ICMP echo requests. -c N limits to N packets. -W timeout. Ctrl+C to stop.",
        "pro":     "ping -c 4 host. ping -i 0.2 (fast). ping -s 1000 (packet size).",
        "examples": ["ping -c 4 8.8.8.8", "ping google.com"],
    },
    "ssh": {
        "synopsis": "ssh [options] user@host",
        "category": "network",
        "noob":    "Lets you log into another computer remotely through the terminal — like remote desktop but text-only.",
        "learner": "Secure Shell. -p port (default 22). -i keyfile (SSH key auth). -L local port forwarding.",
        "pro":     "ssh user@host. ssh -p 2222. ssh -i ~/.ssh/key. ssh -L 8080:localhost:80 user@host.",
        "examples": ["ssh user@192.168.1.100", "ssh -p 8022 localhost"],
    },

    # --- Package management ---
    "pkg": {
        "synopsis": "pkg [command] [package]",
        "category": "packages",
        "noob":    "Termux's app store for the terminal. Use it to install tools like python, git, ffmpeg etc.",
        "learner": "Termux package manager. install/uninstall/upgrade/search/list/show. Always run pkg update before installing.",
        "pro":     "pkg install/uninstall/upgrade/search/list/show/clean. Wraps apt. Repos in /data/data/com.termux/files/usr/etc/apt/.",
        "examples": ["pkg install python3", "pkg search ffmpeg", "pkg update && pkg upgrade -y"],
    },
    "pip": {
        "synopsis": "pip install [package]",
        "category": "packages",
        "noob":    "Installs Python add-on libraries. Like the app store specifically for Python code.",
        "learner": "Python package manager. install, uninstall, freeze (list), show, install -r requirements.txt.",
        "pro":     "pip install pkg. pip install -r req.txt. pip freeze > req.txt. pip show pkg. pip install --upgrade.",
        "examples": ["pip install requests", "pip install -r requirements.txt", "pip freeze > requirements.txt"],
    },
    "npm": {
        "synopsis": "npm [command]",
        "category": "packages",
        "noob":    "The package manager for Node.js — installs JavaScript libraries for your projects.",
        "learner": "Node Package Manager. install/uninstall/init/run/list. npm install saves to node_modules/.",
        "pro":     "npm install pkg. npm install -g (global). npm init -y. npm run script. npm ls.",
        "examples": ["npm install express", "npm init -y", "npm install -g nodemon"],
    },

    # --- Git ---
    "git": {
        "synopsis": "git [command]",
        "category": "git",
        "noob":    "The tool that tracks all changes to your code over time and lets you share it to GitHub.",
        "learner": "Distributed version control. Key commands: init, clone, add, commit, push, pull, status, log, branch, merge.",
        "pro":     "git init/clone/add/commit/push/pull/fetch/merge/rebase/stash/branch/checkout/log/diff/reset.",
        "examples": ["git init", "git status", "git log --oneline"],
    },
    "git init": {
        "synopsis": "git init",
        "category": "git",
        "noob":    "Turns the current folder into a Git project so you can start tracking your work.",
        "learner": "Initialize a new local repository. Creates a .git/ folder. Run once per project.",
        "pro":     "git init. git init --bare (server repos). git init -b main (set default branch).",
        "examples": ["git init"],
    },
    "git clone": {
        "synopsis": "git clone url [dir]",
        "category": "git",
        "noob":    "Downloads an entire project from GitHub to your device, ready to use.",
        "learner": "Clone a remote repo. Creates a new folder. Automatically sets up origin remote. Can specify target dir.",
        "pro":     "git clone url. git clone url dirname. git clone --depth 1 (shallow). git clone --branch name.",
        "examples": ["git clone https://github.com/user/repo.git", "git clone url mydir"],
    },
    "git add": {
        "synopsis": "git add [files]",
        "category": "git",
        "noob":    "Marks files to be included in your next save (commit). Think of it as checking the boxes before saving.",
        "learner": "Stage changes. git add . = all changes. git add file.py = specific file. git add -p = interactive patch.",
        "pro":     "git add . / git add -A / git add -p / git add -u (tracked only).",
        "examples": ["git add .", "git add index.html style.css"],
    },
    "git commit": {
        "synopsis": "git commit -m 'message'",
        "category": "git",
        "noob":    "Saves a snapshot of all the files you marked. Like saving a version of your work with a label.",
        "learner": "Commit staged changes. -m for inline message. --amend to fix last commit. -a to stage+commit tracked files.",
        "pro":     "git commit -m 'msg'. git commit --amend. git commit -a -m 'msg'.",
        "examples": ['git commit -m "add login feature"', "git commit --amend"],
    },
    "git push": {
        "synopsis": "git push [remote] [branch]",
        "category": "git",
        "noob":    "Uploads your saved work to GitHub so it's backed up and others can see it.",
        "learner": "Push commits to remote. git push origin main. --force overwrites (dangerous). -u sets upstream tracking.",
        "pro":     "git push. git push origin main. git push -u origin main. git push --force-with-lease.",
        "examples": ["git push", "git push origin main", "git push -u origin main"],
    },
    "git pull": {
        "synopsis": "git pull [remote] [branch]",
        "category": "git",
        "noob":    "Downloads the latest version of the project from GitHub to your device.",
        "learner": "Fetch + merge remote changes. git pull = git fetch + git merge. --rebase avoids merge commits.",
        "pro":     "git pull. git pull --rebase. git pull origin main.",
        "examples": ["git pull", "git pull origin main"],
    },
    "git status": {
        "synopsis": "git status",
        "category": "git",
        "noob":    "Shows which files have changed since your last save. Run this before every commit.",
        "learner": "Shows staged, unstaged, and untracked changes. -s for short format. Tells you what branch you're on.",
        "pro":     "git status. git status -s. git status -b.",
        "examples": ["git status", "git status -s"],
    },
    "git log": {
        "synopsis": "git log [options]",
        "category": "git",
        "noob":    "Shows a history of all the saves you've made — like a timeline of your work.",
        "learner": "--oneline compact view. --graph shows branch tree. -n 10 limits to 10 commits. --author filters by author.",
        "pro":     "git log --oneline --graph --all. git log -p (patches). git log --stat.",
        "examples": ["git log --oneline -10", "git log --oneline --graph --all"],
    },
    "git diff": {
        "synopsis": "git diff [options]",
        "category": "git",
        "noob":    "Shows exactly what changed in your files since the last save — line by line.",
        "learner": "Show unstaged changes. git diff --staged shows staged. git diff HEAD shows all. git diff branch1 branch2.",
        "pro":     "git diff. git diff --staged. git diff HEAD~1. git diff branch1..branch2.",
        "examples": ["git diff", "git diff --staged"],
    },
    "git branch": {
        "synopsis": "git branch [name]",
        "category": "git",
        "noob":    "Shows all versions of your project (branches), or creates a new one.",
        "learner": "List/create/delete branches. git branch name creates. -d deletes. -D force deletes. -a shows remote branches.",
        "pro":     "git branch. git branch name. git branch -d name. git branch -a.",
        "examples": ["git branch", "git branch feature-login", "git branch -d old-branch"],
    },
    "git checkout": {
        "synopsis": "git checkout [branch/file]",
        "category": "git",
        "noob":    "Switches to a different version of your project, or undoes changes to a file.",
        "learner": "Switch branches or restore files. git checkout -b creates+switches. git checkout -- file discards changes.",
        "pro":     "git checkout branch. git checkout -b new. git checkout -- file. Modern: git switch / git restore.",
        "examples": ["git checkout main", "git checkout -b feature-x"],
    },
    "git stash": {
        "synopsis": "git stash [command]",
        "category": "git",
        "noob":    "Temporarily hides your unsaved changes so you can work on something else, then brings them back later.",
        "learner": "Stash uncommitted changes. pop restores+removes. apply restores without removing. list shows all stashes.",
        "pro":     "git stash. git stash pop. git stash apply. git stash list. git stash drop.",
        "examples": ["git stash", "git stash pop", "git stash list"],
    },

    # --- Process management ---
    "ps": {
        "synopsis": "ps [options]",
        "category": "processes",
        "noob":    "Shows all programs currently running in Termux — like the task manager on your phone.",
        "learner": "Process snapshot. aux shows all processes. -ef alternative. PID column is the process ID for kill.",
        "pro":     "ps aux. ps -ef. ps aux | grep python. watch -n1 ps aux.",
        "examples": ["ps aux", "ps aux | grep python3"],
    },
    "kill": {
        "synopsis": "kill [signal] PID",
        "category": "processes",
        "noob":    "Stops a running program by its ID number. Find the number first using 'show processes'.",
        "learner": "Send signal to process. Default=SIGTERM (graceful). -9=SIGKILL (force). Get PID from ps aux.",
        "pro":     "kill PID. kill -9 PID. kill -SIGTERM PID. killall processname.",
        "examples": ["kill 1234", "kill -9 1234"],
    },
    "pkill": {
        "synopsis": "pkill [options] name",
        "category": "processes",
        "noob":    "Stops a running program by its name instead of its ID number.",
        "learner": "Kill processes by name. -f matches full command line. -9 force kills. More convenient than kill + PID lookup.",
        "pro":     "pkill python3. pkill -9 node. pkill -f 'python script.py'.",
        "examples": ["pkill python3", "pkill -f myserver.py"],
    },
    "top": {
        "synopsis": "top",
        "category": "processes",
        "noob":    "Shows a live view of all running programs and how much memory/CPU they're using. Press Q to quit.",
        "learner": "Live process monitor. q=quit, k=kill, M=sort by memory, P=sort by CPU. htop is more user-friendly.",
        "pro":     "top. top -u user. Better: htop. For one-shot: ps aux --sort=-%cpu | head.",
        "examples": ["top"],
    },
    "htop": {
        "synopsis": "htop",
        "category": "processes",
        "noob":    "A nicer version of the task manager — shows running programs with colors and lets you scroll. Press Q to quit.",
        "learner": "Interactive process viewer. F6=sort, F9=kill, F5=tree view. Much nicer than top. Install: pkg install htop.",
        "pro":     "htop. htop -u user. htop -d 5 (5 tenths sec delay).",
        "examples": ["htop"],
    },

    # --- System info ---
    "df": {
        "synopsis": "df [options] [path]",
        "category": "system",
        "noob":    "Shows how much storage space is used and available on your device.",
        "learner": "Disk free. -h human-readable (GB/MB). df ~ shows Termux storage. df /sdcard shows phone storage.",
        "pro":     "df -h. df -h ~. df -h /sdcard. df -i (inodes).",
        "examples": ["df -h ~", "df -h"],
    },
    "du": {
        "synopsis": "du [options] [path]",
        "category": "system",
        "noob":    "Shows how much space a file or folder is taking up.",
        "learner": "Disk usage. -s summary only. -h human-readable. -sh * shows size of everything in current dir.",
        "pro":     "du -sh *. du -sh ~/. du -ah | sort -rh | head -20.",
        "examples": ["du -sh *", "du -sh ~/myproject"],
    },
    "free": {
        "synopsis": "free [options]",
        "category": "system",
        "noob":    "Shows how much RAM (memory) your device has and how much is currently free.",
        "learner": "Memory info. -h human-readable. Shows total, used, free, shared, buff/cache, available.",
        "pro":     "free -h. free -m (MB). watch -n1 free -h.",
        "examples": ["free -h"],
    },
    "uname": {
        "synopsis": "uname [options]",
        "category": "system",
        "noob":    "Shows basic information about your device's operating system.",
        "learner": "Print system info. -a all info. -r kernel version. -m machine (arm64/x86_64).",
        "pro":     "uname -a. uname -r. uname -m.",
        "examples": ["uname -a"],
    },
    "whoami": {
        "synopsis": "whoami",
        "category": "system",
        "noob":    "Shows your username — in Termux this is always 'u0_a...' or similar.",
        "learner": "Print current user. In Termux you're always a regular user, never root (unless using tsu).",
        "pro":     "whoami. id (more detail). id -u.",
        "examples": ["whoami"],
    },
    "date": {
        "synopsis": "date [options]",
        "category": "system",
        "noob":    "Shows the current date and time.",
        "learner": "Print/set date. +format for custom output. date '+%Y-%m-%d' = ISO format.",
        "pro":     "date. date '+%Y-%m-%d %H:%M:%S'. date -d 'yesterday'. date +%s (unix timestamp).",
        "examples": ["date", "date '+%Y-%m-%d'"],
    },

    # --- Text editing ---
    "nano": {
        "synopsis": "nano [file]",
        "category": "editors",
        "noob":    "A simple text editor inside the terminal. Ctrl+X to exit, Ctrl+O to save, Ctrl+W to search.",
        "learner": "Terminal text editor. Shortcuts shown at bottom. ^=Ctrl. Ctrl+X exit, Ctrl+O save, Ctrl+G help.",
        "pro":     "nano file. nano -l (line numbers). nano -m (mouse). nano -c (cursor pos).",
        "examples": ["nano myfile.txt", "nano ~/.bashrc"],
    },
    "vim": {
        "synopsis": "vim [file]",
        "category": "editors",
        "noob":    "A powerful text editor — but tricky to learn. To quit: press Escape, then type :q! and Enter.",
        "learner": "Modal editor. i=insert mode, Esc=normal mode, :w save, :q quit, :wq save+quit, :q! force quit, /=search.",
        "pro":     ":w :q :wq :q! :x. dd=delete line, yy=yank, p=paste, u=undo, /pattern, n=next.",
        "examples": ["vim file.txt"],
    },

    # --- Shell / scripting ---
    "echo": {
        "synopsis": "echo [text]",
        "category": "shell",
        "noob":    "Prints text to the screen. Used in scripts to show messages or save text to a file.",
        "learner": "Print text. echo 'text' > file writes to file. echo 'text' >> file appends. -n = no newline. -e = escape sequences.",
        "pro":     "echo 'text'. echo -e '\\n\\t'. echo $VAR. printf for more control.",
        "examples": ["echo hello", "echo 'text' > file.txt", "echo $HOME"],
    },
    "export": {
        "synopsis": "export VAR=value",
        "category": "shell",
        "noob":    "Sets a variable that your programs can read. Like storing a setting that all your tools can see.",
        "learner": "Set environment variable. Visible to child processes. Common: export PATH, PYTHONPATH, API_KEY.",
        "pro":     "export VAR=val. export -p (list all). Persist in ~/.bashrc or ~/.zshrc.",
        "examples": ["export PATH=$PATH:~/bin", "export EDITOR=nano"],
    },
    "source": {
        "synopsis": "source file",
        "category": "shell",
        "noob":    "Runs a script file's settings in your current session — like applying new settings without restarting.",
        "learner": "Execute file in current shell. . file is equivalent. Use for .bashrc, .zshrc, venv/bin/activate.",
        "pro":     "source file or . file. Runs in current shell (unlike bash file which spawns subshell).",
        "examples": ["source ~/.bashrc", "source venv/bin/activate"],
    },
    "alias": {
        "synopsis": "alias name='command'",
        "category": "shell",
        "noob":    "Creates a shortcut for a long command. Like renaming a long command to something short you can remember.",
        "learner": "Create command shortcuts. alias ll='ls -la'. Add to ~/.bashrc to persist. alias with no args lists all.",
        "pro":     "alias ll='ls -la'. alias gs='git status'. unalias name. alias (list all).",
        "examples": ["alias ll='ls -la'", "alias gs='git status'"],
    },
    "history": {
        "synopsis": "history [n]",
        "category": "shell",
        "noob":    "Shows a list of commands you've typed before. Press the up arrow to cycle through recent commands.",
        "learner": "Show command history. history 20 = last 20. !! = repeat last command. !n = run command #n.",
        "pro":     "history. history | grep git. !! last cmd. !n run #n. Ctrl+R reverse search.",
        "examples": ["history", "history | grep python"],
    },
    "clear": {
        "synopsis": "clear",
        "category": "shell",
        "noob":    "Clears all the text from your screen so it's blank again. Your history is still there if you scroll up.",
        "learner": "Clear terminal screen. Ctrl+L does the same thing. Doesn't delete history.",
        "pro":     "clear. Ctrl+L. reset (if terminal is broken).",
        "examples": ["clear"],
    },

    # --- Python ---
    "python3": {
        "synopsis": "python3 [file] or python3 -c 'code'",
        "category": "programming",
        "noob":    "Runs Python programs. Type python3 alone to enter interactive mode where you can test code.",
        "learner": "Python 3 interpreter. python3 file.py runs a script. python3 -c 'code' runs one-liner. python3 -m module.",
        "pro":     "python3 script.py. python3 -c 'import sys; print(sys.version)'. python3 -m http.server.",
        "examples": ["python3 script.py", "python3 -m http.server 8080", "python3 -c 'print(2**10)'"],
    },

    # --- Termux-specific ---
    "termux-setup-storage": {
        "synopsis": "termux-setup-storage",
        "category": "termux",
        "noob":    "Gives Termux permission to access your phone's storage. A popup appears — tap Allow. Run this once.",
        "learner": "Request storage permission from Android. Creates ~/storage/ symlinks to Android directories. Must accept the popup.",
        "pro":     "termux-setup-storage. Creates ~/storage/{dcim,downloads,movies,music,pictures,shared}.",
        "examples": ["termux-setup-storage"],
    },
    "termux-wake-lock": {
        "synopsis": "termux-wake-lock",
        "category": "termux",
        "noob":    "Keeps Termux running even when your screen turns off. Important for long downloads or installs.",
        "learner": "Acquire Android wake lock. Prevents Android from killing Termux background process. Needs termux-api.",
        "pro":     "termux-wake-lock. termux-wake-unlock to release. Needs termux-api pkg + Termux:API app.",
        "examples": ["termux-wake-lock"],
    },
    "termux-share": {
        "synopsis": "termux-share [file]",
        "category": "termux",
        "noob":    "Shares a file from Termux using your phone's normal share sheet — like sharing from any other app.",
        "learner": "Share file via Android intent. Opens share sheet. -a action, -t mimetype. Needs termux-api.",
        "pro":     "termux-share file. termux-share -a send -t text/plain file.",
        "examples": ["termux-share myfile.txt"],
    },

    # --- tmux ---
    "tmux": {
        "synopsis": "tmux [command]",
        "category": "terminal",
        "noob":    "Lets you run multiple terminal sessions and keeps things running even if you close Termux. Very useful for long tasks.",
        "learner": "Terminal multiplexer. Ctrl+B prefix for all commands. % split vertical, \" split horizontal, d detach, s sessions.",
        "pro":     "tmux new -s name. tmux attach -t name. Ctrl+B: % | \" d c n p x z.",
        "examples": ["tmux", "tmux new -s work", "tmux attach -t work"],
    },
}

# ---------------------------------------------------------------------------
# Explainer functions
# ---------------------------------------------------------------------------

def _normalize_cmd(cmd: str) -> str:
    """Normalize command input for lookup."""
    return cmd.strip().lower()


def lookup(cmd: str) -> dict | None:
    """Find a command entry. Tries exact match then prefix match."""
    key = _normalize_cmd(cmd)
    if key in COMMAND_DICT:
        return COMMAND_DICT[key]
    # Try just the first word
    first_word = key.split()[0]
    if first_word in COMMAND_DICT:
        return COMMAND_DICT[first_word]
    return None


def explain(cmd: str, mode: str = "learner") -> str:
    """
    Explain a command in plain English.
    Mode-aware depth: noob=story, learner=educational, pro=one-line.
    Returns formatted explanation string.
    """
    entry = lookup(cmd)

    if not entry:
        return (
            f"I don't have offline documentation for '{cmd}' yet.\n"
            f"Try: man {cmd.split()[0]}  or  {cmd.split()[0]} --help"
        )

    desc = entry.get(mode, entry.get("learner", ""))
    synopsis = entry.get("synopsis", cmd)
    examples = entry.get("examples", [])
    category = entry.get("category", "")

    if mode == "noob":
        lines = [
            f"  📖  {cmd.upper()}",
            f"",
            f"  {desc}",
        ]
        if examples:
            lines += ["", f"  Example:  {examples[0]}"]

    elif mode == "learner":
        lines = [
            f"  📖  {cmd.upper()}  —  {synopsis}",
            f"  Category: {category}",
            f"",
            f"  {desc}",
        ]
        if examples:
            lines += ["", "  Examples:"]
            for ex in examples[:3]:
                lines.append(f"    $ {ex}")

    else:  # pro
        lines = [f"  {synopsis}  —  {desc}"]
        if examples:
            lines.append(f"  eg: {examples[0]}")

    return "\n".join(lines)


def dictionary_lookup(cmd: str) -> str:
    """
    Concise one-line definition + synopsis.
    Used for quick inline lookups.
    """
    entry = lookup(cmd)
    if not entry:
        return f"'{cmd}' not found in offline dictionary."
    synopsis = entry.get("synopsis", cmd)
    desc     = entry.get("learner", entry.get("noob", ""))[:80]
    return f"  {synopsis}  —  {desc}"


def list_commands(category: str = None) -> list[str]:
    """List all known commands, optionally filtered by category."""
    if category:
        return [k for k, v in COMMAND_DICT.items()
                if v.get("category") == category]
    return list(COMMAND_DICT.keys())


def search_commands(query: str) -> list[tuple[str, str]]:
    """
    Search command dictionary by keyword in name or description.
    Returns list of (command, one-line-description).
    """
    query = query.lower()
    results = []
    for cmd, entry in COMMAND_DICT.items():
        combined = (cmd + " " + entry.get("noob", "") + " " +
                    entry.get("learner", "")).lower()
        if query in combined:
            results.append((cmd, entry.get("learner", "")[:70]))
    return results

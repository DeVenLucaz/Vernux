# =============================================================================
# vernux.py — VERNUX Entry Point & CLI
# Version: 0.6.0 | Phase 5 — Polish & Release
# =============================================================================

import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules                import VERSION, PHASE_NAME
from modules.config         import load_config, save_config, get as config_get, set_value
from modules.device         import load_profile, build_profile
from modules.matcher        import match, load_patterns
from modules.safety         import classify, requires_confirmation, requires_explicit_yes
from modules.executor       import run, resolve_new_cwd, fill_params
from modules.mode           import get_mode, get_description, format_pre_run, format_result
from modules.doctor         import run_all_checks, run_quick_checks
from modules.explainer      import explain, search_commands, library_available, library_size, list_categories, lookup as lib_lookup
from modules.packages       import resolve_name, get_install_advice, format_install_advice
from modules.reality_bridge import explain_scenario
from modules.context        import get_session
from modules.recipes        import match_recipe, run_recipe, load_recipes
from modules.notify         import build_pre_task_notice
from modules.updater        import run_full_update, check_for_update
from modules.interpreter    import (
    query as llm_query, is_available as llm_available,
    query_explain as llm_query_explain,
    select_model, list_installed_models,
    download_model, get_download_advice
)
from modules                import ui


# ---------------------------------------------------------------------------
# First-run setup
# ---------------------------------------------------------------------------
def first_run_setup():
    print()
    print(f"{ui.CYAN}{ui.BOLD}╔════════════════════════════════════════╗{ui.RESET}")
    print(f"{ui.CYAN}{ui.BOLD}║         Welcome to VERNUX              ║{ui.RESET}")
    print(f"{ui.CYAN}{ui.BOLD}║   Natural Language for Termux          ║{ui.RESET}")
    print(f"{ui.CYAN}{ui.BOLD}║   v{VERSION:<35}║{ui.RESET}")
    print(f"{ui.CYAN}{ui.BOLD}╚════════════════════════════════════════╝{ui.RESET}")
    print()
    print("  First, which mode suits you?")
    print()
    print(f"  {ui.GREEN}[1] 🟢 Noob{ui.RESET}    — Never used a terminal before")
    print(f"  {ui.YELLOW}[2] 🟡 Learner{ui.RESET} — Know a little, want to learn more")
    print(f"  {ui.RED}[3] 🔴 Pro{ui.RESET}     — Know what I'm doing, want speed")
    print()
    mode_map = {"1": "noob", "2": "learner", "3": "pro"}
    mode = None
    while mode is None:
        try:
            choice = input("  Your choice (1/2/3): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            sys.exit(0)
        mode = mode_map.get(choice)
        if mode is None:
            print("  Please enter 1, 2, or 3.")
    cfg = load_config()
    cfg["mode"]      = mode
    cfg["first_run"] = False
    save_config(cfg)
    print()
    print(f"  {ui.GREEN}✔{ui.RESET}  Mode set to {ui.BOLD}{mode.upper()}{ui.RESET}")
    print()
    print("  📱 Profiling your device...")
    profile = build_profile()
    ui.print_device_card(profile)
    if not profile["storage"]["sdcard_available"]:
        print(f"  {ui.YELLOW}⚠  Storage not set up.{ui.RESET}")
        print(f"  {ui.GRAY}   Say: 'fix termux storage access' to set it up{ui.RESET}\n")
    print(f"  {ui.GREEN}✅ Setup complete.{ui.RESET} Type what you want to do.")
    print(f"  {ui.GRAY}   Type 'help' for examples. Type 'exit' to quit.{ui.RESET}\n")


# ---------------------------------------------------------------------------
# Explain handler
# ---------------------------------------------------------------------------
def handle_explain(args_str: str, mode: str):
    """
    Explain a command or search the library.
    Priority: COMMAND_DICT -> library.json -> close-match suggestions -> LLM
    """
    cmd = args_str.strip()
    if not cmd:
        lib_count = library_size()
        hint = f" ({lib_count} commands available)" if lib_count else ""
        print(f"\n  {ui.YELLOW}Usage: explain <command>{ui.RESET}{hint}\n")
        return

    # Search mode — keyword search across dict + library
    if cmd.startswith("search "):
        query   = cmd[7:].strip()
        results = search_commands(query)
        if results:
            print(f"\n  {ui.CYAN}Commands matching \'{query}\':{ui.RESET}")
            for name, desc in results[:12]:
                print(f"  {ui.BOLD}{name:<22}{ui.RESET} {ui.GRAY}{desc}{ui.RESET}")
            print()
        else:
            print(f"\n  {ui.GRAY}No commands found for \'{query}\'.{ui.RESET}\n")
        return

    # Step 1: offline lookup (COMMAND_DICT + library.json)
    result = explain(cmd, mode)
    not_found = (
        "I don\'t have offline documentation" in result or
        "not found in offline" in result or
        "not have offline" in result
    )

    if not not_found:
        print()
        print(result)
        print()
        return

    # Step 2: library search for close matches on partial/misspelled input
    close = search_commands(cmd)
    if close:
        print(f"\n  {ui.GRAY}No exact match for \'{cmd}\'. Similar commands:{ui.RESET}")
        for name, desc in close[:5]:
            print(f"  {ui.CYAN}▸{ui.RESET}  {ui.BOLD}{name:<22}{ui.RESET} {ui.GRAY}{desc[:60]}{ui.RESET}")
        print(f"\n  {ui.GRAY}Try: explain {close[0][0]}{ui.RESET}\n")
        return

    # Step 3: LLM explain fallback
    if llm_available():
        print(f"\n  {ui.GRAY}Looking that up with AI...{ui.RESET}\n")
        with ui.Spinner("Thinking (local AI)"):
            ai_answer = llm_query_explain(cmd)
        if ai_answer:
            print()
            print(f"  {ui.CYAN}🤖 AI explains:{ui.RESET}")
            for line in ai_answer.splitlines():
                if line.strip():
                    print(f"  {line.strip()}")
            print()
            return

    # Final fallback — show the not-found message
    print()
    print(result)
    print()


# ---------------------------------------------------------------------------
# Package intelligence
# ---------------------------------------------------------------------------
def check_package_before_install(user_input: str, mode: str) -> str | None:
    for pat in [r"install\s+(\S+)", r"get\s+(\S+)",
                r"need\s+(\S+)", r"pkg install\s+(\S+)"]:
        m = re.search(pat, user_input.lower())
        if m:
            pkg     = m.group(1).rstrip(".,")
            profile = load_profile()
            ram_gb  = profile.get("ram", {}).get("available_gb", 4.0)
            advice  = get_install_advice(pkg, mode, ram_gb)
            msg     = format_install_advice(advice, mode)
            if msg.strip():
                return msg
            if advice["remapped"]:
                return f"  {ui.GRAY}(using '{advice['real_name']}' — correct Termux name){ui.RESET}"
    return None


# ---------------------------------------------------------------------------
# Intent detection — question vs action
# ---------------------------------------------------------------------------

_QUESTION_PATTERNS = re.compile(
    r"^(what\s+is|what\s+are|what\s+does|what'?s|"
    r"how\s+does|how\s+do\s+i|how\s+to|"
    r"explain|tell\s+me\s+about|describe|"
    r"why\s+is|why\s+does|why\s+do|"
    r"when\s+to\s+use|what\s+can\s+i\s+do\s+with|"
    r"difference\s+between|compare|vs\b|"
    r"is\s+\w+\s+(a|an|the)|can\s+i)\b",
    re.IGNORECASE
)

def _is_question(user_input: str) -> bool:
    """Returns True if input looks like an explanation/question query."""
    return bool(_QUESTION_PATTERNS.match(user_input.strip()))


def _extract_topic(user_input: str) -> str:
    """Pull the core topic word(s) from a question for follow-up hints."""
    # Strip common question prefixes
    cleaned = re.sub(
        r"^(what\s+is|what\s+are|what\s+does|what'?s|how\s+does|"
        r"explain|tell\s+me\s+about|describe|why\s+is|why\s+does|"
        r"how\s+do\s+i|how\s+to|when\s+to\s+use|is\s+a|can\s+i)\s+",
        "", user_input.strip(), flags=re.IGNORECASE
    ).strip()
    # Return first 3 words max
    return " ".join(cleaned.split()[:3])


# ---------------------------------------------------------------------------
# LLM fallback
# ---------------------------------------------------------------------------
def try_llm_fallback(user_input: str, mode: str) -> bool:
    if not llm_available():
        return False

    session = get_session()
    profile = load_profile()
    brand   = profile.get("brand", "")

    # --- Intent detection: question vs action ---
    if _is_question(user_input):
        return _llm_explain_flow(user_input, mode)

    # --- Action flow: generate bash command ---
    command = None
    with ui.Spinner("Thinking (local AI)"):
        command = llm_query(user_input)
    if not command:
        # Command query but AI returned nothing — try explain as last resort
        return _llm_explain_flow(user_input, mode)

    print()
    if mode == "noob":
        print(f"  {ui.CYAN}🤖 The AI suggests:{ui.RESET}")
        print(f"  {command}")
    elif mode == "learner":
        print(f"  {ui.CYAN}🤖 AI generated:{ui.RESET}")
        print(f"  {ui.GRAY}$ {command}{ui.RESET}")
    else:  # pro
        print(f"  {ui.GRAY}$ {command}{ui.RESET}")

    safety = classify(command, session.to_safety_context())
    level  = safety["level"]
    if safety["hard_stop"]:
        ui.print_safety_warning("skull", safety["reason"])
        print(f"  {ui.RED}AI suggested a dangerous command. Not running.{ui.RESET}\n")
        return True
    if level != "green":
        ui.print_safety_warning(level, safety["reason"])
    notice = build_pre_task_notice(command, brand, mode)
    if notice:
        print(notice)
    if not ui.confirm("Run this AI-generated command?"):
        ui.print_info("Cancelled.")
        return True
    exec_result = run(command, cwd=session.get_cwd())
    if exec_result["exit_code"] == 0:
        session.update_cwd(resolve_new_cwd(command, session.get_cwd()))
    session.log_command(user_input, command, exec_result["exit_code"])
    ui.print_result(exec_result["stdout"], exec_result["stderr"],
                    exec_result["exit_code"], mode, exec_result["translated_error"],
                    command=command)
    if exec_result["exit_code"] == 0 and not exec_result["stdout"].strip():
        ui.print_success("Done.", mode)
    return True


def _llm_explain_flow(user_input: str, mode: str) -> bool:
    """
    Handle explanation/question queries via AI.
    Mode-aware output:
      noob    — plain English answer, then friendly 'learn more' prompt
      learner — explanation + related command shown with breakdown hint
      pro     — concise answer + command on one line, no hand-holding
    Returns True if AI gave a useful answer, False otherwise.
    """
    answer = None
    with ui.Spinner("Thinking (local AI)"):
        answer = llm_query_explain(user_input)
    if not answer:
        return False

    topic = _extract_topic(user_input)
    print()

    if mode == "noob":
        print(f"  {ui.CYAN}🤖 Here's what that means:{ui.RESET}")
        print()
        for line in answer.splitlines():
            if line.strip():
                print(f"  {line.strip()}")
        print()
        print(f"  {ui.GREEN}Want to learn more?{ui.RESET}")
        print(f"  {ui.GRAY}Try: explain {topic}   or   library {topic}{ui.RESET}")
        print()

    elif mode == "learner":
        print(f"  {ui.CYAN}🤖 AI explains:{ui.RESET}")
        print()
        for line in answer.splitlines():
            if line.strip():
                print(f"  {line.strip()}")
        print()
        # Try to also surface a related command hint
        results = search_commands(topic)
        if results:
            name, desc = results[0]
            print(f"  {ui.GRAY}Related command: {ui.BOLD}{name}{ui.RESET}{ui.GRAY} — {desc[:55]}{ui.RESET}")
            print(f"  {ui.GRAY}Try: explain {name}   or   library {name}{ui.RESET}")
        print()

    else:  # pro
        # Compact: one paragraph, then command if found
        first_para = answer.strip().splitlines()[0] if answer.strip() else answer.strip()
        print(f"  {ui.GRAY}{first_para}{ui.RESET}")
        results = search_commands(topic)
        if results:
            name, _ = results[0]
            print(f"  {ui.GRAY}→ explain {name}{ui.RESET}")
        print()

    return True

# ---------------------------------------------------------------------------
# Library auto-suggest — called from process_match on unknown input
# ---------------------------------------------------------------------------

def _extract_command_tokens(user_input: str) -> list:
    """
    Pull candidate command tokens from natural language input.
    e.g. "what does ripgrep do" → ["ripgrep"]
         "how to use curl"      → ["curl"]
         "compress files"       → ["compress", "files"]
         "find large files"     → ["find", "large", "files"]
    """
    # Strip common question words and filler
    stop = {
        "what", "does", "how", "to", "use", "do", "is", "the",
        "a", "an", "explain", "me", "i", "can", "want", "help",
        "with", "my", "about", "for", "should", "would", "like",
        "please", "could", "in", "of", "it", "this", "that",
        "tell", "show", "give", "let", "know", "make",
    }
    words = re.findall(r'[a-z0-9_\-\.]+', user_input.lower())
    return [w for w in words if w not in stop and len(w) > 1]


def library_auto_suggest(user_input: str, mode: str) -> bool:
    """
    When pattern matching fails, check the library for:
      1. Direct command name match (e.g. user typed "ripgrep" or "what is ripgrep")
      2. Keyword search match on the input words

    Returns True if we printed something useful (caller should return early).
    Returns False if nothing found (caller continues to next fallback).
    """
    if not library_available():
        return False

    tokens = _extract_command_tokens(user_input)
    if not tokens:
        return False

    # Step 1: try each token as a direct command name lookup
    for token in tokens:
        entry = lib_lookup(token)
        if entry:
            # Found a direct hit — print a compact "did you know" card
            short   = entry.get("short", entry.get("noob", ""))[:140]
            synopsis = entry.get("synopsis", token)
            examples = entry.get("examples", [])
            cat      = entry.get("category", "")

            print(f"\n  {ui.CYAN}📚 Found in library:{ui.RESET}  {ui.BOLD}{token}{ui.RESET}"
                  + (f"  {ui.GRAY}[{cat}]{ui.RESET}" if cat else ""))
            print(f"  {ui.GRAY}{synopsis}{ui.RESET}")
            if short:
                print(f"\n  {short}")
            if examples:
                print(f"\n  {ui.GRAY}Example:{ui.RESET}  {examples[0]}")
            print(f"\n  {ui.GRAY}Full entry: library {token}  |  Explain: explain {token}{ui.RESET}\n")
            return True

    # Step 2: keyword search on the raw input (max 2 words to keep it focused)
    query   = " ".join(tokens[:3])
    results = search_commands(query)
    if results:
        # Only show if at least one result looks relevant (name or desc contains a token)
        relevant = [
            (name, desc) for name, desc in results
            if any(t in name or t in desc.lower() for t in tokens)
        ]
        if relevant:
            print(f"\n  {ui.CYAN}📚 Library suggestions for '{user_input}':{ui.RESET}\n")
            for name, desc in relevant[:4]:
                entry   = lib_lookup(name)
                ex      = entry.get("examples", [""])[0] if entry else ""
                print(f"  {ui.BOLD}{name:<22}{ui.RESET}  {ui.GRAY}{desc[:55]}{ui.RESET}")
                if ex:
                    print(f"  {ui.GRAY}  eg: {ex}{ui.RESET}")
            print(f"\n  {ui.GRAY}More: library search {query}{ui.RESET}\n")
            return True

    return False

def process_match(user_input: str, mode: str) -> None:
    session = get_session()
    profile = load_profile()
    brand   = profile.get("brand", "")
    rb = explain_scenario(user_input, mode, brand)
    if rb:
        print(f"\n{ui.CYAN}  💡 VERNUX knows this:{ui.RESET}")
        for line in rb.splitlines():
            print(f"  {line}")
        print()
    result = match(user_input)
    if not result["found"]:
        # Priority 1: LLM fallback (if model is installed)
        if try_llm_fallback(user_input, mode):
            return
        # Priority 2: library auto-suggest (offline, no model needed)
        if library_auto_suggest(user_input, mode):
            return
        # Priority 3: fuzzy pattern candidates ("did you mean?")
        if result["candidates"]:
            ui.print_did_you_mean(result["candidates"])
        else:
            # Dead end — show install-model tip or rephrase hint
            if library_available():
                tip = "try: explain <command>  or  library search <term>"
            elif not llm_available():
                tip = "type 'install-model' to add AI, or try: library search <term>"
            else:
                tip = "try rephrasing"
            ui.print_info(f"I don't know how to do that yet. {tip}.")
        return
    pattern = result["pattern"]
    params  = result["params"]
    command = fill_params(pattern.get("command", ""), params)
    if "pkg install" in command or "pip install" in command:
        pkg_advice = check_package_before_install(user_input, mode)
        if pkg_advice:
            print(pkg_advice)
            if "already installed" in pkg_advice.lower() and mode != "pro":
                if not ui.confirm("Install anyway?"):
                    return
    safety = classify(command, session.to_safety_context())
    level  = safety["level"]
    if safety["hard_stop"]:
        ui.print_safety_warning("skull", safety["reason"])
        print(f"  {ui.RED}This command will not run.{ui.RESET}\n")
        return
    display = format_pre_run(pattern, mode, params)
    print()
    print(f"  {display['description']}")
    if display["show_command"]:
        if mode == "learner" and display["command_parts"]:
            ui.print_command_parts(command, display["command_parts"])
        else:
            ui.print_command(command, mode)
    if level != "green":
        ui.print_safety_warning(level, safety["reason"])
    if mode == "learner" and pattern.get("undo"):
        ui.print_info(f"Undo: {pattern['undo']}")
    notice = build_pre_task_notice(command, brand, mode)
    if notice:
        print(notice)
    if requires_confirmation(mode, level):
        confirmed = ui.confirm("Run this?", require_yes=requires_explicit_yes(level))
        if not confirmed:
            ui.print_info("Cancelled.")
            return
    exec_result = run(command, cwd=session.get_cwd())
    if exec_result["exit_code"] == 0:
        new_cwd = resolve_new_cwd(command, session.get_cwd())
        session.update_cwd(new_cwd)
        if "pkg install" in command:
            parts = command.split()
            if len(parts) >= 3:
                session.track_installed(parts[2])
    session.log_command(user_input, command, exec_result["exit_code"])
    ui.print_result(exec_result["stdout"], exec_result["stderr"],
                    exec_result["exit_code"], mode, exec_result["translated_error"],
                    command=command)
    if exec_result["exit_code"] == 0 and not exec_result["stdout"].strip():
        ui.print_success("Done.", mode)




# ---------------------------------------------------------------------------
# Library browser
# ---------------------------------------------------------------------------

def handle_library(args_str: str, mode: str):
    """
    Offline command library browser.

    library                   — show library status + usage
    library <command>         — full entry for a command
    library search <term>     — keyword search
    library category <name>   — list commands in a category
    library categories        — list all categories
    library related <command> — find commands in same category
    """
    from modules.explainer import (
        lookup, list_categories, list_commands,
        library_available, library_size, search_commands as lib_search,
        explain as lib_explain,
    )

    args = args_str.strip()

    # ── No args: status + usage ───────────────────────────────────────────
    if not args or args in ("help", "?"):
        lib_count = library_size()
        if lib_count:
            print(f"\n  {ui.CYAN}{ui.BOLD}📚 Command Library{ui.RESET}  {ui.GREEN}●{ui.RESET} {lib_count} commands, 100% offline")
        else:
            print(f"\n  {ui.CYAN}{ui.BOLD}📚 Command Library{ui.RESET}  {ui.RED}●{ui.RESET} not built yet")
            print(f"  {ui.GRAY}Build it: python tools/fetch_library.py{ui.RESET}\n")
            return
        cats = list_categories()
        cat_preview = ", ".join(sorted(cats)[:8])
        print(f"  {ui.GRAY}{len(cats)} categories: {cat_preview}...{ui.RESET}\n")
        print(f"  {ui.BOLD}Usage:{ui.RESET}")
        rows = [
            ("library grep",           "full entry for any command"),
            ("library search <term>",  "keyword search across all commands"),
            ("library category files", "list commands in a category"),
            ("library categories",     "list all categories"),
            ("library related grep",   "find commands in the same category"),
        ]
        for cmd, desc in rows:
            print(f"  {ui.CYAN}{cmd:<32}{ui.RESET} {ui.GRAY}{desc}{ui.RESET}")
        print()
        return

    # ── categories ────────────────────────────────────────────────────────
    if args in ("categories", "cats"):
        cats = list_categories()
        print(f"\n  {ui.CYAN}{ui.BOLD}Library Categories ({len(cats)}){ui.RESET}\n")
        for cat in sorted(cats):
            cmds = list_commands(category=cat)
            print(f"  {ui.BOLD}{cat:<16}{ui.RESET}  {ui.GRAY}{len(cmds):3d} commands{ui.RESET}")
        print()
        return

    # ── category <name> ───────────────────────────────────────────────────
    if args.startswith(("category ", "cat ")):
        cat  = args.split(" ", 1)[1].strip()
        cmds = sorted(list_commands(category=cat))
        if not cmds:
            print(f"\n  {ui.GRAY}No commands found for category '{cat}'.{ui.RESET}")
            cats = list_categories()
            print(f"  Available: {', '.join(sorted(cats))}{ui.RESET}\n")
            return
        print(f"\n  {ui.CYAN}{ui.BOLD}{cat.upper()} — {len(cmds)} commands{ui.RESET}\n")
        col_w = 20
        cols  = 4
        for i in range(0, len(cmds), cols):
            row = cmds[i:i + cols]
            print("  " + "".join(f"{c:<{col_w}}" for c in row))
        print()
        return

    # ── search <term> ─────────────────────────────────────────────────────
    if args.startswith(("search ", "find ")):
        query   = args.split(" ", 1)[1].strip()
        results = lib_search(query)
        if not results:
            print(f"\n  {ui.GRAY}No results for '{query}'.{ui.RESET}\n")
            return
        print(f"\n  {ui.CYAN}Results for '{query}'  ({len(results)} found){ui.RESET}\n")
        for name, desc in results[:15]:
            entry  = lookup(name)
            cat    = entry.get("category", "") if entry else ""
            cat_tag = f"  {ui.GRAY}[{cat}]{ui.RESET}" if cat else ""
            print(f"  {ui.BOLD}{name:<22}{ui.RESET}{cat_tag}")
            if desc:
                print(f"  {ui.GRAY}  {desc[:72]}{ui.RESET}")
        print()
        return

    # ── related <command> ─────────────────────────────────────────────────
    if args.startswith(("related ", "rel ")):
        cmd_name = args.split(" ", 1)[1].strip()
        entry    = lookup(cmd_name)
        if not entry:
            print(f"\n  {ui.GRAY}'{cmd_name}' not found in library.{ui.RESET}\n")
            return
        cat = entry.get("category", "")
        if not cat:
            print(f"\n  {ui.GRAY}No category info for '{cmd_name}'.{ui.RESET}\n")
            return
        cmds = sorted(c for c in list_commands(category=cat) if c != cmd_name)
        print(f"\n  {ui.CYAN}Related to '{cmd_name}'  (category: {cat}){ui.RESET}\n")
        col_w = 20
        cols  = 4
        for i in range(0, len(cmds), cols):
            row = cmds[i:i + cols]
            print("  " + "".join(f"{c:<{col_w}}" for c in row))
        print()
        return

    # ── default: look up a specific command ──────────────────────────────
    entry = lookup(args)
    if not entry:
        close = lib_search(args)
        if close:
            print(f"\n  {ui.GRAY}'{args}' not found. Similar commands:{ui.RESET}")
            for name, desc in close[:5]:
                print(f"  {ui.CYAN}▸{ui.RESET}  {ui.BOLD}{name:<22}{ui.RESET} {ui.GRAY}{desc[:60]}{ui.RESET}")
            print(f"\n  {ui.GRAY}Try: library {close[0][0]}{ui.RESET}\n")
        else:
            hint = "run: python tools/fetch_library.py" if not library_available() else "try: library search <term>"
            print(f"\n  {ui.GRAY}'{args}' not found. ({hint}){ui.RESET}\n")
        return

    # Rich command card
    result = lib_explain(args, mode)
    cat    = entry.get("category", "")
    if cat and mode != "pro":
        result += f"\n\n  {ui.GRAY}Related: library related {args}{ui.RESET}"
    print()
    print(result)
    print()


# ---------------------------------------------------------------------------
# Stats (session summary)
# ---------------------------------------------------------------------------
def handle_stats(mode: str):
    session  = get_session()
    summary  = session.get_session_summary()
    profile  = load_profile()
    patterns = load_patterns()
    recipes  = load_recipes()
    installed = list_installed_models()
    print()
    print(f"  {ui.BOLD}VERNUX Session Stats{ui.RESET}")
    print(f"  {ui.GRAY}{'─' * 38}{ui.RESET}")
    print(f"  Commands run this session : {summary['commands_run']}")
    print(f"  Packages installed        : {len(summary['packages_installed'])}")
    if summary['packages_installed']:
        print(f"  {ui.GRAY}    {', '.join(summary['packages_installed'][:5])}{ui.RESET}")
    print(f"  Current directory         : {summary['cwd']}")
    print(f"  {ui.GRAY}{'─' * 38}{ui.RESET}")
    print(f"  VERNUX version : v{config_get('version', '0.6.0')} — {PHASE_NAME}")
    print(f"  Mode           : {config_get('mode','noob').upper()}")
    print(f"  Patterns loaded: {len(patterns)}")
    print(f"  Recipes loaded : {len(recipes)}")
    ram = profile.get('ram', {}).get('total_gb', 0)
    tier = profile.get('tier', '?')
    print(f"  Device         : {profile.get('brand','?').capitalize()}, {ram:.1f}GB RAM ({tier})")
    if installed:
        print(f"  AI model       : {installed[0]['name']}")
    else:
        print(f"  AI model       : not installed")
    if library_available():
        print(f"  Command library: {library_size()} commands (Linux Command Library)")
    else:
        print(f"  Command library: not built  (run: python tools/fetch_library.py)")
    print()


# ---------------------------------------------------------------------------
# Model installer
# ---------------------------------------------------------------------------
def handle_install_model(mode: str):
    profile = load_profile()
    ram_gb  = profile.get("ram", {}).get("total_gb", 2.0)
    tier    = profile.get("tier", "low")
    from modules.interpreter import _load_models
    installed = list_installed_models()
    if installed:
        print(f"\n  {ui.GREEN}Installed models:{ui.RESET}")
        for m in installed:
            print(f"  ✔  {m['name']} ({m['actual_size_mb']}MB)")
        print()
        if not ui.confirm("Download another model?"):
            return
    data       = _load_models()
    compatible = [m for m in data.get("models", []) if ram_gb >= m["min_ram_gb"]]
    if not compatible:
        ui.print_error(f"No compatible models for {ram_gb:.1f}GB RAM.")
        return
    print(f"\n  {ui.BOLD}Compatible models ({ram_gb:.1f}GB RAM device):{ui.RESET}\n")
    for i, m in enumerate(compatible, 1):
        size_str = f"{m['size_mb']}MB"
        rec = " ← recommended" if ram_gb >= m["recommended_ram_gb"] else ""
        print(f"  [{i}] {m['name']:<35} {size_str}{ui.GREEN}{rec}{ui.RESET}")
    print()
    try:
        choice = input(f"  {ui.CYAN}Choose (1-{len(compatible)}): {ui.RESET}").strip()
        idx = int(choice) - 1
        if not 0 <= idx < len(compatible):
            raise ValueError
    except (ValueError, KeyboardInterrupt, EOFError):
        ui.print_error("Cancelled.")
        return
    model = compatible[idx]
    print(f"\n{get_download_advice(model, tier, mode)}\n")
    if not ui.confirm(f"Download {model['name']}?"):
        return
    print(f"\n  {ui.YELLOW}⚠  Keep Termux open. Use tmux for safety.{ui.RESET}\n")
    success = download_model(model)
    if success:
        set_value("llm_enabled", True)
        set_value("llm_model", model["file"])
        ui.print_success(f"Model downloaded: {model['name']}", mode)
        print(f"  {ui.GRAY}AI fallback is now active.{ui.RESET}\n")
    else:
        ui.print_error("Download failed. Check internet and try again.")


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
def print_help(mode: str):
    recipes  = load_recipes()
    llm_on   = llm_available()
    patterns = load_patterns()
    print()
    print(f"{ui.BOLD}  VERNUX v{VERSION} — {mode.upper()} mode{ui.RESET}")
    if llm_on:
        installed = list_installed_models()
        model_name = installed[0]['name'] if installed else "active"
        print(f"  {ui.GREEN}🤖 Local AI: {model_name}{ui.RESET}")
    else:
        print(f"  {ui.GRAY}🤖 Local AI: not active — type 'install-model' to add it{ui.RESET}")
    lib_count = library_size()
    if lib_count:
        print(f"  {ui.GREEN}📚 Library: {lib_count} commands (Linux Command Library){ui.RESET}")
    else:
        print(f"  {ui.GRAY}📚 Library: not built — run: python tools/fetch_library.py{ui.RESET}")
    print(f"  {ui.GRAY}{len(patterns)} patterns, {len(recipes)} recipes{ui.RESET}")
    print()
    print("  Say what you want to do:")
    for ex in ["install python", "what is grep", "check storage",
               "push my project to github", "compress folder"]:
        print(f"  {ui.GRAY}>{ui.RESET}  {ex}")
    print()
    print(f"  {ui.BOLD}Recipes:{ui.RESET}")
    for r in recipes[:5]:
        print(f"  {ui.CYAN}>{ui.RESET}  {r['triggers'][0]}")
    print(f"  {ui.GRAY}  type 'recipes' for all {len(recipes)}{ui.RESET}")
    print()
    print(f"  {ui.BOLD}Commands:{ui.RESET}")
    for cmd, desc in [
        ("vernux doctor",        "health check (23 checks)"),
        ("vernux update",        "update VERNUX + data"),
        ("vernux stats",         "session summary"),
        ("vernux explain <cmd>", "explain any command"),
        ("vernux config mode",   "noob / learner / pro"),
        ("vernux recipes",       "list all recipes"),
        ("install-model",        "add local AI model"),
        ("vernux library <cmd>",       "look up any command offline"),
        ("vernux library search <term>","keyword search across library"),
        ("vernux library related <cmd>","find commands in same category"),
        ("vernux library categories",  "list all categories"),
        ("vernux --version",     "show version"),
    ]:
        print(f"  {ui.CYAN}{cmd:<30}{ui.RESET} {ui.GRAY}{desc}{ui.RESET}")
    print()


def print_recipes_list():
    recipes = load_recipes()
    print(f"\n  {ui.BOLD}Built-in Recipes ({len(recipes)}):{ui.RESET}\n")
    for r in recipes:
        print(f"  {ui.CYAN}▶{ui.RESET}  {r['triggers'][0]:<42} {ui.GRAY}~{r.get('estimated_minutes','?')} min{ui.RESET}")
    print()


# ---------------------------------------------------------------------------
# CLI routing
# ---------------------------------------------------------------------------
def handle_update(mode: str):
    print(f"\n  {ui.CYAN}🔄 Checking for updates...{ui.RESET}\n")
    results = run_full_update(verbose=True)

    ver_info = results.get("version_check", {})
    code     = results.get("code_update", {})
    pkg      = results.get("pkg_cache", {})
    patterns = results.get("patterns", {})
    recipes  = results.get("recipes", {})

    # Version / code
    if ver_info.get("available"):
        if code.get("ok"):
            print(f"  {ui.GREEN}✔{ui.RESET}  Code updated → v{ver_info.get('latest_version', '?')}")
        else:
            print(f"  {ui.YELLOW}⚠{ui.RESET}  Code update failed: {code.get('message', 'unknown error')}")
    else:
        print(f"  {ui.GREEN}✔{ui.RESET}  Already up to date (v{ver_info.get('current_version', '?')})")

    # Data files
    for label, res in [("Package cache", pkg), ("Patterns", patterns), ("Recipes", recipes)]:
        if res and res.get("ok"):
            print(f"  {ui.GREEN}✔{ui.RESET}  {label} refreshed")
        elif res:
            print(f"  {ui.YELLOW}⚠{ui.RESET}  {label}: {res.get('message', 'skipped')}")

    print()
    if mode == "noob":
        print(f"  {ui.GRAY}VERNUX is ready to use.{ui.RESET}\n")
    else:
        print(f"  {ui.GRAY}Update complete.{ui.RESET}\n")


def handle_cli_args(args: list) -> bool:
    if not args:
        return False
    cmd = args[0].lower()

    if cmd == "doctor":
        checks = run_all_checks()
        ui.print_doctor_report(checks)
        return True

    if cmd == "update":
        handle_update(config_get("mode", "noob"))
        return True

    if cmd == "stats":
        handle_stats(config_get("mode", "noob"))
        return True

    if cmd == "config":
        if len(args) >= 3 and args[1].lower() == "mode":
            new_mode = args[2].lower()
            if new_mode in ("noob", "learner", "pro"):
                set_value("mode", new_mode)
                print(f"\n  {ui.GREEN}✔{ui.RESET}  Mode → {ui.BOLD}{new_mode.upper()}{ui.RESET}\n")
            else:
                print(f"\n  {ui.RED}✗{ui.RESET}  Unknown mode. Choose: noob, learner, pro\n")
        else:
            cfg = load_config()
            print(f"\n  Mode      : {ui.BOLD}{cfg.get('mode','noob').upper()}{ui.RESET}")
            print(f"  LLM       : {'enabled' if cfg.get('llm_enabled') else 'disabled'}")
            print(f"  First run : {cfg.get('first_run', False)}\n")
        return True

    if cmd == "explain":
        handle_explain(" ".join(args[1:]), config_get("mode", "learner"))
        return True

    if cmd == "recipes":
        print_recipes_list()
        return True

    if cmd in ("install-model", "install_model"):
        handle_install_model(config_get("mode", "noob"))
        return True

    if cmd in ("--version", "-v", "version"):
        print(f"\n  VERNUX v{VERSION} — Phase {PHASE_NAME}")
        installed = list_installed_models()
        if installed:
            print(f"  AI model  : {installed[0]['name']}")
        print()
        return True

    if cmd in ("library", "lib"):
        # vernux library grep
        # vernux library search compress
        # vernux library category files
        # vernux library related grep
        handle_library(" ".join(args[1:]), config_get("mode", "learner"))
        return True

    if cmd in ("--help", "-h"):
        print_help(config_get("mode", "noob"))
        return True

    return False


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------
def repl(mode: str):
    patterns = load_patterns()
    recipes  = load_recipes()
    llm_on   = llm_available()
    ai_str   = f" + AI" if llm_on else ""
    print(f"  {ui.GRAY}VERNUX v{VERSION} — {mode.upper()} — "
          f"{len(patterns)} patterns, {len(recipes)} recipes{ai_str}. "
          f"'help' or 'exit'.{ui.RESET}\n")
    prompt = ui.get_prompt(mode)

    while True:
        try:
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {ui.GRAY}Goodbye.{ui.RESET}\n")
            break

        if not user_input:
            continue
        lower = user_input.lower()

        if lower in ("exit", "quit", "bye", "q"):
            session = get_session()
            summary = session.get_session_summary()
            if summary["commands_run"] > 0:
                print(f"\n  {ui.GRAY}{summary['commands_run']} commands run this session. Goodbye.{ui.RESET}\n")
            else:
                print(f"\n  {ui.GRAY}Goodbye.{ui.RESET}\n")
            break

        if lower in ("help", "?", "h"):
            print_help(mode)
            continue
        if lower == "doctor":
            ui.print_doctor_report(run_all_checks())
            continue
        if lower == "quick-doctor":
            ui.print_doctor_report(run_quick_checks())
            continue
        if lower in ("update", "vernux update"):
            handle_update(mode)
            continue
        if lower in ("stats", "session stats"):
            handle_stats(mode)
            continue
        if lower in ("recipes", "list recipes"):
            print_recipes_list()
            continue
        if lower.startswith("library") or lower.startswith("lib "):
            # "library grep" → args_part="grep"
            # "lib search tar" → args_part="search tar"
            if lower.startswith("library"):
                args_part = lower[7:].strip()
            else:
                args_part = lower[4:].strip()
            handle_library(args_part, mode)
            continue
        if lower in ("install-model", "install model", "add ai", "download model"):
            handle_install_model(mode)
            continue
        if lower in ("ai status", "llm status", "model status"):
            installed = list_installed_models()
            if installed:
                for m in installed:
                    print(f"\n  {ui.GREEN}✔ {m['name']} ({m['actual_size_mb']}MB) — active{ui.RESET}\n")
            else:
                print(f"\n  {ui.GRAY}No AI model. Type 'install-model' to add one.{ui.RESET}\n")
            continue

        # Inline explain
        ex_m = (
            re.match(r"^explain\s+(.+)$", lower) or
            re.match(r"^what is\s+(.+)$", lower) or
            re.match(r"^what does\s+(\S+)", lower) or
            re.match(r"^how does\s+(\S+)", lower)
        )
        if ex_m:
            handle_explain(ex_m.group(1), mode)
            continue

        # Mode switch
        sw = re.match(r"^(switch|change)\s+mode\s+(noob|learner|pro)$", lower)
        if sw:
            mode = sw.group(2)
            set_value("mode", mode)
            prompt = ui.get_prompt(mode)
            ui.print_success(f"Switched to {mode.upper()} mode.", mode)
            continue

        # Recipe check (priority)
        profile = load_profile()
        brand   = profile.get("brand", "")
        recipe  = match_recipe(lower)
        if recipe:
            run_recipe(recipe, mode, brand)
            continue

        # Single pattern → LLM fallback
        process_match(user_input, mode)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    if handle_cli_args(args):
        return
    cfg = load_config()
    if cfg.get("first_run", True):
        first_run_setup()
        cfg = load_config()
    mode = cfg.get("mode", "noob")
    repl(mode)

if __name__ == "__main__":
    main()

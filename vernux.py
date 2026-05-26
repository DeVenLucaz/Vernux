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
from modules.explainer      import explain, search_commands
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
    cmd = args_str.strip()
    if not cmd:
        print(f"\n  {ui.YELLOW}Usage: explain <command>{ui.RESET}\n")
        return
    if cmd.startswith("search "):
        query   = cmd[7:].strip()
        results = search_commands(query)
        if results:
            print(f"\n  {ui.CYAN}Commands matching '{query}':{ui.RESET}")
            for name, desc in results[:8]:
                print(f"  {ui.BOLD}{name:<20}{ui.RESET} {ui.GRAY}{desc}{ui.RESET}")
            print()
        else:
            print(f"\n  {ui.GRAY}No commands found for '{query}'{ui.RESET}\n")
        return

    # Try offline dictionary first (works for single known commands)
    result = explain(cmd, mode)
    if "I don't have offline documentation" not in result and "not found in offline" not in result:
        print()
        print(result)
        print()
        return

    # Offline dict failed — try LLM explain query if available
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

    # Final fallback — show the offline message
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
# LLM fallback
# ---------------------------------------------------------------------------
def try_llm_fallback(user_input: str, mode: str) -> bool:
    if not llm_available():
        return False
    command = None
    with ui.Spinner("Thinking (local AI)"):
        command = llm_query(user_input)
    if not command:
        return False
    session = get_session()
    profile = load_profile()
    brand   = profile.get("brand", "")
    print()
    if mode == "noob":
        print(f"  {ui.CYAN}🤖 The AI suggests:{ui.RESET}")
        print(f"  {command}")
    else:
        print(f"  {ui.CYAN}🤖 AI generated:{ui.RESET}")
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
        if try_llm_fallback(user_input, mode):
            return
        if result["candidates"]:
            ui.print_did_you_mean(result["candidates"])
        else:
            tip = "type 'install-model' to add AI" if not llm_available() else "try rephrasing"
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
def handle_update(mode: str):
    print(f"\n  {ui.CYAN}{ui.BOLD}VERNUX Update{ui.RESET}\n")
    print(f"  {ui.GRAY}Checking for updates...{ui.RESET}")
    results = run_full_update()
    ver = results["version_check"]
    if ver.get("error"):
        ui.print_error(f"Version check failed: {ver['error']}")
    elif ver.get("available"):
        ui.print_success(f"Updated to v{ver['latest_version']}", mode)
    else:
        ui.print_info(f"Code up to date (v{ver['current_version']})")
    for key, label in [
        ("pkg_cache", "Package cache"),
        ("patterns",  "Patterns"),
        ("recipes",   "Recipes"),
    ]:
        r = results.get(key, {})
        if r.get("ok"):
            ui.print_success(f"{label}: {r.get('message','updated')}", mode)
        else:
            ui.print_error(f"{label}: {r.get('message','failed')}")
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

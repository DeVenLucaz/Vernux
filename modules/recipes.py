# =============================================================================
# modules/recipes.py — Stateful Recipe Engine
# Version: 0.4.0 | Phase 3 — Recipes
# =============================================================================

import json
import os
import re
from modules.safety   import classify
from modules.executor import run, fill_params
from modules.notify   import build_pre_task_notice
from modules.context  import get_session
from modules          import ui

RECIPES_FILE = os.path.join(os.path.dirname(__file__), "../data/recipes.json")

_RECIPES_CACHE = None

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_recipes(force_reload: bool = False) -> list[dict]:
    global _RECIPES_CACHE
    if _RECIPES_CACHE is not None and not force_reload:
        return _RECIPES_CACHE
    try:
        with open(os.path.abspath(RECIPES_FILE)) as f:
            data = json.load(f)
        _RECIPES_CACHE = data.get("recipes", [])
    except Exception:
        _RECIPES_CACHE = []
    return _RECIPES_CACHE


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_recipe(user_input: str) -> dict | None:
    """Match user input to a recipe by trigger phrases."""
    text    = user_input.lower().strip()
    recipes = load_recipes()
    best    = None
    best_score = 0
    for recipe in recipes:
        for trigger in recipe.get("triggers", []):
            if trigger in text:
                score = len(trigger)
                if score > best_score:
                    best_score = score
                    best = recipe
    return best


# ---------------------------------------------------------------------------
# Parameter collection
# ---------------------------------------------------------------------------

def _collect_params(step: dict, existing_params: dict) -> dict:
    """
    Prompt for any missing parameters that the step needs.
    Returns updated params dict.
    """
    params        = dict(existing_params)
    needed        = step.get("params_needed", [])
    prompts       = step.get("param_prompts", {})
    defaults      = step.get("param_defaults", {})

    for key in needed:
        if key in params and params[key]:
            continue  # already collected
        prompt_text = prompts.get(key, f"  {key}: ")
        default     = defaults.get(key, "")
        if default:
            prompt_text = f"  {prompt_text.rstrip()} [{default}]: "
        try:
            val = input(f"\n  {ui.CYAN}{prompt_text}{ui.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            val = ""
        if not val and default:
            val = default
        params[key] = val

    return params


# ---------------------------------------------------------------------------
# Prerequisite check
# ---------------------------------------------------------------------------

def _check_prereq(step: dict, mode: str) -> bool:
    """
    Check if a prerequisite command is available.
    If not, install it automatically.
    Returns True if prereq is satisfied.
    """
    prereq = step.get("prereq_check")
    if not prereq:
        return True

    result = run(f"command -v {prereq}")
    if result["exit_code"] == 0 and result["stdout"].strip():
        return True

    install_cmd = step.get("prereq_install", f"pkg install {prereq} -y")
    if mode != "pro":
        print(f"\n  {ui.YELLOW}  {prereq} not found. Installing...{ui.RESET}")
    result2 = run(install_cmd)
    if result2["exit_code"] == 0:
        if mode != "pro":
            ui.print_success(f"{prereq} installed.", mode)
        return True
    else:
        ui.print_error(f"Failed to install {prereq}: {result2['stderr'][:80]}")
        return False


# ---------------------------------------------------------------------------
# Single step runner
# ---------------------------------------------------------------------------

def _run_step(step: dict, params: dict, mode: str,
              brand: str = "", dry_run: bool = False) -> dict:
    """
    Execute one recipe step.

    Returns:
      {
        ok:          bool
        output:      str
        skipped:     bool
        params:      dict  (may be updated with newly collected values)
        abort:       bool  (user chose to stop)
      }
    """
    session = get_session()

    # Collect missing params
    params = _collect_params(step, params)

    # Build command
    raw_command = step.get("command", "")
    command     = fill_params(raw_command, params)

    # Show step header
    step_title = step.get("title", step["id"])
    desc_key   = f"description_{mode}"
    desc       = step.get(desc_key, step.get("description_learner", "")).strip()
    desc       = fill_params(desc, params)

    print()
    print(f"  {ui.CYAN}{ui.BOLD}▶ {step_title}{ui.RESET}")
    if desc and mode != "pro":
        for line in desc.splitlines():
            print(f"  {line}")

    # Show command (learner/pro)
    if mode != "noob":
        print(f"  {ui.GRAY}$ {command}{ui.RESET}")

    # Long task notice
    notice = build_pre_task_notice(command, brand, mode)
    if notice and mode != "pro":
        print(notice)

    # Optional step
    if step.get("optional"):
        msg = step.get("optional_message", "Run this step?")
        if not ui.confirm(msg):
            return {"ok": True, "output": "", "skipped": True,
                    "params": params, "abort": False}

    # Safety classification
    safety = classify(command, session.to_safety_context())
    level  = safety["level"]

    if safety["hard_stop"]:
        ui.print_safety_warning("skull", safety["reason"])
        return {"ok": False, "output": "", "skipped": False,
                "params": params, "abort": True}

    if level != "green":
        ui.print_safety_warning(level, safety["reason"])

    # Confirmation for risky steps (always confirm in recipe context)
    needs_confirm = level in ("yellow", "red", "skull") or mode == "noob"
    if needs_confirm and not dry_run:
        if not ui.confirm("Continue with this step?",
                          require_yes=(level == "skull")):
            return {"ok": False, "output": "", "skipped": False,
                    "params": params, "abort": True}

    if dry_run:
        return {"ok": True, "output": "[dry run]", "skipped": False,
                "params": params, "abort": False}

    # Execute
    result = run(command, cwd=session.get_cwd())

    # Update cwd if it changed
    if "cd " in command and result["exit_code"] == 0:
        for part in command.split("&&"):
            part = part.strip()
            if part.startswith("cd "):
                from modules.executor import resolve_new_cwd
                new_cwd = resolve_new_cwd(part, session.get_cwd())
                session.update_cwd(new_cwd)

    # Show output
    if result["exit_code"] == 0:
        if result["stdout"].strip() and mode != "noob":
            lines = result["stdout"].strip().splitlines()
            for line in lines[:10]:  # Cap at 10 lines
                print(f"  {ui.GRAY}{line}{ui.RESET}")
    else:
        err = result["translated_error"] or result["stderr"].strip()[:120]
        ui.print_error(err or f"Step failed (exit {result['exit_code']})")

    # Pause after (e.g. "add SSH key to GitHub, press Enter")
    if step.get("pause_after") and result["exit_code"] == 0:
        pause_msg = fill_params(step.get("pause_message", "Press Enter to continue: "), params)
        try:
            input(f"\n  {ui.YELLOW}{pause_msg}{ui.RESET}")
        except (KeyboardInterrupt, EOFError):
            pass

    session.log_command(step["id"], command, result["exit_code"])

    return {
        "ok":      result["exit_code"] == 0,
        "output":  result["stdout"],
        "skipped": False,
        "params":  params,
        "abort":   False,
    }


# ---------------------------------------------------------------------------
# Conditional step logic
# ---------------------------------------------------------------------------

def _should_skip_step(step: dict, prev_output: str, session_params: dict) -> bool:
    """
    Evaluate conditional logic for a step.
    Returns True if this step should be skipped.
    """
    # if_output_contains: only run if previous output matches
    if_contains = step.get("if_output_contains")
    if if_contains and if_contains not in prev_output:
        return True  # condition not met, skip

    # if_empty_run: only run if previous output was empty
    if step.get("if_empty_run") and prev_output.strip():
        return True

    return False


# ---------------------------------------------------------------------------
# Main recipe runner
# ---------------------------------------------------------------------------

def run_recipe(recipe: dict, mode: str, brand: str = "") -> bool:
    """
    Execute a recipe end-to-end.

    Returns True if completed successfully, False if aborted/failed.
    """
    session = get_session()
    title   = recipe.get("title", recipe["id"])
    steps   = recipe.get("steps", [])[:]
    est_min = recipe.get("estimated_minutes", "?")

    # Recipe header
    print()
    print(f"{ui.CYAN}{ui.BOLD}{'═' * 46}{ui.RESET}")
    print(f"{ui.CYAN}{ui.BOLD}  📋 RECIPE: {title}{ui.RESET}")
    if recipe.get("description") and mode != "pro":
        print(f"{ui.GRAY}  {recipe['description']}{ui.RESET}")
    print(f"{ui.GRAY}  Estimated time: ~{est_min} min  |  {len(steps)} steps{ui.RESET}")
    if recipe.get("requires_internet"):
        print(f"{ui.YELLOW}  ⚠  Internet required{ui.RESET}")
    print(f"{ui.CYAN}{ui.BOLD}{'═' * 46}{ui.RESET}")

    # Step preview — show what the recipe will do before asking yes/no
    if mode != "pro":
        print(f"\n  {ui.BOLD}What this will do:{ui.RESET}")
        for i, step in enumerate(steps, 1):
            key = "description_noob" if mode == "noob" else "description_learner"
            desc = step.get(key) or step.get("title", "")
            # Take only first line of description for preview
            first_line = desc.splitlines()[0][:70] if desc else step.get("title", "")
            print(f"  {ui.GRAY}{i:2d}. {first_line}{ui.RESET}")

        # Show what info it needs from the user
        params_needed = []
        param_prompts_all = {}
        for step in steps:
            for p in step.get("params_needed", []):
                if p not in params_needed:
                    params_needed.append(p)
                    param_prompts_all[p] = step.get("param_prompts", {}).get(p, p)

        if params_needed:
            print(f"\n  {ui.BOLD}It will ask you for:{ui.RESET}")
            for p in params_needed:
                print(f"  {ui.GRAY}  • {param_prompts_all[p]}{ui.RESET}")
        print()

    # Confirm before starting (noob/learner)
    if mode != "pro":
        if not ui.confirm("  Start this recipe?"):
            ui.print_info("Recipe cancelled.")
            return False

    # Shared param store — carries across all steps
    params       = {}
    prev_output  = ""
    completed    = 0
    total        = len(steps)

    # Get recipe-level params if any step needs them upfront
    # (We collect lazily per-step instead, which is friendlier)

    for i, step in enumerate(steps, 1):
        step_id = step.get("id", f"step_{i}")

        # Progress indicator
        print()
        print(f"  {ui.GRAY}Step {i}/{total}{ui.RESET}", end="")

        # Conditional skip check
        if _should_skip_step(step, prev_output, params):
            print(f"  {ui.GRAY}(skipping — condition not met){ui.RESET}")
            continue

        # Prereq check
        if not _check_prereq(step, mode):
            print(f"\n  {ui.RED}Cannot continue — prerequisite failed.{ui.RESET}")
            _print_checkpoint_summary(completed, total, title)
            return False

        # Run the step
        result = _run_step(step, params, mode, brand)

        # Update shared params with any newly collected values
        params.update(result["params"])

        if result["abort"]:
            print(f"\n  {ui.YELLOW}Recipe stopped at step {i}.{ui.RESET}")
            _print_checkpoint_summary(completed, total, title)
            return False

        if result["skipped"]:
            print(f"  {ui.GRAY}  (step skipped){ui.RESET}")
            continue

        if not result["ok"]:
            print(f"\n  {ui.RED}Step {i} failed: '{step.get('title', step_id)}'{ui.RESET}")
            _print_checkpoint_summary(completed, total, title)

            # Offer to retry or skip
            if mode != "noob":
                choice = input(f"\n  {ui.YELLOW}[r] retry  [s] skip  [q] quit: {ui.RESET}").strip().lower()
                if choice == "r":
                    # Retry once
                    result2 = _run_step(step, params, mode, brand)
                    params.update(result2["params"])
                    if not result2["ok"]:
                        return False
                    completed += 1
                elif choice == "s":
                    continue
                else:
                    return False
            else:
                return False
        else:
            prev_output = result["output"]
            completed  += 1

        # Checkpoint save
        session.recipe_state[recipe["id"]] = {
            "step": i,
            "completed": completed,
            "params": params,
        }

    # Success banner
    print()
    print(f"{ui.GREEN}{ui.BOLD}{'═' * 46}{ui.RESET}")
    print(f"{ui.GREEN}{ui.BOLD}  ✅ Recipe complete: {title}{ui.RESET}")
    print(f"{ui.GREEN}  {completed}/{total} steps done{ui.RESET}")
    print(f"{ui.GREEN}{ui.BOLD}{'═' * 46}{ui.RESET}")
    print()

    return True


def _print_checkpoint_summary(completed: int, total: int, title: str):
    """Show what completed before the failure."""
    print()
    print(f"  {ui.YELLOW}Checkpoint: {completed}/{total} steps completed for '{title}'{ui.RESET}")
    if completed > 0:
        print(f"  {ui.GRAY}The completed steps don't need to be re-done.{ui.RESET}")
    print()

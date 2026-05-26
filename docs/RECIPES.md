# VERNUX Community Recipes

A **recipe** is a verified multi-step workflow that VERNUX walks you through
end-to-end. You say what you want, VERNUX handles every step — installing
prerequisites, collecting what it needs from you, running commands in order,
and telling you if something goes wrong.

---

## Built-In Recipes

| Trigger phrase                   | What it does                                  | Time  |
|----------------------------------|-----------------------------------------------|-------|
| `push project to github`         | Full wizard — git init, SSH key, remote, push | ~5min |
| `setup python dev environment`   | Python, pip, venv, project structure          | ~3min |
| `download youtube video`         | Install yt-dlp, ffmpeg, download to Downloads | ~5min |
| `make termux look good`          | zsh + Oh My Zsh + theme + aliases             | ~5min |
| `set up local web server`        | Python HTTP server accessible on your network | ~2min |
| `backup termux to sdcard`        | Full Termux backup → Downloads folder         | ~3min |
| `setup nodejs project`           | Node.js + npm init + Express + starter server | ~4min |
| `compress and share folder`      | zip + Android share sheet                     | ~2min |
| `fix termux storage access`      | Diagnose + fix all storage permission issues  | ~2min |
| `update everything`              | pkg upgrade + pip + npm global + cleanup      | ~5min |

---

## How Recipes Work

Recipes are **stateful** — they know what completed and what didn't.

- VERNUX checks prerequisites at each step and installs missing tools automatically
- Parameters are collected interactively only when needed (e.g. your GitHub username)
- Risky steps (git push, chmod) pause for confirmation
- If a step fails, VERNUX shows a checkpoint — what completed, what didn't
- Learner/Pro can retry or skip a failed step; Noob gets a clear error message

---

## Submit a Community Recipe

Community recipes are welcome via GitHub Pull Request.

### Recipe JSON Schema

```json
{
  "id": "your_recipe_id",
  "triggers": ["phrase that starts it", "alternative phrase"],
  "title": "Human-Readable Title",
  "description": "One sentence description",
  "estimated_minutes": 3,
  "requires_internet": true,
  "steps": [
    {
      "id": "step_id",
      "title": "Step Title",
      "command": "the bash command to run",
      "description_noob":    "Plain English — what this does",
      "description_learner": "Educational — flags explained",
      "description_pro":     "One-liner",
      "safety": "green",
      "long_task": false
    }
  ]
}
```

### Step Fields

| Field              | Required | Description |
|--------------------|----------|-------------|
| `id`               | ✅       | Unique snake_case identifier |
| `title`            | ✅       | Short display title |
| `command`          | ✅       | Bash command. Use `{param}` for user-supplied values |
| `description_noob` | ✅       | Plain English, no jargon |
| `safety`           | ✅       | `green` / `yellow` / `red` |
| `long_task`        | ❌       | Set `true` for downloads/installs — shows timing notice |
| `params_needed`    | ❌       | List of `{param}` placeholders to collect from user |
| `param_prompts`    | ❌       | `{"param": "Prompt text: "}` |
| `param_defaults`   | ❌       | `{"param": "default value"}` |
| `prereq_check`     | ❌       | Command name to check — auto-installs if missing |
| `prereq_install`   | ❌       | Install command if prereq not found |
| `pause_after`      | ❌       | Pause and wait for Enter after this step |
| `pause_message`    | ❌       | Message shown during pause |
| `optional`         | ❌       | User can skip this step |
| `optional_message` | ❌       | Message shown for optional steps |

### Submission Checklist

Before submitting a PR:

- [ ] Tested end-to-end on a real Android device
- [ ] All required Termux packages available via `pkg install`
- [ ] Recipe runs cleanly from fresh state (no assumed prior setup)
- [ ] Noted any device/brand-specific issues in your PR description
- [ ] All three description fields filled in (noob, learner, pro)
- [ ] Safety levels set correctly (yellow or red for anything that modifies/deletes)

---

## File Location

Community recipes go in `data/recipes.json` under the `recipes` array.
Built-in recipes ship with VERNUX. Community recipes can be added via
`vernux update` once the community pipeline is live in Phase 6.

---

*VERNUX Recipe system — Phase 3*

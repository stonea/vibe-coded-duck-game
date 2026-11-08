# Vibe Coded Duck Game

A terminal duck game written in a single Python file (`duckgame.py`), with no dependencies beyond the standard library. It draws with plain ANSI escape codes, so there is no curses.

## Requirements

- Python 3 on macOS or Linux (it uses `termios` and `tty`)
- A terminal at least **150 columns x 35 rows**. If the window is too small, the game pauses and tells you which way to resize it.
- Best results in a terminal that supports the Kitty keyboard protocol (key press and release events). Other terminals work through a fallback that guesses key releases.
- Sound effects use `afplay` and the macOS system sounds. They are skipped if those are missing.

## Running

```
python3 duckgame.py          # shows the title splash; offers to resume a saved game
python3 duckgame.py --new    # ignore any saved game
```

Environment variables:

- `DUCK_SAVE`: path of the save file (default `~/.duck_save.json`)
- `NO_COLOR`: turn colour off

## Levels

| Level | What it is | Goals to finish it |
|-------|------------|--------------------|
| 1 | A one-screen tutorial with no enemies and hints painted on the backdrop | Quack, pick up every `$`, lay an egg |
| 2 | A one-screen arena with eight beetles, a pea-shooter and pea packs | Pick up every `$`, defeat every beetle |
| 3 | A one-screen level with two sliding ledges: ride one to reach the pea-shooter, then shoot the beetle on the high one from a safe ledge | Pick up every `$`, defeat every enemy |
| 4 | A tall climbing level: bounce off mushrooms from ledge to ledge, with wind gusts near the top | Pick up every `$` (some hang in the air), reach the summit |
| 5 | The Flood Climb: a medium tower of ledges with water that rises at a moderate pace, then speeds up gently when the rain starts. Same drowning rules as level 7 | Pick up every `$`, reach the top ledge |
| 6 | The Final Climb, combining everything: a mirrored version of level 4's tower of stairs, mushrooms, sliding ledges and wind, with a pea-shooter, six beetles (one rides a sliding ledge) and rising water that speeds up when the rain starts. Beetles the water reaches drown. Same drowning rules as level 7 | Pick up every `$`, defeat every beetle, reach the top ledge |
| 7 | The Flood Tower: the water rises steadily, then faster once the rain starts, so climb a tall tower of ledges before it catches you. The duck turns blue under the water, and after three seconds under she drowns (a short sinking animation), and pressing space restarts the level (no lives or air meter here) | Pick up every `$`, reach the top ledge |
| 8 | The full game: a 2400-column world with lakes, caves, pearls, enemies and items | All 17 achievements (then a celebration and a golden duck) |

Finishing a level's goals starts the next level after a short banner. Each level starts fresh: inventory, health, lives, ammo and stamina all reset. Only your mute setting carries over (and your hat, but hats only work in level 8).

Level 1 hides most of the HUD (just the coin counter) and has no running, hunger or other meters. Levels 1 to 7 have no hunger, happiness, feeding or hats; those belong to level 8, the full game.

## Controls

| Key | Action |
|-----|--------|
| Left / Right | Walk (hold Shift to run, levels 2 to 5) |
| Space | Quack (hold for more quacks). Once you have the pea-shooter it shoots a pea instead. |
| Up | Jump; hold Up while falling to glide (needs the umbrella); swim up in water |
| Down | Sit (lay an egg if you wait); press again on a ledge to drop through; in a lake, float, then dive |
| `s` | Shoot a pea (same as Space once you have the pea-shooter; needs ammo) |
| `i` | Inventory |
| `a` | Achievements for the current level |
| `f` | Feed (scatter crumbs; level 8 only) |
| `h` | Change hat (level 8 only) |
| `w` | Change weather |
| `m` | Mute |
| `p` | Pause / resume (the game clock stops while paused) |
| `r` | Restart the current level (asks first) |
| `q`, `x` or Esc | Quit (asks first) |

## Game systems (levels 2 to 5)

- **Meters:** fullness and happiness (level 8 only), health (HP), run stamina and air. Three lives. Running out of air or health costs a life. Losing all lives is game over.
- **Items:** umbrella (glide), pea-shooter, oxygen tank (3x air). They are placed on random ledges, except the pea-shooter, which is always near the start.
- **Pea packs:** give ammo for the pea-shooter. Shown in the HUD as `Peas N`.
- **Mushrooms and wind (level 4):** a very tall climb. The first part is plain jumping up a staggered staircase of ledges; then landing on a bounce mushroom throws you up; hold Up as you land for a bigger bounce, and steer in the air. Gusts blow near the top; hold Down to sit and brace.
- **Enemies:** beetles patrol ledges and the ground. Bats (level 8) fly in a slow sine wave, so you can crouch under them. Enemies hurt on contact and are shot with peas.
- **Lakes:** at least three, with deep caves, air pockets and pearls (level 8).
- **Eggs and chicks:** sit down and wait to lay an egg. Eggs hatch into chicks that follow you and grow up. Predators (fox, hawk) come after them.
- **Saving:** the game autosaves every 20 seconds and on exit, and offers to resume next time. A finished game over deletes the save.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the code is organised.

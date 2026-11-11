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
| 2 | A short level (the screen scrolls sideways) with two small hills of stairs and a few mites. A quack (Space) stuns nearby mites for a few seconds, so stun them and slip past; there is no pea-shooter here | Pick up every `$`, stun a mite |
| 3 | A long level (the screen scrolls sideways) of stair hills patrolled by small mites. A quack stuns nearby mites for a few seconds, so stun your way right across the level to the pea-shooter on the far-right platform; once you have it, one pea kills a mite | Pick up every `$`, defeat every mite |
| 4 | Three hills of stairs side by side (the screen scrolls sideways). The first hill has mites: stun them, climb to the top, then jump up to the highest ledge for the pea-shooter. Hill 2 is a shooting lesson: two easy mites (one pea each) and just two beetles (three peas each) you can pick off from a distance. Hill 3 is full of beetles; it climbs and then comes back down. A secret hides above its top ledge | Pick up every `$`, defeat every mite and beetle |
| 5 | A one-screen level with two sliding ledges: ride one to reach the pea-shooter, then shoot the beetle on the high one from a safe ledge. A third sliding ledge carries you across a wide gap to a staircase of beetle-guarded ledges, so you have to ride two sliders to finish (the screen scrolls sideways) | Pick up every `$`, defeat every enemy |
| 6 | A tall climbing level: small mites patrol the stairs at the bottom (quack to stun them), a pea-shooter waits about a third of the way up, then beetles guard the mushroom ledges above it, and bounce off mushrooms from ledge to ledge, with wind gusts near the top | Pick up every `$` (some hang in the air), reach the summit (beating the enemies is optional) |
| 7 | The Flood Climb: a medium tower of ledges with water that rises at a moderate pace, then speeds up gently when the rain starts. Same drowning rules as level 10 | Pick up every `$`, reach the top ledge |
| 8 | The Final Climb, combining everything: a mirrored version of level 6's tower of stairs, mushrooms, sliding ledges and wind, with a pea-shooter, six beetles (one rides a sliding ledge) and rising water that speeds up when the rain starts. Beetles the water reaches drown. Same drowning rules as level 10 | Pick up every `$`, defeat every beetle, reach the top ledge |
| 9 | Bramble Hill: a zigzag of grassy ledges patrolled by hedgehogs, which walk uphill, curl into a spiky ball and roll back down (peas bounce off the ball, so wait for it to uncurl), and armadillos, which only a shot in the back can hurt (a pea that hits the front bounces back and hurts you, so sit down or jump over it), plus beetles and mites. A tall climb with two mushrooms and a sliding ledge | Pick up every `$`, defeat every enemy, reach the top ledge |
| 10 | The Flood Tower: the water rises steadily, then faster once the rain starts, so climb a tall tower of ledges before it catches you. The duck turns blue under the water, and after three seconds under she drowns (a short sinking animation), and pressing space restarts the level (no lives or air meter here) | Pick up every `$`, reach the top ledge |
| 11 | An ice rink: the duck slides instead of walking, with beetles, a hedgehog, an armadillo, a pea-shooter and a climb to the top | Pick up every `$`, defeat every enemy, reach the top ledge |
| 12 | A harder ice rink with more ledges and a mushroom | Pick up every `$`, defeat every beetle, reach the top ledge |
| 13 | The grand tour: a wide, tall world with an umbrella glide, wind and fourteen beetles | Pick up every `$`, defeat every beetle, reach the top of the tower |
| 14 | The full game: a 2400-column world with lakes, caves, pearls, enemies and items | All 17 achievements (then a celebration and a golden duck) |

Finishing a level's goals starts the next level after a short banner. Each level starts fresh: inventory, health, lives, ammo and stamina all reset. Only your mute setting carries over (and your hat, but hats only work in level 14).

Level 1 hides most of the HUD (just the coin counter) and has no running, hunger or other meters. Levels 1 to 13 have no hunger, happiness, feeding or hats; those belong to level 14, the full game.

## Controls

| Key | Action |
|-----|--------|
| Left / Right | Walk (hold Shift to run, levels 4 to 7) |
| Space | Quack (hold for more quacks). Once you have the pea-shooter it shoots a pea instead; otherwise it quacks (which stuns mites on level 3). |
| Up | Jump; hold Up while falling to glide (needs the umbrella); swim up in water |
| Down | Sit (lay an egg if you wait); press again on a ledge to drop through; in a lake, float, then dive |
| `s` | Shoot a pea (same as Space once you have the pea-shooter; needs ammo) |
| `i` | Inventory |
| `a` | Achievements for the current level |
| `f` | Feed (scatter crumbs; level 14 only) |
| `h` | Change hat (level 14 only) |
| `w` | Change weather |
| `m` | Mute |
| `p` | Pause / resume (the game clock stops while paused) |
| `r` | Restart the current level (asks first) |
| `q`, `x` or Esc | Quit (asks first) |

## Game systems

- **Meters:** fullness and happiness (level 14 only), health (HP), run stamina and air. Three lives. Running out of air or health costs a life. Losing all lives is game over.
- **Items:** umbrella (glide), pea-shooter, oxygen tank (3x air). They are placed on random ledges, except the pea-shooter, which is always near the start.
- **Pea packs:** give ammo for the pea-shooter. Shown in the HUD as `Peas N`.
- **Mushrooms and wind (level 6):** a very tall climb. The first part is plain jumping up a staggered staircase of ledges; then landing on a bounce mushroom throws you up; hold Up as you land for a bigger bounce, and steer in the air. Gusts blow near the top; hold Down to sit and brace.
- **Enemies:** mites (levels 2 to 4 and 6) are stunned by quacks and die to one pea. Beetles patrol ledges and the ground. Hedgehogs (level 9) curl into balls that peas bounce off, and armadillos (level 9) only take damage from behind: a pea that bounces off their armor comes back and hurts the duck. Bats (level 14) fly in a slow sine wave, so you can crouch under them. Enemies hurt on contact and are shot with peas.
- **Lakes:** at least three, with deep caves, air pockets and pearls (level 14).
- **Eggs and chicks:** sit down and wait to lay an egg. Eggs hatch into chicks that follow you and grow up. Predators (fox, hawk) come after them.
- **Saving:** the game autosaves every 20 seconds and on exit, and offers to resume next time. A finished game over deletes the save.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the code is organised.

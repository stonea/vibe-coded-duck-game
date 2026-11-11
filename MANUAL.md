---
title: "VIBE CODED DUCK GAME"
subtitle: "Instruction Booklet"
geometry: "a5paper,margin=18mm"
fontsize: 10pt
toc: true
toc-depth: 1
colorlinks: true
header-includes: |
  ```{=latex}
  \usepackage{xcolor}
  \definecolor{nred}{HTML}{E60012}
  \usepackage{titlesec}
  \titleformat{\section}{\color{nred}\Large\bfseries}{}{0em}{}[\color{nred}\titlerule]
  \usepackage{float}
  \floatplacement{figure}{H}
  \usepackage{fancyhdr}
  \pagestyle{fancy}
  \fancyhf{}
  \fancyfoot[C]{\color{nred}Vibe Coded Duck Game \quad\thepage}
  \renewcommand{\headrulewidth}{0pt}
  ```
---

\newpage

![The title screen](manual_images/title.png){width=100%}

\newpage

# Important Information

> **Please read before playing.** Take a 10 minute break every hour, play in a well-lit room, and stop if your hands or wrists feel sore. No ducks were harmed. Pixel ducks may be dropped into ponds.

## What You Need

- Python 3 on macOS or Linux (standard library only; nothing to install).
- A terminal at least **150 columns x 35 rows**. If it is too small, the game pauses and tells you which way to resize.
- Best: a terminal that supports the Kitty keyboard protocol (key press and release). Others work with a fallback that guesses key releases.
- Sound effects use `afplay` and the macOS system sounds; they are skipped if missing.

## Starting the Game

```
python3 duckgame.py          # title splash; offers to resume
python3 duckgame.py --new    # ignore any saved game
```

On a saved game press **R** to resume, **N** to start over, **Q** to quit.

| Variable    | Effect                                      |
|-------------|---------------------------------------------|
| `DUCK_SAVE` | Save file path (default `~/.duck_save.json`) |
| `NO_COLOR`  | Turns colour off                            |

# Meet the Duck

A cosy little duck lives in a world of ponds, hills, caves and sky ledges. She can walk, jump, glide, swim, dive and quack. She can lay eggs and raise chicks, and with luck she might even become a golden duck!

## Objective

Each level has its own goals; press **A** to see them. Finish them all and the next level begins after a short banner. Typical goals:

- Pick up every `$` coin.
- Defeat every enemy (when there are enemies).
- Reach the top ledge or summit.
- Lay an egg, or stun a mite (early levels).

> **Note:** each level starts fresh. Inventory, health, lives, ammo and stamina reset. Only your mute setting carries over (and your hat, which only works in level 13).

Levels 1 to 12 teach the basics. Level 13 is the full game: a 2400-column world with lakes, caves, pearls, hunger, happiness, hats and chicks. Earn all 17 achievements to see a celebration and a golden duck.

# Controls

![Hold Space to quack. The duck is in level 1, the tutorial.](manual_images/quack.png){width=100%}

| Key           | Action                                                              |
|---------------|---------------------------------------------------------------------|
| Left / Right  | Walk. Hold Shift to run (levels 4--7 and 13).                       |
| Space         | Quack (hold for more). With the pea-shooter it shoots a pea instead. |
| Up            | Jump. Hold while falling to glide (umbrella). Swim up in water.     |
| Down          | Sit (wait to lay an egg). Press again on a ledge to drop through. In a lake: float, then dive. |
| S             | Shoot a pea (needs the pea-shooter and ammo)                        |
| I             | Inventory                                                           |
| A             | Achievements for this level                                         |
| F             | Feed: scatter crumbs (level 13)                                     |
| H             | Change hat (level 13)                                               |
| W             | Change weather                                                      |
| M             | Mute                                                                |
| P             | Pause / resume                                                      |
| R             | Restart level (asks first)                                          |
| Q, X or Esc   | Quit (asks first)                                                   |

# The Game Screen

![Level 13. The status line at the top shows every meter.](manual_images/l13.png){width=100%}

| Meter          | Meaning                                                     |
|----------------|-------------------------------------------------------------|
| HP             | Drops when enemies touch you. At zero you lose a life.      |
| Lives          | Three lives. Lose them all and it is game over.             |
| Full / Happy   | Hunger and mood (level 13 only).                            |
| Stamina / Glide| Fuels running (level 13) or the umbrella glide.             |
| Air            | Breath underwater. Running out costs a life.                |
| Peas N         | Pea-shooter ammunition.                                     |
| `$ n/N`        | Coins collected out of total.                               |


![Press A to see the level's goals.](manual_images/ach.png){width=100%}

Level 1 shows only the coin counter. Levels 2 to 4 show health only; when you faint, a popup appears and Space restarts the level.

# Items and Hazards

![Press I to open the inventory (level 13).](manual_images/inv.png){width=100%}

| Item          | What it does                                                         |
|---------------|----------------------------------------------------------------------|
| Coin `$`      | Walk into it. Many levels need them all.                             |
| Pea-shooter   | Space (or S) fires peas. Always found near the start.                |
| Pea pack      | Refills ammo.                                                        |
| Umbrella      | Hold Up while falling to glide.                                      |
| Oxygen tank   | Triples your air underwater (level 13).                              |
| Mushroom      | Bounce pad. Hold Up as you land for a bigger bounce.                 |
| Sliding ledge | A moving ledge. Hop on to cross gaps.                                |


![With the pea-shooter, Space fires peas (level 4).](manual_images/shoot.png){width=100%}

**Wind.** Near the top of tall levels, gusts blow you sideways. Hold Down to sit and brace.


![Flood Tower (level 9): climb ahead of the water.](manual_images/flood.png){width=100%}

**Rising water.** On flood levels (7 to 9) the water climbs, faster once rain starts. The duck turns blue underwater and drowns after three seconds. Press Space to restart.

# Friends and Foes

| Enemy       | Where        | How to beat                                           |
|-------------|--------------|-------------------------------------------------------|
| Mite        | Levels 2--4, 6 | A quack stuns it. One pea defeats it.               |
| Beetle      | Levels 4--13 | Patrols ledges and ground. Three peas.                |
| Bat         | Level 13     | Flies in a slow wave. Crouch under it.                |
| Fox / Hawk  | Level 13     | Hunt eggs and chicks. Quack to scare them away.       |

**Eggs and chicks.** Press Down to sit and wait; she will lay an egg. Eggs hatch into chicks that follow you and grow up. Keep them safe, and have 3 chicks at once for *Full Nest*.


![A lake in level 13: float on the surface, then dive.](manual_images/l13b.png){width=100%}

**Lakes (level 13).** Float on the surface, then press Down to dive. Watch your air; air pockets in caves let you breathe.

# The Levels

![Level 3: stun the mites, then find the pea-shooter.](manual_images/l3.png){width=100%}

| Lv | Name | What it is | Goal |
|----|------|------------|------|
| 1 | Tutorial | One screen, no enemies, hints on the backdrop. | Quack, every `$`, lay an egg |
| 2 | Stunning | Two small hills and a few mites. Quack to stun; no pea-shooter. | Every `$`, stun a mite |
| 3 | Mites | Long stair hills; stun your way to the pea-shooter on the far right. | Every `$`, defeat every mite |
| 4 | Three Hills | Hill 1 mites and the pea-shooter; hill 2 a shooting lesson; hill 3 full of beetles. A secret hides above. | Every `$`, defeat all enemies |
| 5 | Moving Ledges | Ride sliding ledges to the pea-shooter and across a wide gap. | Every `$`, defeat all enemies |
| 6 | Mushrooms | Tall climb: mites, pea-shooter, beetles, mushrooms, wind at the top. | Every `$`, reach the summit |
| 7 | Medium Flood | Climb ahead of rising water. | Every `$`, reach the top |
| 8 | Final Climb | Level 6 mirrored, with sliders, six beetles, wind and water. | Every `$`, defeat beetles, reach the top |
| 9 | Flood Tower | A tall tower; water rises, then speeds up in rain. | Every `$`, reach the top |
| 10 | Ice Rink | She slides instead of walking. Beetles and a pea-shooter. | Every `$`, defeat beetles, reach the top |
| 11 | Hard Ice Rink | More ledges, a slider and a mushroom. | Every `$`, defeat beetles, reach the top |
| 12 | Grand Tour | Wide, tall: ice, mushrooms, a chasm, umbrella glide, 14 beetles. | Every `$`, defeat beetles, reach the tower top |
| 13 | Full Game | 2400-column world of lakes, caves, pearls and items. | All 17 achievements |


![Level 6: mushrooms, mites and beetles on a tall climb.](manual_images/l6.png){width=100%}

![Level 10: the ice rink.](manual_images/l10.png){width=100%}

# Achievements

| Achievement      | How to earn it                       |
|------------------|--------------------------------------|
| Lay an egg       | Sit down and wait                    |
| Quack Chorus     | Hold space for 7 quacks              |
| Hatchling        | An egg hatches into a chick          |
| Proud Mama       | A chick grows into a duck            |
| Full Nest        | Have 3 chicks at once                |
| Snack Time       | Eat some crumbs (F)                  |
| Fashionista      | Try every hat (H)                    |
| Skydiver         | Drop through a ledge                 |
| King of the Hill | Reach the top ledge                  |
| Swimmer          | Dive in a pond                       |
| Nature Lover     | Meet a butterfly, frog and fish      |
| Night Owl        | Let her fall asleep                  |
| Weatherduck      | See rain and snow (W)                |
| Chick Rescue     | Find a lost chick                    |
| Coin Collector   | Collect 10 coins                     |
| Scarecrow        | Quack a predator away                |
| Happy Duck       | Get happiness above 90               |

# Saving, Pausing and Quitting

- **Saving:** autosaves every 20 seconds and on exit; offers to resume next time. A finished game over deletes the save.
- **Pause:** press **P**. The game clock stops, including the rising water.
- **Restart:** press **R** (asks first).
- **Game over:** lose all three lives, then **Y** or Enter to start over from level 1, or **Q** to quit.
- **Quit:** **Q**, **X** or Esc (asks first, then saves).

# Hints and Tips

- Read the hints painted on level 1's backdrop.
- On levels 2 and 3, quack to stun mites and walk past them.
- Shoot beetles from a distance; keep your pea packs.
- Hold Up as you land on a mushroom for a big bounce.
- On flood levels, keep climbing and grab coins on the way.
- Press Down on a ledge to drop through it.
- On ice, plan your stops; you slide farther than you think.
- Lay eggs early in level 13 so chicks have time to grow.
- Stuck? Press A to see which goals remain.

# Troubleshooting

| Problem | Fix |
|---------|-----|
| Window too small | Enlarge to at least 150 x 35; the game resumes. |
| Keys feel sticky | Use a Kitty-protocol terminal (kitty, WezTerm, Ghostty). |
| No colour | Unset `NO_COLOR`. |
| No sound | Needs macOS `afplay`; skipped elsewhere. |
| Fresh game | `python3 duckgame.py --new` or delete `~/.duck_save.json`. |
| Terminal looks odd | Type `reset` and press Enter. |

**Thank you for playing!**

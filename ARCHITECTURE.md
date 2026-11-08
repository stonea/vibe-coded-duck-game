# Architecture

Everything lives in one file, `duckgame.py` (about 2,500 lines, standard library only). This document describes how the code is organised and, in the feature reference below, what every feature does and where it is implemented. Tunable numbers are module-level constants near the top of the file, so a name in `CAPS` in this document can be found with a search.

Contents

1. [File layout](#file-layout)
2. [Runtime flow](#runtime-flow)
3. [Levels](#levels)
4. [Feature reference](#feature-reference)
5. [World class and update order](#world-class-and-update-order)
6. [Rendering](#rendering)
7. [Input](#input)
8. [Terminal handling and the size gate](#terminal-handling-and-the-size-gate)
9. [Saving](#saving)
10. [Sound](#sound)
11. [Testing and extending](#testing-and-extending)

## File layout

Top to bottom:

| Region | Contents |
|--------|----------|
| Constants | Layout (`STEP`, `GROUND`, `WORLD_H`, `LAKE_DEPTH`), terminal minimums (`MIN_COLS` 150, `MIN_ROWS` 35), colours (`C_*`, `USE_COLOR`), timings, sprites, rates and damage values, grouped by feature |
| Achievements and level tables | `ACHIEVEMENTS`, `LEVEL1_ACHIEVEMENTS`, `LEVEL3_ACHIEVEMENTS`, `LEVEL_ACHIEVEMENTS`, `LAST_LEVEL`, `LEVEL_INTROS`, ledge, coin, beetle, mover and hint tables for levels 1 to 3, and `FLOODS` (levels 5 and 6) |
| Input tables | `PLAIN_KEYS`, `KITTY_KEYS`, `ARROW_NAMES`, `HOLD_KEYS` and the regexes for parsing escape sequences |
| Helpers | `clamp`, `sprite` (mirror art), `quack_pos`, `new_sparkles`, `quack_count`, `duck_lines`, `new_chick`, `new_adult` |
| Map builders | `is_water`, `build_caves`, `cave_cell`, `build_platforms`, `place_packs`, `place_items`, `support`, `build_scenery`, `configure_level` |
| `World` | All game state, input handling, simulation (`update_*`), status line, mini-map and `frame()` |
| Terminal layer | `bar`, `to_ansi`, `Input`, help bar, `draw_status`, `draw`, `supports_key_release` |
| `Sound` | Background `afplay` playback |
| Saving | `read_save`, `write_save` |
| Startup screens | `TITLE_ART`, `splash_scene`, `term_size`, `too_small`, `wait_for_size`, `paint_title`, `splash`, `ask_resume` |
| `main()` | Terminal setup, startup flow, game loop, cleanup |

## Runtime flow

```
main()
 ├─ alternate screen, hide cursor, tty.setcbreak
 ├─ splash(fd)                  animated title; pauses if the window is too small
 ├─ read_save() / ask_resume()  r: resume, n: start over, q: quit (skipped by --new)
 ├─ supports_key_release()      ask the terminal for Kitty key events
 ├─ World(now, level)           (+ load_state when resuming)
 └─ loop:
     ├─ size gate: too small -> wait_for_size(); size changed -> set_view + redraw help bar
     ├─ select() on stdin, 10 ms timeout
     ├─ Input.poll() -> (name, pressed) events -> World.handle / request_quit
     ├─ World.update(now)
     ├─ level finished? -> World(now, level + 1, hat, muted)
     ├─ autosave every SAVE_EVERY seconds
     ├─ World.pop_events() -> Sound (quack, coin, fanfare)
     └─ draw_status() and draw(frame) only when they changed
```

Notes:

- The loop is single threaded and driven by `time.monotonic()`. Every timed thing (animations, enemies, growth, weather) stores a due time and checks `now >= due` each tick.
- `finally` restores the terminal and then either deletes the save (game over) or writes it (normal exit).
- At game over the keys are `y` / Enter (start over at level 1 with a fresh `World`) or `q` (quit).
- Changing level builds a new `World`. Only the hat (which is dropped unless the new level is the full game) and the mute setting are passed on, so inventory, health, lives, ammo, eggs and chicks all reset.

## Levels

There are eleven levels. `World.level` selects behaviour and `configure_level(level)` selects the map. The map data are module globals that `configure_level` rebinds: `WORLD_W`, `PONDS`, `PLATFORMS`, `START_LEDGES`, `PLATFORMS_BY_X`, `TREES`, `FLOWERS`, `COINS`, `LEDGE_LEVEL`, `CAVE`, `PEARL_SPOTS`, `LEVEL_ITEMS`, `PACK_TOTAL`, `EASY_SPOTS`, `MOVERS`, `MUSHROOMS`. `World.__init__` calls it first, and the module calls `configure_level(LAST_LEVEL)` at import so the globals always exist. Only one level is active at a time.

| | Level 1 (tutorial) | Level 2 (arena) | Level 3 (moving ledge) | Level 4 (mushrooms) | Level 5 (medium flood) | Level 6 (final climb) | Level 7 (flood tower) | Level 8 (ice rink) | Level 9 (hard ice rink) | Level 10 (grand tour) | Level 11 (full game) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Width | 149 columns (`SCREEN_W`) | 149 columns | 149 columns | 149 columns | 149 columns | 149 columns | 149 columns | 149 columns | 149 columns | 392 columns (`GRAND_W`) | 2400 columns |
| Camera | Fixed single screen | Fixed single screen | Fixed single screen | Dead-zone vertical scroll (about 40 rows tall) | Dead-zone vertical scroll (about 105 rows tall) | Dead-zone vertical scroll (about 115 rows tall) | Dead-zone vertical scroll (about 135 rows tall) | Dead-zone vertical scroll (about 50 rows tall) | Dead-zone vertical scroll (about 55 rows tall) | Follows the duck both ways (about 160 rows tall) | Follows the duck both ways |
| Ledges | 5 (`LEVEL1_LEDGES`): a 4-ledge staircase to the top coin, plus one low ledge | 12, two arches (`LEVEL2_LEDGES`) | 2 static (`LEVEL3_LEDGES`) plus two sliding ledges (`LEVEL3_MOVERS`) | Stairs and mushroom ledges (`LEVEL4_LEDGES`, absolute floor rows); stairs 6 and 9 are replaced by two sliding ledges (`LEVEL4_MOVERS`) | 26 staggered ledges 4 rows apart (`build_flood_ledges`, seeded) | Level 4's layout mirrored left to right (`LEVEL6_LEDGES`): 10 stairs and 10 mushroom ledges, stairs 6 and 9 replaced by two sliding ledges (`LEVEL6_MOVERS`), mushrooms in `LEVEL6_MUSHROOMS` | 33 staggered ledges 4 rows apart (`build_flood_ledges`, seeded) | 15 zigzag ledges 3 rows apart (`ICE_X`, `ICE_LEDGES`): 14 to 25 columns wide, that overlap their neighbours by 2 to 4 columns | 14 ledges 3 rows apart then 9, 12... rows (`ICE2_X`, `ICE2_LEDGES`): narrower ledges that still overlap by 2 to 4 columns, a sliding ledge (`ICE2_MOVERS`) for the wide gap before ledge 6, and a mushroom (`ICE2_MUSHROOMS`) on ledge 9 that throws her to the 10th, 9 rows up | 29 (`GRAND`): an icy rink of 5 ledges, a sliding ledge (`GRAND_MOVERS`), 3 mushroom ledges up to a long launch ledge, a 60 column chasm, then a far ledge and level 6's 18-ledge mushroom tower shifted right (`GRAND_TOWER_DX`) | 369 generated by `build_platforms()` (seeded) |
| Lakes and caves | None | None | None | None | None (the flood is the water) | None (the flood is the water) | None (the flood is the water) | None | None | None | 3 lakes (`PONDS` at 150, 1000, 1800), caves from `build_caves()` |
| Coins | 9: one per ledge plus `LEVEL1_COINS` | 17: one per ledge plus 5 on the ground | 6: one per static ledge plus 4 on the ground (`LEVEL3_COINS`) | 9: one per ledge plus 5 mostly hanging in the air (`LEVEL4_COINS`) | 38: one per ledge plus two at the ends of each wide ledge | 28: one per ledge plus one hanging above each mushroom | 49: one per ledge plus two at the ends of each wide ledge | 23: one per ledge plus 4 on the rink floor and 4 over gaps (`ICE_COINS`) | 20: one per ledge, 4 on the rink floor, one over the mushroom and one over the sliding ledge | 61: one per ledge, 8 on the ground (two in the chasm), one above the sliding ledge, one over each mushroom and three along the glide | 369, one per ledge |
| Enemies | None | 8 beetles (`LEVEL2_BEETLES`), no respawn | 1 beetle riding the high sliding ledge | None | None | 6 beetles (`level6_beetles()` plus one riding the second sliding ledge), no respawn; the flood drowns any it reaches | None | 4 beetles (`ICE_BEETLES`: the rink floor and ledges 2, 4 and 6), no respawn | 5 beetles (`ICE2_BEETLES`: the rink floor and ledges 2, 4, 7 and 11), no respawn | 14 beetles (`GRAND_BEETLES`), no respawn | 22 beetles that respawn, bats |
| Predators and friends | Friends only | Friends and predators | Friends and predators | Friends and predators | Friends and predators | Friends and predators | Friends and predators | Friends and predators | Friends and predators | Friends and predators | Friends and predators |
| Items | None | Pea-shooter, 7 pea packs | Pea-shooter, 3 pea packs | None | None | Pea-shooter on the first ledge, 6 pea packs | None | Pea-shooter on the first ledge, 6 pea packs | Pea-shooter on the first ledge, 6 pea packs | Pea-shooter on the first ledge, hidden umbrella on a secret sky ledge chain, 8 pea packs | Umbrella, pea-shooter, oxygen tank, 14 pea packs |
| Meters (hunger, mood, stamina, air, health, lives) | Off; only `$ n/9` is shown | Health only (no lives, hunger or mood); dying shows a popup and space restarts the level | Health and lives | Same as level 3 | Health and the water gap (no lives) | Same as level 5 | Same as level 5 | Health only (no lives, hunger or mood); dying shows a popup and space restarts the level | Same as level 8 | Health and lives, plus a `Glide` bar (stamina; no running) | All, with hunger and mood, stamina and air |
| Feed (`f`) and hats (`h`) | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Enabled |
| Running (Shift) | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled | Disabled (she slides instead) | Disabled (she slides instead) | Disabled (the umbrella glide is enabled) | Enabled |
| Goal | Quack, all coins, lay an egg | All coins, defeat every beetle | All coins, defeat every enemy | All coins, reach the summit | All coins, reach the top ledge | All coins, defeat every beetle, reach the top ledge | All coins, reach the top ledge | All coins, defeat every beetle, reach the top ledge | All coins, defeat every beetle, reach the top ledge | All coins, defeat every beetle, reach the top of the tower | All 17 achievements |

### Level progression

- Each level has an achievement list (`LEVEL_ACHIEVEMENTS[level]`). `unlock(key)` ignores keys that are not in the current list, so shared code can call `unlock("egg")` or `unlock("coins")` without checking the level.
- `update_level_goals()` unlocks the goals that come from state: `allcoins` (levels 1 to 10, when no coins remain), `summit` (level 4, when she stands at or above `SUMMIT`; levels 5 to 7, at or above the flood config's `summit`; levels 8, 9 and 10, at or above the `summit` of their `ICE_CONFIGS` entry) and `slayer` (`SLAYER_LEVELS`: levels 2, 3, 6, 8, 9 and 10, when `kills` reaches `enemy_total`, the number of starting enemies). The quack goal is unlocked in `handle("space")`, and `egg` where the egg lands.
- When all goals of a level below `LAST_LEVEL` are unlocked, `level_done` is set, the fanfare plays and a "LEVEL N COMPLETE" banner is shown. After `LEVEL_DONE_DELAY` (3 s), `main()` creates the next `World`.
- On the last level, unlocking everything starts a celebration (`CELEBRATE_TIME` 12 s: fireworks, confetti, screen shake, rainbow duck, crown, banner) and permanently turns the duck golden (`golden`).
- Levels 1 to 4 show grey hints (`HINTS_BY_LEVEL`) painted on the backdrop at the lowest drawing priority.
- Level 11 map generation is deterministic, because the generators use fixed `random.Random` seeds (321 for ledges, 11 for scenery, 500+i for each lake's caves). Saves therefore only need to store what changed.

## Feature reference

### Movement and physics

- **Walk and run.** Left and Right move one column per `WALK_INTERVAL`. Running is only enabled in level 11 (`LAST_LEVEL`). Shift multiplies the interval by `RUN_FACTOR` (several columns per tick, capped at 8 per update) when stamina allows (`run_active`). Hunger below `SLOW_BELOW` slows walking. Underwater strokes are `SWIM_SLOWDOWN` times slower.
- **Jump.** Up starts a "rise" of `JUMP_ROWS` rows with per-row delays `RISE_DELAYS`, then a short hang (`HANG_DELAY`) and a "fall" with delays `FALL_DELAYS`. A jump is slightly taller than `STEP`, so one jump reaches the next ledge level. Ledges are one-way: the duck passes up through them and lands on top.
- **Falling off ledges.** `update_air` starts a fall when the duck walks onto a column with no support. `support(x, row)` returns the first floor at or below a row, using `PLATFORMS_BY_X` buckets of `BUCKET` (40) columns.
- **Drop through.** Press Down while sitting on a ledge: the duck moves one row down and falls (unlocks `skydiver`).
- **Glide.** With the umbrella, holding Up while falling slows the fall to `GLIDE_DELAY` per row and drains stamina (`GLIDE_DRAIN`).
- **Sit.** Down sits (crouch sprite, smaller hitbox). Up stands. Sitting for `SIT_AFTER` (5 s) rolls once for an egg.
- **King of the Hill.** Landing on the highest ledge level (`GROUND - STEP * MAX_LEVEL`) unlocks `king`.

### Quacking

- Hold Space. `quack_count(held)` gives 1 to `MAX_QUACKS` (7) quacks, one more every `QUACK_INTERVAL` (0.5 s), wrapping after the last.
- Each new quack draws a word (`QUACK_WORDS`) and sparkles on a sine path (`quack_pos`, `new_sparkles`), plays a sound event, raises happiness by `QUACK_HAPPINESS` and may make chicks peep.
- The 7th quack unlocks `chorus`. Any quack in level 1 unlocks `quack`.
- A quack within `SCARE_DIST` of a hunting predator scares it off (`scare`).

### Needs and meters (levels 2 to 7)

Hunger, mood and hats only exist in the full game (level 11). `World.survival` (`level == LAST_LEVEL`) gates them: in levels 1 to 10 fullness stays at 100 (so health and stamina regenerate normally), happiness is fixed (`cheer()` returns early and `update_needs` skips the hunger and mood update), the `f` and `h` keys do nothing, `hat` is always `None` (also when loading a save), the "hungry?" and "so hungry..." thoughts never appear, and the status bar omits the Fed and Happy meters. `draw_help` shows `HELP_LEVELS_2_TO_6` there, without the `f` and `h` hints.

`update_needs` and `update_stamina` run these. In level 1 they return early.

| Meter | Behaviour |
|-------|-----------|
| Fullness (`Fed`) | Starts at 80, falls `HUNGER_RATE` per second (half when asleep). Each crumb gives `FOOD_VALUE`. The duck thinks "so hungry..." below `HUNGRY_BELOW`. |
| Happiness (`Happy`) | Drifts toward a mood target made from fullness plus a bonus for chicks and adults. Coins, quacks and pearls give small boosts. At 90 or more it unlocks `happy`. It also raises the chance of an egg. |
| Health (`HP`, `MAX_HEALTH` 50, half the original 100; the bar is scaled to it) | Enemy contact costs `BEETLE_DAMAGE` or `BAT_DAMAGE`. It regenerates slowly while fullness is above `HUNGRY_BELOW`. |
| Stamina (`Run` bar, level 11 only: running and the umbrella exist only there) | Running (`RUN_DRAIN`) and gliding (`GLIDE_DRAIN`) use it. It regenerates (half speed when hungry). At zero the duck is `tired` until it recovers to `TIRED_UNTIL`. Crumbs give `STAMINA_PER_CRUMB`. |
| Air (`Air` / `Tank`) | Shown only where there are lakes (`PONDS`, level 11). See swimming. The tank multiplies the maximum by `TANK_AIR_FACTOR` (3). |
| Lives | `MAX_LIVES` (3), shown as hearts. |

The status bar shows level, coins, the five meters, lives, pearls and peas. The second status row is the mini-map.

### Lives and game over

`lose_life(reason)` removes a life and queues a toast. In level 2 there are no lives: `lose_life` sets `died` instead, which freezes `update`, makes `handle` ignore everything but space and shows a "THE DUCK DIED" popup; space sets `restart_now`. Elsewhere, health reaching 0 ("Knocked out!") restores health and gives 3 seconds of invulnerability. Running out of air ("Out of air!") washes the duck up on the nearest lake's surface and costs `BLACKOUT_PENALTY` happiness. At 0 lives `game_over` is set, an overlay offers `y` / `q`, and the save is deleted on exit.

### Crumbs and feeding

`f` drops `CRUMBS_PER_FEED` crumbs a short distance ahead. They fall until they land on a floor. The duck walks to the nearest landed crumb on its floor by itself when it is idle, and eating gives fullness, stamina and the `snack` achievement. Chicks and adults also eat crumbs; each crumb ages a chick by `GROWTH_PER_CRUMB` seconds.

### Hats

`h` cycles `HAT_ORDER`: none, top hat, party hat, crown, shades. Shades are drawn into the face (`duck_lines(..., shades=True)`). Trying each hat unlocks `fashion`. The crown is forced on during the celebration.

### Idle life

- **Idle behaviours** (`IDLE_BEHAVIORS`): blink, look behind, preen, started when the duck is free (not moving, sitting, quacking or asleep).
- **Thoughts:** random bubbles from `THOUGHTS` every few seconds (`THOUGHT_GAP`). In level 1 "hungry?" is excluded.
- **Sleep:** after `SLEEP_AFTER` (20 s) without input the duck falls asleep: eyes closed, "zZ", a moon and stars appear, hunger slows, and `owl` unlocks.
- **"nom"** is shown briefly after eating.

### Eggs, chicks and ducklings

- **Laying:** after sitting `SIT_AFTER` seconds, the chance is `EGG_BASE_CHANCE + 0.6 * happiness / 100` and needs fullness above 0. The egg flies along `EGG_ARC`, lands on the floor below (it rolls off a ledge edge) and unlocks `egg`. The `t` key forces an egg (test shortcut).
- **Eggs:** after `HATCH_AFTER` (10 s) an egg either melts or hatches (50/50, `MELT_FRAMES`, `HATCH_FRAMES`). A hatch creates a chick and unlocks `hatchling`. Three chicks at once unlock `nest`.
- **Growth:** a chick becomes a duckling at `GROW_TO_DUCKLING` seconds of age and an adult at `GROW_TO_DUCK`. The first unlocks nothing; the adult unlocks `mama`.
- **Chick AI** (`update_young`): each chick is in mode `follow`, `wander` or `lost`.
  - Followers trail mama in a line spaced by `CHICK_GAP`, hop up ledges when mama is on a higher floor and close (`CLIMB_RANGE`), and chase nearby butterflies.
  - "Adventurous" chicks sometimes wander off (`WANDER_RANGE`). If they end far away (`LOST_DIST`) they become lost and peep until mama comes within `FOUND_DIST`, which unlocks `rescue`.
  - Chicks run to crumbs, peep when mama quacks and say "eep!" when a predator is near.
- **Adults** (`update_adults`) wander near where they grew up, eat crumbs and do not follow.

### Friends

Up to `MAX_FRIENDS` visitors appear every `FRIEND_EVERY` seconds and stay 15 to 30 seconds: a butterfly (flutters, chicks chase it), a frog (hops, croaks "ribbit") and a fish (leaps from a lake, level 11 only because it needs a visible pond). Meeting all three unlocks `nature`. `g` summons one (test shortcut).

### Predators

Every `PREDATOR_EVERY` seconds, if there is an egg or chick, a fox or a hawk may arrive from the edge of the screen. It is never spawned in level 1 (`next_predator` is infinite).

- A **fox** walks along the ground and can only take prey on the ground floor.
- A **hawk** flies at the top of the screen, lines up above its target and dives. It can take anything.
- A caught chick or egg is removed with a notice. Quacking within `SCARE_DIST`, or hitting the predator with a pea, makes it flee and unlocks `scare`.
- `P` (Shift+p) summons one (test shortcut).

### Weather and sky

`w` (or a random timer, `WEATHER_EVERY`) cycles `WEATHERS`: clear, clouds, rain, snow. Rain and snow are screen-space particles that stop at the ground line. Seeing rain and snow unlocks `weather`. The moon and stars appear when the duck sleeps.

### Coins and pearls

- **Coins** (`$`) hover over every ledge (and on the ground in levels 1 to 4). Collecting one gives `COIN_HAPPINESS` and a sound. In level 11 the 10th coin unlocks `coins` (`COINS_FOR_ACHIEVEMENT`).
- **Pearls** (`o`, level 11) sit at the bottom of each lake and in cave chambers. They give `PEARL_HAPPINESS`, count in the HUD and respawn after `PEARL_RESPAWN`.

- **Pink gems** (`GEM`, shown in the HUD and the inventory overlay) are the secret of level 1. Sitting for `PATCH_SIT_TIME` on the springy grass patch (`update_chamber`) makes her fall through the grass into a cavern carved out of the rock under level 1's ground (`CH_X0`..`CH_X1`, rows `CH_TOP`..`CH_FLOOR`): the camera simply scrolls down after her. Below the grass `support()` treats only the cavern's ledges as floors (`CH_LEDGES`, added with `add_platform` only on level 1); on the surface it behaves as before. `max_cam_y()` allows scrolling below the ground while `feet > GROUND`, and `draw_cavern` draws the rock and the carved room only once the camera has scrolled down. Her x is clamped to the cavern walls while she is below the grass. Pressing Down again on a ledge drops her through it only if there is a floor below (`support(..., feet + 1) < WORLD_H`), so the cavern floor can't be fallen through. A stair of ledges on the left (clear of the patch, so the fall never lands on it) leads back up through the ceiling to the surface; stepped ledges on the right climb to the gem at `CH_GEM`. The gem is taken once per level (`gem_taken`). `World.gems` carries from level to level (the `gems` argument of `World`; the test menu keeps it, restarting a level resets it to `gems_at_start` so a restart can't farm gems, a new game after game over starts at 0). They are saved as `gems`, `gems_start` and `gem_taken`, and saving while below the grass stores the position on the patch.

- **Level 2's pink gem** is at the top of a zigzag of invisible ledges (`HIDDEN2`, added with `add_platform` only on level 2, so they are real floors from the start). The first one sits just above and to the left of the second arch's peak (jump up from the left edge of the top ledge). As a subtle hint, until the first one is found the left end of the ledge to jump from (`HINT_LEDGE2`) glows faintly (two neighbouring `=`, which move back and forth within the left 4 columns of the ledge, never further, every second or so, turn dim pink) while her feet (her centre column) are on one of those left 4 columns. Each appears when she lands on it (`revealed`, a ledge -> (time, column) map filled by `update_chamber`): `draw_hidden` spreads the `=` out from the landing column at `REVEAL_SPEED` columns a second with a sparkle at the leading edge, and the normal ledge drawing skips these ledges. The chain climbs past the top of the screen to the gem (`GEM_SPOTS[2]`), which is neither drawn nor collectable until the `GEM_APPEARS_AFTER`th (4th) ledge has appeared, so the camera scrolls up once the floor she stands on is near the top of the pinned view (`camera_target_y`). Revealed ledges are saved as `revealed` (indexes into `HIDDEN2`). **Level 4's pink gem** hangs above a mushroom that only sprouts once she walks to the right end of the summit ledge (centre column >= `SECRET_TRIGGER`; `show_secret_mushroom` appends `SECRET_MUSHROOM` to the per-world `MUSHROOMS` copy and sets `secret_shown`, saved as `secret`). It looks like every other mushroom and has no coin above it (the coins still hang above `LEVEL4_MUSHROOMS`). The gem (`SECRET_GEM`, drawn and collectable only after the mushroom has sprouted) is out of reach of a plain bounce (apex 13 rows) and only collectable with the boosted bounce (hold Up as she lands, apex 16 rows). The level ends 3 seconds (`LEVEL_DONE_DELAY`) after the last achievement, so a player who has all the coins and then reaches the summit has little time; the intended play is to take the gem first or leave a coin behind.

**Gem hints:** the inventory overlay shows a cryptic hint for the current level's gem (`GEM_HINTS`, level -> text, wrapped with `textwrap` to the overlay width). Once `gem_taken` it says the gem has been found instead; levels without a gem (8) show nothing.

**Level 7's pink gem** rides on a storm cloud. When the rain starts (`rain_t0` set in `update_flood`, i.e. she reaches ledge 12), `spawn_cloud` registers a sliding ledge (`CLOUD_CFG`: width 10, `lo`..`hi` 86..128, at `CLOUD_FLOOR` = GROUND-51, three rows above ledge 12) with a `"cloud"` flag and queues a toast. It is drawn in the movers loop as a white `~` base with a rounded fluffy top (`(~~~~~~)` and `.--.` on the two rows above, behind the duck) and rain below, and uses the normal mover code, so she rides it. The gem (`GEM_SPOTS[7]`) sits above the cloud's far end and only appears once she has stood on the cloud (`cloud_boarded`, set by `on_cloud()`). The first landing also lowers the water by `CLOUD_DROP` (6) rows once (`flood_drop`, added in `update_flood`), so re-landing cannot keep draining it. While `on_cloud()` is true, `update_flood` pushes `flood_t0`, `rain_t0` and `surge_t0` forward by each tick's elapsed time, so the water holds still until she steps off. `load_state` respawns the cloud when `rain_age` is restored. Test note: she must step right only while the cloud carries her, or she walks off the end.

**Level 6's pink gem** is on a lone ledge half way up the tower (`LONE6`, added with `add_platform` in `World.__init__`, not part of `LEVEL6_LEDGES`, so beetles, coins and the flood config ignore it). It sits far to the right of the tower, so the only way onto it is to walk off the right end of a ledge about 50 rows above (ledges 24 and 26 work; she drifts about one column per two rows of fall) and land on it. Standing on its right 4 columns makes two neighbouring `=` glow pink (`HINT_LEDGES` maps a level to its hint ledge and which end glows; levels 2 and 6 use it). Jumping from there reveals `HIDDEN6`, a zigzag of 7 ledges kept to the right of `LONE6` so a falling duck lands on the lone ledge rather than on a hidden one; the gem (`GEM_SPOTS[6]`) shows after the 4th. Gusts of wind can nudge her while climbing.

**Level 5's pink gem** (the mermaid): if she drowns while her feet are on the grass (`mermaid_pending`, set where `update_flood` starts the drowning), the usual dying animation plays and then she then floats down through the rock for `MERMAID_FLOAT` seconds (eased drift with a sway from where she drowned to beside the mermaid, driven from `update_flood` while the world is frozen; `float_t0`/`float_x0`) instead of seeing the "YOU DROWNED" prompt. When she arrives `enter_mermaid_cave` removes the flood (`flood = None`) and puts her on the cavern floor (`MER_LEDGES`: floor plus stairs back up; drawn by `draw_cavern`, which now serves levels 1 and 5). A mermaid sprite (`MERMAID`) revives her and says `MERMAID_SAYS` ("Be careful little duck!") above her head for the revival plus 2 seconds; input is ignored for `MERMAID_REVIVE` seconds, then the hidden room in the rock opens (`room_open`, the rock wall recedes at `ROOM_OPEN_SPEED`, `MER_ROOM_LEDGES` are added with `add_platform`) and the gem at `MER_GEM` can be collected (`gem_visible()`). Climbing the stairs back onto the grass does not restart the level: the flood is simply put back at the grass (`flood = GROUND + 1`, `flood_t0 = None`) and starts rising again when she lands on the first ledge. Everything else (coins, gem, open room) is kept, and drowning on the grass again drops her back into the open cavern without a new revival. Walking underground is clamped to the cavern's columns (`MER_X0..MER_X1`). Saving while in the cave stores her on the grass with the flood not started.

**Level 3's pink gem** works the same way (`HIDDEN3`; `HIDDEN_LEDGES` maps a level to its hidden ledges and `World.hidden` holds them), but the secret hangs off the beetle's high sliding ledge: the first hidden ledge floats four rows above that mover's left end, so it appears when she jumps from it near its leftmost position. That mover now slides out to `hi=84` so its right end is within a jump of the static top ledge. The hint is on the mover itself: while her feet are on its left 4 columns and the first hidden ledge is not found, two neighbouring `=` glow dim pink (movers loop of `frame`, `movers[1]`). The level 3 achievements hint moved to row -19 so the chain's `=` rows are clear. `GEM_SPOTS` maps each level with a gem to its position; `gem_taken` is per level.

### Swimming and lakes (level 11)

- Lakes are `POND_W` (40) columns wide. Walking in floats the duck on the surface with ripples and a splash.
- **Dive:** while sitting on water, Down floats first, then dives. Down again holds depth; Up rises. The depth rows are limited by `fits()`, which checks that the duck's head and body are inside water or air (`cave_cell`) and not rock.
- **Caves:** `build_caves()` returns `CAVE`, a dict `(x, y) -> "w"` (water) or `"a"` (air pocket). Each lake is a basin that narrows to a shaft, with three tunnels and chambers off the shaft at depths 10, 17 and 24. The first two chambers have air pockets, the deepest has none. Everything else in the cave area is rock (`#`).
- **Air:** while the head is in water (`"w"`), air drains at `BREATH_DRAIN`; otherwise it refills at `BREATH_REGEN`. After running out she cannot dive until air is above `BREATH_MIN`. Running out is a black-out (see lives).
- **Swimmer:** reaching depth 2 unlocks `swimmer`.

### Items and inventory

`ITEMS` maps a key to `(name, map tag, art, description)`. Items are shown in the world as tags (`[U]`, `[P]`, `[O]`) and picked up by overlapping them. `place_items(have)` puts each missing item on its own random ledge, except the pea-shooter, which is on a ledge next to the start (`EASY_SPOTS` in levels 2 and 3). `i` opens the inventory overlay with art and descriptions; items not yet found show as `???`.

| Item | Effect |
|------|--------|
| Umbrella | Hold Up while falling to glide |
| Pea-shooter | Space fires a pea once she holds it (instead of quacking); `s` still works too |
| Oxygen tank | Triples the air capacity |

### Combat

- **Pea-shooter:** `shoot()` needs the item, ammo, not sitting and not diving. A pea flies up to `PEA_RANGE` columns at `PEA_STEP` per column, with a `PEA_COOLDOWN` between shots.
- **Pea packs** (`(o)`) give `PACK_AMMO` peas (max `MAX_AMMO`) and a new one appears elsewhere `PACK_RESPAWN` seconds after pickup. A kill gives `KILL_AMMO` peas.
- **Beetles** patrol a stretch of ledge or ground between `lo` and `hi` and have `BEETLE_HP` hit points. A pea that does not kill one makes it flinch for `BEETLE_HIT_TIME` (white, `(>_<)`, paused and knocked back a column), and its eyes show the damage afterwards (`BEETLE_HURT_EYES`). In level 11 `beetle_target` (`BEETLE_COUNT`) are kept alive by `spawn_beetle`, with respawns after `ENEMY_RESPAWN`. Level 3's single beetle (`ride` is the mover it stands on) and level 2's beetles (`LEVEL2_BEETLES`) do not respawn.
- **Bats** (level 11, at most 2) fly in from the side on a sine wave (`BAT_AMPLITUDE`, `BAT_WAVELENGTH`, `BAT_STEP`) around a base height level with the duck. A crouching duck has a lower hitbox, so it can pass under the wave. Bats leave after 20 s or when far away.
- **Contact:** `check_contact` damages the duck, gives `HIT_INVULN` seconds of invulnerability (hurt flash) and shows "Ouch!".
- Predators can also be hit with peas.

### Achievements

Level 1: `quack`, `allcoins`, `egg`. Level 2: `allcoins`, `slayer`. Level 3: `allcoins`, `slayer`. Level 4: `allcoins`, `summit`. Levels 6, 8, 9 and 10: `allcoins`, `slayer`, `summit`. Levels 5 and 7: `allcoins`, `summit`. Level 11 has 17:

| Key | Title | How it is earned |
|-----|-------|------------------|
| egg | Lay an egg | An egg lands |
| chorus | Quack Chorus | Hold Space for 7 quacks |
| hatchling | Hatchling | An egg hatches |
| mama | Proud Mama | A chick grows into an adult |
| nest | Full Nest | 3 chicks at once |
| snack | Snack Time | Eat a crumb |
| fashion | Fashionista | Try every hat |
| skydiver | Skydiver | Drop through a ledge |
| king | King of the Hill | Reach the top ledge |
| swimmer | Swimmer | Dive 2 rows |
| nature | Nature Lover | Meet a butterfly, frog and fish |
| owl | Night Owl | Fall asleep |
| weather | Weatherduck | See rain and snow |
| rescue | Chick Rescue | Find a lost chick |
| coins | Coin Collector | Collect 10 coins |
| scare | Scarecrow | Scare off a predator |
| happy | Happy Duck | Happiness above 90 |

`a` toggles the achievements overlay (two columns when the screen is short). `toast_queue` shows "Achievement unlocked" banners one at a time (`TOAST_TIME`). In level 1 (only) a "Still to do: ..." line (`still_to_do()`) listing the remaining achievements with their hints is always drawn on the toast row whenever no toast is showing, until the level is done. The undocumented `T` test menu toggles achievements by hand.

### Moving ledges (levels 3 and 4)

`LEVEL3_MOVERS` lists the sliding ledges; each slides between `x0 = lo` and `x0 = hi`, one column every `step` seconds (`MOVER_STEP` = 0.3 s divided by the ledge's speed: 3x for the low one, 2x for the high one). They are not in `PLATFORMS` (so they get no coin or item), only in the `PLATFORMS_BY_X` buckets that `support()` and the renderer read (`configure_level` rebinds the global `MOVERS`). `World.update_mover` steps every mover (`step_mover`): it calls `move_platform(old, new)` to update the buckets and carries whatever stands on it: the duck (if on the ledge's floor and not airborne), any enemy whose `ride` is that mover (its patrol range moves too), and eggs, crumbs, chicks and adults resting on it.

Level 4 reuses the same machinery: `LEVEL4_MOVERS` replaces stairs 6 and 9 of the staircase (those static ledges are dropped from `PLATFORMS`, along with their coins), leaving gaps that can only be crossed by riding the sliding ledges, which carry her like level 3's. The first (row of stair 6) slides between columns 30 and 57, between stairs 5 and 7; the second (row of stair 9) slides across columns 60 to 101, between stair 8 and the last stair.

Sliding ledges are drawn before the trees (the first thing drawn wins a cell), so they pass in front of them.

Level 1 has a little decoration, drawn by `World.draw_level1_decor` after the hints (so it never hides anything), except the springy patch, which `squish_grass` draws just before the ground line so it can replace it: a patch of springy grass (`SQUISH_PATCH`, columns 46 to 60): the green `=` ground line dents (`_`, `-`) under the duck while she stands on it and wobbles (`-`, `~`) back for `SQUISH_TIME` seconds after she leaves (state kept in `squish_at`/`squish_x`, render-only), flocks of four birds that flap across the sky (`BIRD_FLOCKS`, drawn by `draw_birds`; level 2 has two flocks, one flying each way at different heights, so its background is less empty), and a rare twinkle (`*` above the coin for 0.4 s, every `COIN_TWINKLE_PERIOD` seconds per coin, staggered by column). None of it affects gameplay.

Level 3 is built around two movers. The low one (level 1 height) is the only way up: the pea-shooter lies on the static ledge `(94, 108)` at level 2 height, out of jump reach from the ground, so the duck rides the low mover to its right end, where it slides partly under that ledge, and hops up. From there she climbs to the level 3 ledge `(98, 112)`. The beetle rides the high mover, which stays left of column 74, well clear of the spot where the duck jumps from the low mover to the pea-shooter ledge and over twenty columns from that top ledge, so she can shoot it from there without touching it. `place_items` copes with levels that have no low `START_LEDGES`, because `EASY_SPOTS` supplies the positions.

### Flood levels (levels 5 to 7)

Level 5 is the medium flood, level 6 the final climb and level 7 the flood tower. All are built from the `FLOODS` table (`flood_config()`), and `World.flood_cfg` holds the active entry (`ledges`, `coins`, `summit`, `top`, `speed`, `rain_ledge`, `accel`, `start_x`, `hints`). Level 5 is gentler: 26 ledges (mostly 14 to 22 columns wide; every fourth is 36 to 44 wide, with a coin at each end), water at 2.16 rows per second, rain from the 8th ledge with a 0.25 acceleration, and a final surge from ledge 13 (50% of the way up): `surge` is `(ledge, extra speed, extra acceleration)` = `(13, 1.16, 0.23)`, started by `surge_t0` when she first lands there (`None` in levels 6 and 7). Level 5 also has `max_speed` (7.5 rows per second): when it is set, `capped_rise` integrates the water's speed in 0.1 s steps and clamps it, so the end of the climb never gets faster than that (level 6 caps at 1.8).

Level 6 is the combination level. Its `FLOODS[6]` entry has extra keys that `configure_level` reads: `movers`, `mushrooms`, `beetles` (patrols on stair ledges 3 and 8 and mushroom ledges 2, 5, 8, 11, 14 and 17, away from the mushroom at the ledge's end), `items` (the pea-shooter), `packs` and `easy_spots` (the pea-shooter and a pack on the first ledge). The layout is level 4's stairs plus a taller mushroom tower (`mushroom_tower(LEVEL6_DRIFT)`: 18 mushroom ledges instead of 10, 178 rows in all against level 4's 114), mirrored with `mirror_x`; `LEVEL6_SUMMIT` is its top row, and `SKY_MORE` adds sky above so it fits. The stairs, mushroom bounce, sliding ledges (one carries a beetle, like level 3) and wind gusts (`update_wind`, same `WIND_ROW`) all work through the existing level 3/4 code paths, extended to level 6. `update_enemies` drowns a beetle the water reaches and counts it as a kill, so the `slayer` goal cannot be lost by climbing past one.

- `build_flood_ledges()` makes the ledges 4 rows apart (seeded; level 7 has 33, and every fourth is 40 to 50 columns wide, with a coin at each end so she has to run along it), each overlapping the one below by at least four columns, so every step is a plain jump. The config's `summit` is the top ledge's floor row.
- `World.flood` is the water surface row. It starts at `GROUND + 1` and stays put until she first lands on a ledge (`flood_t0` is `None` until then), then rises at the config's `speed` in rows per second (2.16 in level 5, 0.8 in level 6, 3.0 in level 7). When she first lands on ledge `rain_ledge` (the 8th in level 5, the 11th in level 6, the 12th in level 7) the rain starts (`set_weather("rain")`, and random weather changes are off in both flood levels) and the water speeds up by `accel` (0.25 in level 5, 0.015 in level 6, 0.36 in level 7) rows per second every second (all from `update_flood`, using the game clock) and stops at the config's `top`, so the top ledge always stays dry. The save stores `flood_age`, `rain_age` and `surge_age`.
- `wet()` (feet in the water) slows walking by `FLOOD_SLOWDOWN`. `submerged()` (head under) turns the duck blue (`C_DROWNING`); after `FLOOD_DROWN` (3) seconds under, `update_flood` sets `drowned`. `update` then freezes everything except the water and weather; `frame` sinks the duck by `DROWN_SINK` rows with x eyes and rising bubbles, and after `DROWN_ANIM` seconds shows "YOU DROWNED! Press space to restart". `handle` ignores every key except that space, which sets `restart_now`. There is no air meter and no lives on this level (the status bar shows the water gap instead).
- There are no butterflies or frogs here (`update_friends` returns early); instead `World.school` holds `FLOOD_FISH` fish that swim sideways at fixed rows (`update_school`) and are drawn only while under the water. The water is drawn in `frame()` after the scenery but before hints, so everything stays in front of it. The status bar shows how many rows are left between the water and her feet.

### Ice rinks (levels 8 and 9)

Levels 8 and 9 (`ICE_LEVELS`) are flagged by `World.ice` and built from the `ICE` and `ICE2` tables (`ICE_CONFIGS` maps level to table). Each has a `summit` row and, on level 9, `movers` and `mushrooms`. The `ICE` table (`ledges`, `coins`, `beetles`, `start_x`, `items`, `packs`, `easy_spots`, `hints`), read in `configure_level` and `World.__init__`. There are no trees or flowers, the ground and ledges are cyan (`C_ICE`) and it always snows (`weather` is fixed to `"snow"`). The level uses `NO_LIVES_LEVELS` like level 2: health reaching 0 shows the "THE DUCK DIED" popup and space restarts.

`update_ice(now, direction)` replaces the step-per-interval walking with a velocity (`vel`, signed columns per second, `slide_x` keeps the fraction of a column). Holding a direction adds `ICE_ACCEL` up to `ICE_MAX` (22, the walking speed); in the air she only gets `ICE_AIR_ACCEL`, so the speed at take-off carries her. Letting go slows her by `ICE_FRICTION` on the ground. Her feet only animate (`step`) while a direction is held, so a free slide looks like gliding. Sitting (Down) is the brake (`ICE_BRAKE`); a second Down drops through the ledge as usual. The edges of the world are walls (`vel` is zeroed). Shooting kicks her backwards by `ICE_RECOIL`, which can brake or steer her.

Level 9 (`ICE2`) is the harder rink. Its zigzag has narrower ledges that still overlap their neighbours, and also one slow slider (`ICE2_MOVERS`, `World.movers` and `step_mover` as in level 3) that is the only way across the gap before ledge 6, and a mushroom (`ICE2_MUSHROOMS`, the level 4 bounce) that throws her 9 rows up to ledge 10 without holding Up. Her ice speed (`vel`) is kept while riding and bouncing.

`ICE_X` zigzags up to the right, then back to the left. Each ledge overlaps the one below by 2 to 4 columns, so a jump from the edge of one lands under the next; on the ice she still has to manage her speed so she does not slide off the far end.

### The grand tour (level 10)

`GRAND` (shaped like the ice tables and also stored in `ICE_CONFIGS`, so the summit goal, coins and beetles come from the same code) describes a 392 column world, more than twice the area of level 6. The camera scrolls both ways like the full game. From left to right: an icy rink (only columns below `GRAND_ICE_X` are ice: `World.slippery()` switches `update_ice` on by her column, and `ice_at(x)` colours the ledges), a sliding ledge (`GRAND_MOVERS`, level 5 height) that is the only way off the rink, three mushrooms (`GRAND_MUSHROOMS`) that carry her to the launch ledge. The umbrella (`easy_spots["umbrella"]`) is a hidden side path: a ground mushroom behind the start (`(0, GROUND)`, with a coin above it as a lure) bounces her onto a chain of secret sky ledges (`_secret`, one beetle on the fourth). It forks at the fourth ledge: the obvious way on (right, up to column 184) is a false route that ends at a coin and a "wrong way" hint, while the real route doubles back left over the rink, then back right (a switchback, up to row 52 above the ground) to the umbrella at column 102. The second rink ledge's jump also reaches the chain. Dropping off lands back on the route. A hint at the launch ledge only nudges her to look near the start. The chasm after the launch ledge (`GRAND_CHASM`, 60 columns) cannot be jumped, and no ledge near the ground on the far side can be reached from the ground, so the umbrella glide is needed: jump, then hold Up while falling (about 7 rows a second, `GLIDE_DRAIN` stamina a second, shown in the `Glide` bar), keeping Right held until over the far ledge. Coins hang along the glide path. The far side is level 4's mushroom tower (`mushroom_tower(LEVEL6_DRIFT)`) shifted by `GRAND_TOWER_DX` columns and 18 rows down, with wind above `WIND_ROW`. Beetles come from `ledge_patrol`, which keeps them clear of each ledge's mushroom. Leaving the ice keeps her speed for a moment: `coast()` carries `vel` on and `GRASS_DRAG` removes it within a few columns on grass (`ICE_FRICTION` in the air), after which she walks normally. It only runs while no direction is held: holding a key on grass drops the speed at once, so it never adds to the walking speed. Unlike levels 2 and 8 to 9 it uses lives. Running stays disabled.

### Mushrooms and wind (level 4)

- **Bounce pads:** `MUSHROOMS` lists `(x0, floor row)` pads, `MUSH_W` columns wide (`MUSHROOM` art, drawn over the floor). `World.on_mushroom()` is true when her feet are on the pad's floor and her centre is within it. Landing on one (or walking onto it) calls `bounce()` instead of landing: she rises `BOUNCE_ROWS` (11) rows, or `BOUNCE_ROWS + BOUNCE_BOOST` (14) when Up is held, through the normal one-way "rise" phase, which now reads `World.rise_rows` (a plain jump sets it to `JUMP_ROWS`). She can steer in the air, and Shift-running carries her much further. Sitting on a pad does not bounce. A "boing" event plays `BOING_SOUND`.
- **Layout:** floors are 8 rows apart (an 11-row bounce clears the next ledge), except the last step to the summit, which is 12 rows and needs the boosted bounce. Mushrooms sit at alternating ends of the ledges, so each bounce is steered sideways onto the next one. Coins hang over each mushroom and are collected on the way up. Reaching `SUMMIT` unlocks `summit`.
- **Wind:** `update_wind` runs in levels 4 and 6. After `GUST_EVERY` seconds a gust is announced ("Gust coming!"), then after `GUST_WARN` (1.5 s, time to sit) it blows in a random direction for `GUST_TIME`, pushing the duck one column per interval that shrinks from `GUST_PUSH_START` (0.075 s, weak) to `GUST_PUSH_END` (0.01 s, about 100 columns a second; when a frame is slower than the interval she is pushed several columns at once, up to 4) over the gust, so it accelerates and will sweep her off a ledge unless she sits. It only affects her at or above `WIND_ROW` (the upper ledges and the top of the bounces), and a sitting duck is braced and does not move. Streaks are drawn while it blows.
- Level 4 is about 115 rows tall. Part 1 (`LEVEL4_STAIR_X`, hand-staggered ledges 3 rows apart with gaps of up to 2 columns) is plain jumping; part 2 chains mushrooms 8 rows apart (straight for three ledges, then drifting sideways per `LEVEL4_DRIFT`), with a 12-row final step needing the boosted bounce. `SKY_ADDED` (80) extra rows were added to `TOP_MARGIN` for it (and `SKY_EXTRA`, 30 more, for level 5), so save version 6 shifts old saves' rows down by `shift_rows`. The dead-zone camera (`camera_target_y`) follows `feet` during a bounce so she never leaves the screen top.

### Pause and restart

- `p` toggles `World.paused`. While paused, `handle` ignores everything except unpausing and the quit prompt, held keys are cleared, and a PAUSED overlay is shown. `main()` keeps a game clock (`gclock()`: real time minus accumulated paused time) and uses it for every `now`, so timers, animations and growth do not jump when the game resumes. Saves use the same clock.
- `r` opens a "Restart this level?" prompt (`confirm_restart`). `y` sets `restart_now`, and `main()` builds a fresh `World` for the same level (hat and mute carry over). `n`, `q`, `x` or Esc cancel.

### Notices

`notice` is a red line under the toast row for events like "Found the Umbrella!", "Pea pack!", "Ouch!", "Out of peas!" and predator warnings. The toast row at the top is for achievements and level intros.

### Mini-map

`minimap()` compresses the world width into one terminal row using block characters for ledge height, `~` for water, `_` for ground, `c` for chicks and adults and `D` for the duck. The current view is shown in reverse video. It is only shown in levels 2 to 5.

## World class and update order

`World` holds all mutable state for one level. Rough groups:

- **Duck:** `x`, `feet`, `floor`, `airborne`, `air_phase`, `sitting`, `facing`, `dirs`, `depth`, `dive_dir`, `breath`, `stamina`, `health`, `lives`.
- **Things:** `eggs`, `young`, `adults`, `crumbs`, `friends`, `predator`, `enemies`, `peas`, `coins`, `packs`, `pearls`, `item_spots`.
- **Progress:** `unlocked`, `kills`, `inventory`, `ammo`, `level_done`, `golden`.
- **UI:** `toast`, `toast_queue`, `notice`, overlay flags (`show_inventory`, `show_achievements`, `confirm_quit`, `test_menu`), `cam`, `cam_y`.

`handle(name, pressed, now)` handles key events (in this order: quit confirmation, test menu, then game keys). `update(now)` runs these in order each tick:

`update_celebration`, `update_depth`, `update_items`, `update_peas`, `update_mover`, `update_enemies` (with `check_contact`), `update_needs` (with `update_stamina`), `update_duck` (with `update_air`: quacking, egg roll, walking, eating, coins, idle), `update_eggs`, `update_crumbs`, `update_friends`, `update_predator`, `update_young`, `update_adults`, `update_weather`, `update_level_goals`, then the camera easing.

### Camera

- Horizontal: `camera_target()` centres on the duck and clamps to the world. The camera moves at most 2 columns per tick.
- Vertical: in levels 1 to 3, while she is at or above the ground and her floor is clear of the top of the view (the pinned camera lets go when she climbs level 2's hidden ledges), when the view is at least `SCREEN_VIEW_H` (20) rows tall, `camera_target_y()` is pinned to show the whole level. Otherwise it uses a dead zone of `VBUFFER` rows, based on the floor the duck stands on rather than the jump, so jumping does not scroll the screen. Moving at most 1 row per tick. The lake bed is only in range while the duck is in water (`max_cam_y`).

## Rendering

`World.frame(now)` returns one ANSI string per canvas row.

1. **World grid.** A `WORLD_W x WORLD_H` grid of `(char, colour)` cells. `put()` only writes into blank cells, so the order of drawing is the priority order. The order is: duck, umbrella and hat, speech bubbles, flying egg and eggs, crumbs, coins, items, packs, enemies, peas, friends, predator, chicks, adults, quack words and sparkles, splashes, ripples, water surface, trees and flowers, ledges, pearls, grass and cave water and rock, and finally the level hints. `put_sprite(..., opaque=True)` marks blank sprite cells as solid so scenery does not show through the duck.
2. **Camera slice.** The visible part of the grid is cut out.
3. **Screen layers.** Celebration shake, fireworks and confetti, weather particles, clouds, moon and stars are painted into the view with `sky()`, which also only fills blank cells.
4. **Overlays**, drawn over everything: toast, notice, celebration banner, level-complete banner, then one of game over, quit confirm, test menu, inventory or achievements.

`to_ansi(row)` merges runs of the same colour into SGR sequences. `draw()` writes rows starting at `CANVAS_ROW` (5). Rows 1 and 2 are the help bar (`HELP` or `HELP_LEVEL1`), row 3 is the status and row 4 is the mini-map. `main()` only redraws the canvas or the status when it differs from the previous one.

`duck_lines()` builds the duck from parts (body, beak, wing, face, feet) so quacking, preening, shades, sitting and swimming all share one sprite. `sprite()` mirrors any art using the `MIRROR` translation table. Facing is a `+1` / `-1` value.

## Input

`Input` converts raw bytes to `(name, pressed)` events:

- **Kitty protocol** (`parse_kitty`): when `supports_key_release()` finds the terminal supports it, `main()` enables `CSI >11u` and gets true press, repeat and release events. Shift is reported as a modifier (and as keys 57441 and 57447). Plain letters with Shift are uppercased (used for `T`).
- **Fallback** (`parse_plain`): reads ordinary escape sequences. Keys in `HOLD_KEYS` (left, right, space, up) have releases synthesised: a gap longer than `FIRST_REPEAT_DELAY` (before auto-repeat starts) or `REPEAT_GAP` (after) means "released".

`PLAIN_KEYS` maps byte codes to names: Space, `t` egg, `f` feed, `m` mute, `w` weather, `h` hat, `p` pause, `P` predator, `g` friend, `i` inventory, `s` shoot (Space also shoots once she holds the pea-shooter: the `space` branch of `World.handle` fires `shoot` instead of starting a quack), `a` achievements, `T` test menu, `1` to `9`, `0` (level 10) and `-` (level 11) (used by the test menu), Enter, `y`, `n`, and `q` / `x` as quit. Esc is `quit` in both modes. Arrows come from `ARROW_NAMES`.

| Key | Event name | Handled by |
|-----|------------|------------|
| Arrows | `left`, `right`, `up`, `down` | `handle` |
| Shift | `shift` | `handle`, sets `running` (ignored in level 1) |
| Space | `space` | quack |
| `q`, `x`, Esc | `quit` | `World.request_quit`: closes overlays first, then toggles the quit prompt |
| `y`, `n` | `yes`, `no` | answer the quit prompt, or restart at game over |

## Terminal handling and the size gate

- `main()` switches to the alternate screen (so a resize can't corrupt scrollback), hides the cursor and uses cbreak mode. It restores all of that in `finally`.
- `term_size()` reads the live size with `os.get_terminal_size`. `shutil.get_terminal_size` is avoided because it trusts a stale `COLUMNS` variable.
- `too_small(size)` is true below `MIN_COLS` x `MIN_ROWS`. `wait_for_size(fd)` pauses and shows "make your console wider / taller / larger" with arrows pointing the way to grow, along with the current size and "press q to quit". It updates as the window is resized and returns as soon as the size is right.
- The gate runs on the splash, the resume prompt and inside the game loop. In-game it also clears held keys and rebuilds `Input` so a key held during the resize is not stuck.
- On any size change `World.set_view` is called with the new view size and the help bar is redrawn.

### Startup screens

`splash_scene(width, tick)` draws the animated title using the game's sprites: the duck walks in, three ducklings follow, two butterflies flutter, a frog blinks and says "ribbit!", and hearts float. `paint_title` combines it with `TITLE_ART`. `ask_resume` shows the resume prompt if a save exists.

## Saving

- `SAVE_PATH` is `~/.duck_save.json` unless `DUCK_SAVE` is set. `write_save` writes to a temp file and renames it, so a crash can't leave a half-written save. It is written every `SAVE_EVERY` seconds and on a normal exit. A game over deletes it.
- `World.save_state(now)` returns a dict with `version` (14), `level`, `kills`, `unlocked`, `golden`, `hat`, collected coins, meters, `muted`, tried hats, met friends and seen weathers, health, ammo, packs, inventory, item positions, lives, stamina, pearls found, position and floor, chicks (with age and trait), adults and eggs (with age).
- Not saved: enemies (rebuilt from the level, with `kills` removing the first beetles in levels 2 and 3), friends, predators, crumbs and weather.
- `load_state` validates and clamps every field. If it raises `KeyError`, `TypeError` or `ValueError`, `main()` ignores the save and starts level 1.
- **Migration:** a save without `version` 2 was made before the tutorial level existed, so `main()` adds 1 to its level; a save below `version` 3 predates the moving-ledge level, so any level of 2 or more gets another +1; a save below `version` 4 predates the swap of the arena and moving-ledge levels, so levels 2 and 3 are exchanged; a save below `version` 5 predates the mushroom level, so any level of 4 or more gets +1; a save below `version` 6 predates the taller sky, so `shift_rows` moves every saved row down by `SKY_ADDED`; a save below `version` 7 predates the flood tower, so any level of 5 or more gets +1; a save below `version` 8 predates the taller flood tower, so its rows move down by `SKY_EXTRA` and a level 7 save (the flood tower, by then) is dropped (the level restarts); a save below `version` 9 predates the medium flood level, so any level of 5 or more gets another +1; a save below `version` 10 predates the combined level 6, so any level of 6 or more gets +1; a save below `version` 14 predates the grand tour, so any level of 10 or more (after the earlier shifts) gets +1; a save below `version` 13 predates the second ice rink, so any level of 9 or more (after the earlier shifts) gets +1; a save below `version` 12 predates the ice rink, so any level of 8 or more gets +1; a save below `version` 11 predates the taller level 6, so its rows move down by `SKY_MORE` and a level 6 save is dropped (the level restarts). The default for a missing level is 2.

## Sound

`World` appends strings to `events` (`quack`, `coin`, `fanfare`) and `main()` drains them with `pop_events()`. `Sound` plays them with `afplay` and the macOS system sounds (`QUACK_SOUND`, `COIN_SOUND`, `FANFARE_SOUND`) in subprocesses so the game never blocks. Without `afplay`, the quack falls back to the terminal bell and the other sounds are silent. `m` mutes; muted worlds simply don't queue events.

## Testing and extending

There is no automated test suite. Checks so far have been throwaway scripts:

- Build a `World(now, level)`, set state, call `update(t)` and `frame(t)`, and strip ANSI (`re.sub(r"\x1b\[[0-9;]*m", "", ...)`) to inspect the text.
- Run the whole game under a pty (`pty.fork`, `fcntl.ioctl(TIOCSWINSZ)` to set a size) with a bounded read loop, because the game redraws constantly. Set `DUCK_SAVE` to a temp path so the real save is not touched.
- The test keys `t` (egg), `g` (friend), `P` (predator) and `T` (achievement menu) are intended for this.

Adding things:

- **A level:** add a branch in `configure_level`, a list in `LEVEL_ACHIEVEMENTS`, an intro in `LEVEL_INTROS`, raise `LAST_LEVEL` (and `PLAIN_KEYS`, which maps `1` to `9`, `0` (level 10) and `-` (level 11) to `levelN`), set the start x in `World.__init__` and any goal logic in `update_level_goals`. Remember that older saves are mapped by `version`, so bump it if numbering changes.
- **An item:** add art and an `ITEMS` entry, list it in the level's `LEVEL_ITEMS`, and use `"key" in self.inventory` where it matters.
- **An achievement:** add it to the level's list and call `self.unlock(key, now)` where it happens.
- **A friend or enemy:** add a `kind`, an `update_<kind>` method (friends are dispatched by name) and a drawing branch in `frame()`.

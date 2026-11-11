import json
import math
import os
import random
import re
import select
import shutil
import subprocess
import sys
import termios
import textwrap
import time
import tty

# ---- layout -------------------------------------------------------------------------------
STEP = 3  # rows between platform levels; the duck's jump is a little higher than this
MAX_LEVEL = 10
SKY_ADDED = 80  # extra rows of sky for the tall level 6 (saves from before it are shifted down by this much)
SKY_EXTRA = 30  # and more for the taller flood tower (saves from before it are shifted by this much too)
SKY_MORE = 40  # and more again for the taller level 8 (saves from before it are shifted by this much too)
TOP_MARGIN = 10 + SKY_ADDED + SKY_EXTRA + SKY_MORE  # rows of sky above the highest level's feet row
GROUND = TOP_MARGIN + STEP * MAX_LEVEL  # feet row of the ground floor
SURFACE_H = GROUND + 2  # the row under the ground floor holds the grass line
LAKE_DEPTH = 32  # rows below the surface; the last row is the lake bed
WORLD_H = GROUND + LAKE_DEPTH + 1
CAVE_MARGIN = 24  # how far the caves reach past each lake's edge
DEFAULT_VIEW_H = 21
MIN_VIEW_H = 8
VBUFFER = 6  # rows the camera keeps between the duck and the top/bottom of the screen
WORLD_W = 2400  # the world is wider than the screen; the camera follows the duck (level 3; see configure_level)
POND_W = 40
PONDS = [150, 1000, 1800]  # left edge of each lake
MIN_COLS = 150  # the game won't run in a smaller terminal
MIN_ROWS = 35
CANVAS_ROW = 5  # first terminal row used by the canvas (rows 1-2: help, 3: status, 4: mini-map)

# ---- colours (SGR codes) ------------------------------------------------------------------
USE_COLOR = "NO_COLOR" not in os.environ
C_DROWNING = "94"  # the duck turns blue under the flood
C_DUCK, C_BEAK = "93", "38;5;208"
C_WATER, C_RIPPLE = "34", "96"
C_EGG, C_CRUMB = "97", "38;5;137"
C_QUACK, C_BUBBLE, C_STAR = "1;93", "96", "93"
C_CHICK, C_DUCKLING, C_ADULT = "93", "33", "33"
C_LEAF, C_TRUNK = "32", "38;5;94"
C_GRASS, C_PLATFORM = "32", "38;5;130"
C_ICE = "96"
C_COIN = "1;93"
C_FLOWERS = ("91", "95", "93", "97")
C_RAIN, C_SNOW, C_CLOUD, C_MOON = "34", "97", "37", "93"
C_TEXT, C_ZZZ, C_SHADES = "97", "94", "90"
C_BUTTERFLY, C_FROG, C_FISH, C_SPLASH = "95", "92", "96", "96"

# ---- duck ---------------------------------------------------------------------------------
DUCK_W = 9
DUCK_H = 5
FEET = ["   ^ ^", "  ^ ^ "]
WALK_INTERVAL = 0.045
RUN_FACTOR = 0.196  # step interval multiplier while shift is held
JUMP_ROWS = 5  # peak height of a jump in rows
RISE_DELAYS = [0.015, 0.02, 0.025, 0.035, 0.04]  # seconds spent on each row of the climb
HANG_DELAY = 0.04
FALL_DELAYS = [0.035, 0.025, 0.02, 0.015]  # then 0.015 per row
IDLE_BEHAVIORS = [("blink", 0.25), ("look", 0.8), ("preen", 1.5)]
IDLE_GAP = (3.0, 7.0)  # seconds between idle behaviours
THOUGHTS = ["hungry?", "!", "hmm...", "nice day", "la la la", "..."]
THOUGHT_GAP = (8.0, 15.0)
THOUGHT_TIME = 1.8
SLEEP_AFTER = 20.0  # seconds without input before the duck falls asleep and night falls
NOM_TIME = 0.5
# hats are 6 wide and anchored two columns into the duck, above its head
HATS = {
    "tophat": (["  __  ", "_|__|_"], "37"),
    "party": (["  /\\  ", " /__\\ "], "91"),
    "crown": ([" \\^^/ ", " [__] "], "1;33"),
    "shades": None,
}
HAT_ORDER = [None, "tophat", "party", "crown", "shades"]

# ---- quacking -----------------------------------------------------------------------------
MAX_QUACKS = 7
QUACK_INTERVAL = 0.5  # seconds of holding per additional quack
QUACK_U = 12  # distance from the duck's left edge (in its facing direction) to the first quack
QUACK_SPACING = 8
WAVE_AMPLITUDE = 2
BEAK_ROW = 1  # quack and sparkle rows are relative to the top of the duck
BUBBLES = "oO°"
STARS = "*+"
QUACK_WORDS = ["Quack!"] * 12 + ["QUACK!"] * 3 + ["quack?"] * 3 + ["Honk!"] * 2
QUACK_SOUND = "/System/Library/Sounds/Pop.aiff"

# ---- eggs, chicks, ducklings, ducks -------------------------------------------------------
SIT_AFTER = 5.0  # seconds of sitting before an egg may be laid
EGG_BASE_CHANCE = 0.2  # plus up to 0.6 more when she is happy (50% at happiness 50)
EGG_FRAME_TIME = 0.08
EGG = "0"
# (distance behind the duck, rows relative to the floor) the egg passes through as it shoots out
EGG_ARC = [(0, -2), (1, -3), (2, -3), (3, -2), (4, -1), (5, 0)]
HATCH_AFTER = 10.0  # seconds an egg sits before it melts away or hatches (50/50)
MELT_FRAMES = ["o", "°", ".", "_"]
HATCH_FRAMES = ["0", "O", "@", "*"]
ANIM_FRAME_TIME = 0.25

CHICK = ["(o>"]
DUCKLING = ["  _", "=(o>"]
ADULT = ["   __", "__( o>", "\\_<_ )"]
SPRITE_W = {"chick": 3, "duckling": 4}
ADULT_W = 6
CHICK_INTERVAL = 0.0375
CHICK_IDLE_HOP_INTERVAL = 0.11
CHICK_GAP = 4  # spacing between young trailing behind their mama
CHASE_DIST = 18  # how close a butterfly must be for chicks to chase it
GROW_TO_DUCKLING = 30.0  # seconds of age
GROW_TO_DUCK = 70.0
GROWTH_PER_CRUMB = 6.0
LOST_DIST = 20  # an adventurous chick this far from mama when it stops is lost
FOUND_DIST = 10
WANDER_RANGE = 40
ADULT_INTERVAL = 0.075
CLIMB_RANGE = 12  # chicks hop up a ledge when mama is above and this close
PLATFORM_OVERLAP = 5
PREDATOR_EVERY = (45.0, 90.0)
SCARE_DIST = 30  # how close a quacking mama must be to scare a predator off
FOX = [" /\\_/\\", "=(o.o)>"]
FOX_W = 7
HAWK = [[" \\ | / ", "  (o>  "], ["_/ | \\_", "  (o>  "]]
HAWK_W = 8
C_FOX, C_HAWK = "38;5;208", "37"
NOTICE_TIME = 3.0

# ---- world --------------------------------------------------------------------------------
CRUMB = ","
CRUMB_FALL = 0.1
CRUMBS_PER_FEED = 3
WEATHERS = ["clear", "clouds", "rain", "snow"]
WEATHER_EVERY = (25.0, 45.0)
PARTICLE_TICK = 0.08
CLOUD = [" .--. ", "(____)"]
MOON = [" .-.", "( o)", " `-'"]
RIPPLE_FRAMES = ["o", "°", "."]
RIPPLE_FRAME_TIME = 0.3
SPLASH_ARC = [0, 1, 2, 1, 0]
SPLASH_FRAME = 0.08
FRIENDS = ["butterfly", "frog", "fish"]
FRIEND_EVERY = (15.0, 30.0)
MAX_FRIENDS = 3
BUTTERFLY = ["}{", ")("]
FROG = "(o.o)"
FISH = "><>"
FISH_ARC = [(0, GROUND - 1), (1, GROUND - 2), (2, GROUND - 3), (3, GROUND - 3), (4, GROUND - 2), (5, GROUND - 1)]
FISH_FRAME = 0.12
TREE = ["  ,@@,", " '@@@@'", "   ||", "   ||"]
MIRROR = str.maketrans("()<>/\\`'{}", ")(><\\/'`}{")

# ---- achievements -------------------------------------------------------------------------
# (id, title, hint)
ACHIEVEMENTS = [
    ("egg", "Lay an egg", "sit down and wait"),
    ("chorus", "Quack Chorus", "hold space for 7 quacks"),
    ("hatchling", "Hatchling", "an egg hatches into a chick"),
    ("mama", "Proud Mama", "a chick grows into a duck"),
    ("nest", "Full Nest", "have 3 chicks at once"),
    ("snack", "Snack Time", "eat some crumbs (f)"),
    ("fashion", "Fashionista", "try every hat (h)"),
    ("skydiver", "Skydiver", "drop through a ledge"),
    ("king", "King of the Hill", "reach the top ledge"),
    ("swimmer", "Swimmer", "dive in a pond"),
    ("nature", "Nature Lover", "meet a butterfly, frog and fish"),
    ("owl", "Night Owl", "let her fall asleep"),
    ("weather", "Weatherduck", "see rain and snow (w)"),
    ("rescue", "Chick Rescue", "find a lost chick"),
    ("coins", "Coin Collector", "collect 10 coins"),
    ("scare", "Scarecrow", "quack a predator away"),
    ("happy", "Happy Duck", "get happiness above 90"),
]
LEVEL1_ACHIEVEMENTS = [
    ("quack", "Quack", "hold space"),
    ("allcoins", "Pick up every $", "walk into the coins"),
    ("egg", "Lay an egg", "press Down to sit, then wait"),
]
LEVEL2_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins"),
    ("stun", "Stun a mite", "quack (Space) when a mite is close"),
]
LEVEL3_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins"),
    ("slayer", "Defeat every mite", "quack to stun them, then shoot them with the pea-shooter (Space)"),
]
LEVEL4_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins"),
    ("slayer", "Defeat every enemy", "quack to stun the mites, shoot mites and beetles with the pea-shooter (Space)"),
]
LEVEL5_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins"),
    ("slayer", "Defeat every enemy", "shoot them with the pea-shooter (Space)"),
]
LEVEL6_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins, some hang in the air"),
    ("summit", "Reach the summit", "bounce up to the top ledge"),
]
LEVEL7_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins"),
    ("summit", "Escape the flood", "climb to the top ledge"),
]
LEVEL8_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins, some hang in the air"),
    ("slayer", "Defeat every beetle", "shoot them (Space), or let the flood drown them"),
    ("summit", "Escape the flood", "bounce up to the top ledge"),
]
LEVEL9_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins, even the ones over the gaps"),
    ("slayer", "Defeat every enemy", "quack (Space) to stun mites, shoot beetles, hedgehogs once they uncurl and armadillos in the back"),
    ("summit", "Reach the summit", "climb the bramble hill to the top ledge"),
]
LEVEL10_ACHIEVEMENTS = LEVEL7_ACHIEVEMENTS
LEVEL11_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins, even the ones over the gaps"),
    ("slayer", "Defeat every enemy", "shoot them (Space): the kick slows you down"),
    ("summit", "Reach the summit", "climb the icy ledges to the top"),
]
LEVEL12_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins, even the ones over the gaps and above the mushroom"),
    ("slayer", "Defeat every beetle", "shoot them (Space): the kick slows you down"),
    ("summit", "Reach the summit", "ride the sliding ledge, bounce up the mushroom, and climb to the top"),
]
LEVEL13_ACHIEVEMENTS = [
    ("allcoins", "Pick up every $", "grab all the coins, even the ones along the glide"),
    ("slayer", "Defeat every beetle", "shoot them (Space): they are all over the tour"),
    ("summit", "Reach the summit", "slide, ride, bounce, glide over the chasm and climb the tower"),
]
LEVEL_ACHIEVEMENTS = {n: globals()[f"LEVEL{n}_ACHIEVEMENTS"] for n in range(1, 14)}
LEVEL_ACHIEVEMENTS[14] = ACHIEVEMENTS  # finishing a level's list moves on to the next level
LAST_LEVEL = 14
GRAND_LEVEL = 13
HEDGE_LEVEL = 9  # bramble hedgehogs and armadillos  # the grand tour: the biggest level, with every mechanic
ICE_LEVELS = (11, 12)  # the two ice rinks
NO_LIVES_LEVELS = (2, 3, 4, HEDGE_LEVEL, *ICE_LEVELS)  # dying offers a restart instead of costing a life
SLAYER_LEVELS = (3, 4, 5, 8, HEDGE_LEVEL, *ICE_LEVELS, GRAND_LEVEL)  # levels with a "defeat every enemy" goal
BOUNCE_ROWS = 11  # a mushroom throws her this high; holding Up as she lands adds BOUNCE_BOOST
BOUNCE_BOOST = 3
MUSH_W = 5
MUSHROOM = ["(@o@)", " |_| "]
MUSHROOM_SQUASHED = ["     ", "(@o@)"]  # the cap plunges onto the stem
MUSH_PLUNGE = 0.3  # seconds a mushroom stays squashed after a bounce
C_MUSHROOM = "91"
GUST_EVERY = (5.0, 9.0)  # seconds between wind gusts
GUST_WARN = 1.5  # time to react and sit down
GUST_TIME = 3.5
GUST_PUSH_START = 0.075  # seconds per column of wind push when a gust begins: weak...
GUST_PUSH_END = 0.01  # ...and this at its peak, strong enough to sweep her off a ledge
WIND_ROW = GROUND - 60  # the wind only blows at and above this row (level 6's upper ledges)
C_WIND = "38;5;117"
BOING_SOUND = "/System/Library/Sounds/Pop.aiff"
LEVEL_INTROS = {1: "Level 1: quack, pick up every $, and lay an egg",
                2: "Level 2: quack to stun the mites, then pick up every $",
                3: "Level 3: quack to stun the mites and walk all the way right to the pea-shooter, then pick up every $ and defeat them all",
                4: "Level 4: three hills: mites, then beetles. Pick up every $ and defeat them all",
                5: "Level 5: ride the moving ledges to the pea-shooter and on across the gap, then pick up every $ and defeat every enemy",
                6: "Level 6: stun the mites with quacks, find the pea-shooter on the way up, shoot the beetles above it, bounce up the mushrooms to the summit and grab every $",
                7: "Level 7: the water is rising! Grab every $ and climb to the top ledge",
                8: "Level 8: the final climb! Bounce, ride, shoot the beetles and outrun the water to the top",
                9: "Level 9: mites, beetles, hedgehogs that curl into rolling spiky balls and armadillos that only fall to a shot in the back (bounced peas can hurt you)! Grab every $, defeat them all and climb to the top",
                10: "Level 10: the water is rising fast! Grab every $ and climb to the top ledge",
                11: "Level 11: the ice rink! You slide, so press Down to brake. Grab every $, shoot the beetles and climb to the top",
                12: "Level 12: a harder rink! Ride the sliding ledge, bounce up the mushroom, shoot the beetles and grab every $",
                13: "Level 13: the grand tour! Slide, ride, bounce, shoot, find the umbrella to glide over the chasm, then climb the windy tower",
                14: "Level 14"}
LEVEL_DONE_DELAY = 3.0  # seconds of "level complete" before the next level starts
SCREEN_W = MIN_COLS - 1  # levels 1-5 fill the (minimum) screen width
LEVEL4_W = 320  # three hills side by side, so the camera follows the duck
LEVEL4_LEDGES = [(22, 36, 1), (32, 46, 2), (42, 56, 3), (52, 72, 4), (68, 84, 5), (76, 92, 3), (88, 104, 2), (100, 116, 1),  # hill 1: mites, and the pea-shooter on its highest ledge
                 (126, 140, 1), (136, 150, 2), (146, 166, 3), (162, 176, 2), (172, 186, 1),  # hill 2: beetles
                 (204, 218, 1), (214, 228, 2), (224, 238, 3), (234, 248, 4), (244, 262, 5),
                 (258, 274, 4), (270, 286, 3), (282, 298, 2), (294, 308, 1)]  # hill 3: beetles and the secret, climbing to a level 5 top and back down  (x0, x1, ledge level)
LEVEL4_START_X = 6
LEVEL4_SHOOTER = (80, GROUND - 5 * STEP - 1)  # on the highest ledge, a jump up from the top of the first hill
LEVEL4_PACK = (62, GROUND - 4 * STEP - 1)
LEVEL4_MITES = [(16, 34, 0), (34, 42, 2), (54, 68, 4), (78, 88, 3), (90, 100, 2),  # (patrol lo, patrol hi, ledge level): a few on the first hill, stunned to reach the shooter
                (137, 146, 2), (164, 172, 2)]  # two more on hill 2: easy first targets, one pea each
LEVEL4_COINS = [(x, GROUND - 1) for x in (12, 62, 120, 190, 250, 300)]
LEVEL1_LEDGES = [(44, 58, 1), (54, 68, 2), (64, 78, 3), (74, 88, 4), (104, 118, 1)]  # level 1: a four-ledge staircase to the top coin, plus a low ledge
LEVEL1_COINS = [(26, GROUND - 1), (34, GROUND - 1), (80, GROUND - 1), (90, GROUND - 1)]
LEVEL1_START_X = 8
C_HINT = "38;5;245"
LEVEL1_HINTS = [  # (x, row, text) painted on the backdrop, behind everything else; spread over the screen's height
    (3, GROUND - 26, "Welcome, little duck!"),
    (3, GROUND - 22, "Left / Right arrows: walk"),
    (3, GROUND - 18, "Hold Space to quack!"),
    (3, GROUND - 14, "Grab the $ coins  ->"),
    (36, GROUND - 25, "Up arrow: jump onto the ledges"),
    (40, GROUND - 17, "Hop up here, then keep climbing"),
    (36, GROUND - 23, "Press Down on a ledge to drop through it"),
    (96, GROUND - 27, "Press Down to sit,"),
    (96, GROUND - 24, "then wait a few seconds to lay an egg"),
    (96, GROUND - 22, "No egg yet? Get up, sit down, and try again."),
    (96, GROUND - 19, "Quack, grab every $ and lay an egg"),
    (96, GROUND - 16, "to finish the level."),
    (96, GROUND - 12, "Press a to see your achievements."),
    (96, GROUND - 8, "Finish all achievements to move to the next level."),
]
# level 3: the mites. A tiny enemy that is stunned by a quack. Stairs of ledges climb to the pea-shooter, each guarded by a mite, so she has to
# quack (Space) to stun the mites and slip past them. With the pea-shooter in hand, Space shoots instead and one pea kills a mite.
MITE_W = 3
MITE_STEP = 0.2  # seconds per column: quicker than a beetle
MITE_DAMAGE = 10.0
STUN_TIME = 3.0  # seconds a quack keeps a mite still (every new quack renews it)
STUN_RANGE = 26  # columns, either side of the duck
STUN_ROWS = 13  # rows, above or below the duck's feet: a quack carries up a staircase of four ledges
MITE_TOP = "{o}"
MITE_LEGS = ["/|\\", "\\|/"]
MITE_STUNNED = "{x}"
MITE_STARS = ["* *", " * "]
C_MITE = "33"
LEVEL2_W = 200  # wider than the screen, but much shorter than the later levels
LEVEL2_LEDGES = [(30, 44, 1), (40, 54, 2), (50, 70, 3), (66, 80, 2), (76, 90, 1),  # the first hill
                 (120, 134, 1), (130, 144, 2), (140, 160, 3), (156, 170, 2), (166, 180, 1)]  # the second hill  (x0, x1, ledge level)
LEVEL2_START_X = 6
LEVEL2_MITES = [(100, 114, 0), (52, 66, 3), (142, 156, 3), (150, 192, 0)]  # (patrol lo, patrol hi, ledge level): a few, each guarding a stretch of the way
LEVEL2_COINS = [(x, GROUND - 1) for x in (14, 36, 96, 116, 186)]
LEVEL2_HINTS = [(3, GROUND - 15, "Mites bite! Hold Space to quack: it stuns the ones nearby for a few seconds"),
                (3, GROUND - 13, "A stunned mite is harmless: slip past it before it wakes up"),
                (3, GROUND - 11, "Press 'a' to see achievements; complete all achievements to finish the level.")]
LEVEL3_SHIFT = 20  # empty ground before the first coin and mite, so the duck has to walk a little
LEVEL3_W = 300 + LEVEL3_SHIFT  # about twice the screen: the duck has to walk a long way, and the camera follows her
LEVEL3_LEDGES = [(28, 42, 1), (38, 52, 2), (48, 62, 3), (58, 80, 4), (76, 92, 3), (88, 104, 2), (100, 116, 1), (112, 128, 2), (124, 140, 3),  # the first hill
                 (158, 172, 1), (168, 182, 2), (178, 198, 3), (194, 208, 2), (204, 218, 1),  # the second hill
                 (240, 254, 1), (250, 264, 2), (260, 296, 3)]  # the stairs up to the pea-shooter's platform on the far right  (x0, x1, ledge level)
LEVEL3_LEDGES = [(x0 + LEVEL3_SHIFT, x1 + LEVEL3_SHIFT, n) for x0, x1, n in LEVEL3_LEDGES]
LEVEL3_START_X = 6
LEVEL3_SHOOTER = (292 + LEVEL3_SHIFT, GROUND - 3 * STEP - 1)  # at the far right end of the last platform
LEVEL3_PACK = (62 + LEVEL3_SHIFT, GROUND - 4 * STEP - 1)
LEVEL3_MITES = [(16, 26, 0), (40, 48, 2), (60, 70, 4),  # (patrol lo, patrol hi, ledge level): over the first hill...
                (92, 100, 2), (114, 122, 2),
                (160, 168, 1), (180, 194, 3), (206, 214, 1), (150, 230, 0),  # ...the second hill...
                (252, 260, 2), (262, 290, 3), (234, 296, 0)]  # ...and the stairs to the pea-shooter
LEVEL3_MITES = [(lo + LEVEL3_SHIFT, hi + LEVEL3_SHIFT, n) for lo, hi, n in LEVEL3_MITES]
LEVEL3_COINS = [(x + LEVEL3_SHIFT, GROUND - 1) for x in (12, 60, 100, 128, 150, 190, 230, 270)]
LEVEL3_HINTS = [(3, GROUND - 25, "Mites! They bite, but a quack (hold Space) stuns them for a few seconds"),
                (3, GROUND - 23, "Stunned mites are harmless: keep walking right, the pea shooter [P] is far away"),
                (3, GROUND - 21, "With the pea shooter, Space shoots instead of quacking: one pea kills a mite"),
                (3, GROUND - 19, "Press 'a' to see achievements; complete all achievements to finish the level."),
                (LEVEL3_MITES[0][0] + 2, GROUND - 6, "Quack at me!")]
LEVEL4_HINTS = [(3, GROUND - 25, "Three hills! Quack to stun the mites, then climb the first hill"),
                (3, GROUND - 23, "Jump from the top ledge up to the pea shooter [P], then shoot (Space)"),
                (3, GROUND - 21, "Hill 2: one pea kills a mite, a beetle takes three. Shoot from a distance!"),
                (3, GROUND - 19, "Hill 3 is full of beetles: save your peas, packs [o] refill them"),
                (3, GROUND - 17, "Press 'a' to see achievements; complete all achievements to finish the level.")]
LEVEL5_W = 290  # a long level: she rides one sliding ledge to the pea-shooter, then a second one across the big gap
LEVEL5_LEDGES = [(94, 108, 2), (98, 112, 3),  # static ledges (the pea-shooter is on the first); the moving ones are LEVEL5_MOVERS
                 (177, 193, 3), (189, 205, 4), (201, 221, 5), (217, 233, 4), (229, 245, 3), (241, 257, 2)]  # beyond the second slider: up, then back down (the last step is out of jump reach from the ground)  (x0, x1, ledge level)
LEVEL5_COINS = [(x, GROUND - 1) for x in (12, 45, 70, 125, 160, 215, 250, 280)]
LEVEL5_BEETLES = [(178, 189, 3), (190, 201, 4), (202, 217, 5), (218, 229, 4), (230, 241, 3), (242, 253, 2), (150, 285, 0)]  # (patrol lo, patrol hi, ledge level)
MOVER_STEP = 0.3  # seconds per column for a speed-1 ledge
LEVEL5_MOVERS = [  # ledges sliding between x0=lo and x0=hi; the one with a beetle is out of reach from below
    {"w": 14, "n": 1, "lo": 20, "hi": 90, "step": MOVER_STEP / 3},  # the only way up to the pea-shooter ledge
    {"w": 12, "n": 3, "lo": 36, "hi": 84, "step": MOVER_STEP / 2, "beetle": True},
    {"w": 12, "n": 3, "lo": 113, "hi": 165, "step": MOVER_STEP / 2.5},  # slides between the top ledge (ends at 112) and the far ledges (start at 177), touching each at the ends (index 2: the glint and the secret use index 1)
]
LEVEL5_START_X = 24
LEVEL5_HINTS = [(3, GROUND - 13, "Ride the moving ledge to reach the pea shooter [P]"), (3, GROUND - 12, "Press Space to shoot"),
                (44, GROUND - 17, "Shoot the beetle on the high moving ledge"), (44, GROUND - 15, "from the ledge across from it."),
                (100, GROUND - 21, "Ride the second moving ledge across the gap"),
                (36, GROUND - 19, "Press 'a' to see achievements; complete all achievements to finish the level.")]
# Level 6 climbs in two parts. Part 1 is plain jumping: a staggered staircase of ledges 3 rows apart, each a plain jump from the last.
# Part 2 is mushrooms: ledges 8 rows apart that alternate right and left, a mushroom at the end of each throwing her
# toward the next one. The very last step is 12 rows and needs the boosted bounce.
LEVEL6_STAIRS = 10
LEVEL6_STAIR_X = [(36, 58), (60, 80), (44, 64), (24, 46), (8, 30), (32, 52), (54, 76), (78, 98), (58, 80), (72, 101)]  # staggered by hand
LEVEL6_LEDGES = [(x0, x1, GROUND - STEP * k) for k, (x0, x1) in enumerate(LEVEL6_STAIR_X, 1)]  # (x0, x1, floor row)
LEVEL6_DRIFT = [0, 0, 0, -6, 4, -5, 12, -4, 14, -8]  # sideways shift of each mushroom ledge: straight at first, then wandering
LEVEL8_DRIFT = LEVEL6_DRIFT[:9] + [-4, 8, -4, 10, -6, 10, -6, 8, -8]  # level 8 keeps climbing: 18 mushroom ledges


def mushroom_tower(drift):
    """The mushroom part above the stairs: ledges 8 rows apart (the last 12), a mushroom at the end of each but the last."""
    ledges, mushrooms = [], [(95, GROUND - STEP * LEVEL6_STAIRS)]  # (x0, floor row)
    for j in range(1, len(drift) + 1):
        floor = GROUND - STEP * LEVEL6_STAIRS - 8 * j if j < len(drift) else GROUND - STEP * LEVEL6_STAIRS - 8 * (j - 1) - 12
        d = drift[j - 1]
        ledges.append((59 + d, 95 + d, floor) if j % 2 else (67 + d, 105 + d, floor))
        if j < len(drift):
            mushrooms.append((61 + d, floor) if j % 2 else (99 + d, floor))
    return ledges, mushrooms


_tower, LEVEL6_MUSHROOMS = mushroom_tower(LEVEL6_DRIFT)
LEVEL6_LEDGES += _tower
LEVEL6_COINS = [(x0 + 2, floor - 7) for x0, floor in LEVEL6_MUSHROOMS]  # hanging above each mushroom
LEVEL6_MOVERS = [  # sliding ledges that replace stairs 6 and 9: the gaps they leave can only be crossed by riding them
    {"w": 14, "n": 6, "lo": 30, "hi": 44, "step": MOVER_STEP / 2},
    {"w": 14, "n": 9, "lo": 60, "hi": 88, "step": MOVER_STEP / 2},
]
LEVEL6_START_X = 40
LEVEL6_MITES = [(8, 30, GROUND), (100, 140, GROUND), (62, 76, GROUND - 3 * 2), (26, 42, GROUND - 3 * 4), (10, 26, GROUND - 3 * 5),
                (56, 72, GROUND - 3 * 7), (80, 94, GROUND - 3 * 8)]  # mites patrol the stairs at the bottom: (patrol lo, patrol hi, floor row)
LEVEL6_BEETLES = [(70, 95, 144), (64, 90, 128), (66, 92, 112)]  # beetles on mushroom ledges above the pea-shooter: (patrol lo, patrol hi, floor row)
LEVEL6_SHOOTER = (86, GROUND - 3 * 10 - 9 - 1)  # on the first mushroom ledge, about a third of the way up
LEVEL6_PACK = (72, GROUND - 3 * 10 - 9 - 1)
SUMMIT = LEVEL6_LEDGES[-1][2]
LEVEL6_HINTS = [(3, GROUND - 6, "Up arrow: jump up the ledges"),
                (3, GROUND - 4, "Press 'a' to see achievements; complete all achievements to finish the level."),
                (3, GROUND - 9, "Mites! Quack (Space) to stun them"), (3, GROUND - 8, "Pea shooter [P]: a third of the way up"),
                (3, GROUND - 31, "Bounce on the mushrooms to climb!"), (3, GROUND - 29, "Hold Up as you land to bounce higher"),
                (3, GROUND - 27, "Steer in the air to land on the next ledge"),
                (3, GROUND - 17, "Ride the moving ledges to cross the gaps"),
                (3, GROUND - 63, "Gusts blow up here: hold Down to sit and brace"),
                (3, SUMMIT + 14, "The last step needs a bigger bounce: hold Up as you land")]
HINTS_BY_LEVEL = {1: LEVEL1_HINTS, 2: LEVEL2_HINTS, 3: LEVEL3_HINTS, 4: LEVEL4_HINTS, 5: LEVEL5_HINTS, 6: LEVEL6_HINTS}
ENEMY_W = 5
FLOOD_SLOWDOWN = 2.0  # wading is slower than walking
FLOOD_FISH = 40  # fish swimming around the tower; each is only drawn while it is under the water
FLOOD_DROWN = 3.0  # seconds under the water before she drowns
DROWN_ANIM = 1.5  # seconds of the dying animation before the restart prompt appears
DROWN_SINK = 6  # rows she sinks while drowning


def build_flood_ledges(count, wide_every, narrow, wide, seed):
    """A tower of staggered ledges, STEP+1 rows apart; each overlaps the one below by at least four columns."""
    rng = random.Random(seed)
    ledges, x0, x1 = [], 50, 74
    for k in range(1, count + 1):
        width = rng.randint(*wide) if k % wide_every == 0 else rng.randint(*narrow)
        lo, hi = max(4, x0 - width + 4), min(x1 - 4, SCREEN_W - 5 - width)
        x0 = rng.randint(lo, hi)
        x1 = x0 + width - 1
        ledges.append((x0, x1, GROUND - (STEP + 1) * k))
    return ledges


def flood_config(ledges, coins, speed, accel, rain_ledge, start_x, hints, surge=None, max_speed=None, **extra):
    summit = ledges[-1][2]
    return {**extra, "ledges": ledges, "coins": coins, "summit": summit, "top": summit + 6,  # the water stops rising at "top", so the top ledge stays dry
            "speed": speed,  # rows per second the water rises at first...
            "rain_ledge": rain_ledge,  # ...until she reaches this ledge (counting from 1) and the rain starts (None: no rain)...
            "accel": accel,  # ...then it speeds up by this many rows per second every second
            "surge": surge,  # (ledge, extra speed, extra acceleration): past this ledge the water speeds up again (None: never)
            "max_speed": max_speed,  # the water never rises faster than this many rows per second (None: no limit)
            "start_x": start_x, "hints": hints}


# level 8 mirrors level 6's tower (stairs, mushrooms, sliding ledges, wind) and adds beetles, a pea-shooter and a rising flood
def mirror_x(x0, x1):
    return SCREEN_W - 1 - x1, SCREEN_W - 1 - x0


_tower, _mushrooms = mushroom_tower(LEVEL8_DRIFT)
LEVEL8_LEDGES = [(*mirror_x(x0, x1), floor) for x0, x1, floor in LEVEL6_LEDGES[:LEVEL6_STAIRS] + _tower]
LEVEL8_MUSHROOMS = [(mirror_x(x0, x0 + MUSH_W - 1)[0], floor) for x0, floor in _mushrooms]
LEVEL8_SUMMIT = LEVEL8_LEDGES[-1][2]
LEVEL8_MOVERS = [{**spec, "lo": SCREEN_W - spec["w"] - spec["hi"], "hi": SCREEN_W - spec["w"] - spec["lo"]} for spec in LEVEL6_MOVERS]
LEVEL8_MOVERS[1]["beetle"] = True  # a beetle rides the second sliding ledge, so it has to be shot before the gap can be crossed
LEVEL8_MOVER_ROWS = {GROUND - STEP * spec["n"] for spec in LEVEL8_MOVERS}


def level8_beetles():
    """Patrols on stair ledges 3 and 8 and on mushroom ledges 2, 5, 8, 11, 14 and 17, kept clear of the mushroom at the ledge's end."""
    beetles = []
    mushroom_at = {floor: x0 for x0, floor in LEVEL8_MUSHROOMS}
    for k in (3, 8, 12, 15, 18, 21, 24, 27):
        x0, x1, floor = LEVEL8_LEDGES[k - 1]
        m = mushroom_at.get(floor)
        if m is None:
            lo, hi = x0 + 2, x1 - ENEMY_W - 1
        elif m - x0 > x1 - (m + MUSH_W - 1):
            lo, hi = x0 + 1, m - ENEMY_W - 1
        else:
            lo, hi = m + MUSH_W + 1, x1 - ENEMY_W + 1
        beetles.append((lo, hi, floor))
    return beetles


LEVEL8_FIRST = LEVEL8_LEDGES[0]
# level 7 is the medium flood: a shorter tower than level 10 with mid-sized ledges, slower water and a gentler rain
MEDIUM_LEDGES = build_flood_ledges(26, 4, (14, 22), (36, 44), 5)
# level 10 is the flood tower: a tall tower of mostly narrow ledges, where rain makes the water speed up
HARD_LEDGES = build_flood_ledges(33, 4, (16, 26), (40, 50), 77)
FLOODS = {
    7: flood_config(MEDIUM_LEDGES, [(x, floor - 1) for x0, x1, floor in MEDIUM_LEDGES if x1 - x0 > 30 for x in (x0 + 3, x1 - 3)],
                    1.94, 0.225, 8, 56,
                    [(3, GROUND - 10, "The water is rising! Jump up the ledges to stay above it"),
                     (3, GROUND - 8, "Stay above the water: under it for 3 seconds and you drown"),
                     (3, GROUND - 6, "Press 'a' to see achievements; complete all achievements to finish the level.")],
                    surge=(13, 1.04, 0.21), max_speed=6.75),  # halfway up (ledge 13 of 26)
    10: flood_config(HARD_LEDGES, [(x, floor - 1) for x0, x1, floor in HARD_LEDGES if x1 - x0 > 30 for x in (x0 + 3, x1 - 3)],  # both ends of each wide ledge, so she has to run along it
                    3.0, 0.36, 12, 56,
                    [(3, GROUND - 10, "The water is rising! Jump up the ledges to stay above it"),
                     (3, GROUND - 8, "Stay above the water: under it for 3 seconds and you drown"),
                     (3, GROUND - 6, "Press 'a' to see achievements; complete all achievements to finish the level.")]),
}
FLOODS[8] = flood_config(
    LEVEL8_LEDGES, [(x0 + 2, floor - 7) for x0, floor in LEVEL8_MUSHROOMS], 0.8, 0.015, 11, SCREEN_W - LEVEL6_START_X - DUCK_W,
    [(3, GROUND - 6, "Grab the pea shooter [P] and shoot the beetles (Space)"),
     (3, GROUND - 4, "Press 'a' to see achievements; complete all achievements to finish the level."),
     (3, GROUND - 17, "Ride the moving ledges to cross the gaps; shoot the beetle riding one"),
     (3, GROUND - 31, "Bounce on the mushrooms to climb! Hold Up as you land for more height"),
     (3, GROUND - 29, "The water keeps rising: stay above it and keep moving"),
     (3, GROUND - 63, "Gusts blow up here: hold Down to sit and brace"),
     (3, LEVEL8_SUMMIT + 14, "The last step needs a bigger bounce: hold Up as you land")],
    max_speed=1.8, movers=LEVEL8_MOVERS, mushrooms=LEVEL8_MUSHROOMS, beetles=level8_beetles(),
    items=["peashooter"], packs=6,
    easy_spots={"peashooter": (LEVEL8_FIRST[0] + 3, LEVEL8_FIRST[2] - 1), "pack": (LEVEL8_FIRST[1] - 3, LEVEL8_FIRST[2] - 1)})
HINTS_BY_LEVEL.update({level: cfg["hints"] for level, cfg in FLOODS.items()})

# level 9 is bramble hill: a zigzag of ledges climbing back and forth (like the rinks, but on grass). Hedgehogs walk up their ledge, curl at the top and
# roll back down: peas bounce off the ball. Armadillos patrol and only a pea in the back hurts them: one that hits the front bounces back at the duck.
HEDGE_X = ([(4 + 20 * k, 30 + 20 * k) for k in range(6)] + [(84 - 20 * k, 110 - 20 * k) for k in range(5)]
           + [(24 + 20 * k, 50 + 20 * k) for k in range(5)] + [(84 - 20 * k, 110 - 20 * k) for k in range(5)])  # right, left, right, left: 21 ledges
HEDGE_LEDGES = [(x0, x1, GROUND - STEP * k) for k, (x0, x1) in enumerate(HEDGE_X, 1)]
HEDGE_COINS = [(x, GROUND - 1) for x in (45, 75, 105, 135)]
HEDGE_COINS += [((min(HEDGE_X[k - 1][1], HEDGE_X[k][1]) + max(HEDGE_X[k - 1][0], HEDGE_X[k][0])) // 2, GROUND - STEP * k - 4) for k in (3, 6, 9, 12, 15, 18)]


HEDGE_MUSH_LEDGES = (4, 14)  # a mushroom at the left end of each of these ledges throws her up to the ledge 4 above it, in the same columns
HEDGE_MUSHROOMS = [(HEDGE_X[k - 1][0], GROUND - STEP * k) for k in HEDGE_MUSH_LEDGES]
HEDGE_MOVERS = [{"w": 12, "n": 8, "lo": 98, "hi": 128, "step": MOVER_STEP / 2}]  # a sliding ledge a jump above ledge 7, with a coin hovering over it
HEDGE_COINS += [(x0 + 2, floor - 7) for x0, floor in HEDGE_MUSHROOMS] + [(115, GROUND - STEP * 8 - 4)]


def hedge_patrol(k):
    """A patrol across ledge k (1-based), with the direction of the next ledge as its uphill; it stays clear of the ledge's mushroom."""
    x0, x1 = HEDGE_X[k - 1]
    return x0 + 1 + (MUSH_W + 1 if k in HEDGE_MUSH_LEDGES else 0), x1 - ENEMY_W, GROUND - STEP * k, 1 if HEDGE_X[k][0] > x0 else -1


HEDGE_HEDGEHOGS = [(36, 100, GROUND, 1)] + [hedge_patrol(k) for k in (2, 5, 8, 11, 14, 17, 20)]  # (patrol lo, hi, floor row, uphill direction)
HEDGE_BEETLES = [hedge_patrol(k)[:3] for k in (4, 10, 16)]
HEDGE_MITES = [(lo, x1 - MITE_W + 1, floor) for k in (1, 7, 13, 19) for lo, x1, floor in [(HEDGE_X[k - 1][0] + (14 if k == 1 else 1), HEDGE_X[k - 1][1], GROUND - STEP * k)]]  # the first one starts clear of the duck
HEDGE_ARMADILLOS = [(105, 140, GROUND)] + [hedge_patrol(k)[:3] for k in (3, 6, 9, 12, 15, 18)]
HEDGE = {"summit": HEDGE_LEDGES[-1][2], "ledges": HEDGE_LEDGES, "coins": HEDGE_COINS, "hedgehogs": HEDGE_HEDGEHOGS, "armadillos": HEDGE_ARMADILLOS, "beetles": HEDGE_BEETLES, "mites": HEDGE_MITES,
         "movers": HEDGE_MOVERS, "mushrooms": HEDGE_MUSHROOMS,
         "start_x": 8, "items": ["peashooter"], "packs": 12,
         "easy_spots": {"peashooter": (HEDGE_LEDGES[0][0] + 3, HEDGE_LEDGES[0][2] - 1), "pack": (HEDGE_LEDGES[0][1] - 3, HEDGE_LEDGES[0][2] - 1)},
         "hints": []}
# level 11 is the ice rink: the duck keeps her speed and slides. A zigzag of ledges climbs back and forth, with gaps that need a
# running start (a gap of 1 or 2 columns needs about 9 or 13 columns a second, and the jump has to leave from the last column or two).
ICE_MAX = 22.0  # top speed in columns per second (the same as walking)
ICE_ACCEL = 16.0  # columns per second gained each second while a direction is held
ICE_AIR_ACCEL = 14.0  # she can barely steer in the air: what she had at take-off carries her across
ICE_FRICTION = 3.5  # columns per second lost each second while sliding free
ICE_BRAKE = 40.0  # ...and while sitting: Down is the brake
GRASS_DRAG = 120.0  # leaving the ice: the leftover speed on grass dies away this fast (columns per second each second)
ICE_RECOIL = 14.0  # the pea-shooter kicks her backwards by this much speed
ICE_X = [(4, 28), (26, 47), (45, 65), (63, 80), (78, 93), (91, 104), (102, 115),  # to the right: each ledge overlaps the last by 2 to 4 columns...
         (92, 105), (82, 95), (72, 85), (62, 75), (52, 65), (42, 55), (32, 45), (22, 35),  # ...and back to the left
         (33, 60), (58, 88), (86, 120)]  # then three larger platforms at the top
ICE_LEDGES = [(x0, x1, GROUND - STEP * k) for k, (x0, x1) in enumerate(ICE_X, 1)]
ICE_COINS = [(x, GROUND - 1) for x in (45, 75, 105, 135)]  # on the rink floor
ICE_COINS += [((min(ICE_X[k - 1][1], ICE_X[k][1]) + max(ICE_X[k - 1][0], ICE_X[k][0])) // 2, GROUND - STEP * k - 4) for k in (3, 6, 9, 12)]  # hovering over some of the gaps
ICE_SUMMIT = ICE_LEDGES[-1][2]
ICE_BEETLES = [(66, 100, GROUND)] + [(ICE_X[k - 1][0] + 1, ICE_X[k - 1][1] - ENEMY_W, GROUND - STEP * k) for k in (2, 4, 6)]
ICE = {"summit": ICE_SUMMIT, "ledges": ICE_LEDGES, "coins": ICE_COINS, "beetles": ICE_BEETLES, "hedgehogs": [(105, 140, GROUND, 1), (ICE_X[16][0] + 1, ICE_X[16][1] - ENEMY_W, GROUND - STEP * 17, 1)],
       "armadillos": [(ICE_X[2][0] + 1, ICE_X[2][1] - ENEMY_W, GROUND - STEP * 3), (ICE_X[17][0] + 1, ICE_X[17][1] - ENEMY_W, GROUND - STEP * 18)], "start_x": 20, "items": ["peashooter"], "packs": 6,
       "easy_spots": {"peashooter": (ICE_LEDGES[0][0] + 3, ICE_LEDGES[0][2] - 1), "pack": (ICE_LEDGES[0][1] - 3, ICE_LEDGES[0][2] - 1)},
       "hints": [(3, GROUND - 14, "Ice! You keep sliding after you let go: press Down to sit and brake"),
                 (3, GROUND - 12, "Take a run-up to jump the gaps: you can hardly steer in the air"),
                 (3, GROUND - 10, "Shooting (Space) kicks you backwards: use it to slow down, or shoot while you slide"),
                 (3, GROUND - 8, "Falling only drops you down. 'a': achievements")]}
HINTS_BY_LEVEL[HEDGE_LEVEL] = HEDGE["hints"]
HINTS_BY_LEVEL[11] = ICE["hints"]

# level 12 is a harder rink: narrower ledges that still overlap their neighbours by a few columns, a sliding ledge that carries her over a gap too wide to
# jump, and a mushroom that throws her up to a ledge 9 rows above (a plain jump is 5).
ICE2_X = [(4, 28), (26, 48), (46, 66), (64, 84), (82, 100), (117, 136),  # to the right (the sliding ledge fills the gap before the 6th)...
          (110, 126), (96, 112), (82, 98)]  # ...back to the left; a mushroom on the last of these throws her to the next
ICE2_LEDGES = [(x0, x1, GROUND - STEP * k) for k, (x0, x1) in enumerate(ICE2_X, 1)]
ICE2_LEDGES += [(64, 90, GROUND - STEP * 9 - 9), (49, 67, GROUND - STEP * 9 - 12), (34, 52, GROUND - STEP * 9 - 15),
                (19, 37, GROUND - STEP * 9 - 18), (4, 22, GROUND - STEP * 9 - 21)]
ICE2_MOVERS = [{"w": 12, "n": 5, "lo": 98, "hi": 108, "step": MOVER_STEP / 2}]  # overlaps ledge 5 at one end and ledge 6 at the other
ICE2_MUSHROOMS = [(84, GROUND - STEP * 9)]
ICE2_COINS = [(x, GROUND - 1) for x in (45, 75, 105, 135)]
ICE2_COINS += [(x0 + 2, floor - 7) for x0, floor in ICE2_MUSHROOMS]  # hanging above the mushroom
ICE2_COINS += [(110, GROUND - STEP * 5 - 3)]  # above the sliding ledge
ICE2_BEETLES = [(66, 100, GROUND)] + [(ICE2_X[k - 1][0] + 1, ICE2_X[k - 1][1] - ENEMY_W, GROUND - STEP * k) for k in (2, 4, 7)]
ICE2_BEETLES += [(ICE2_LEDGES[10][0] + 1, ICE2_LEDGES[10][1] - ENEMY_W, ICE2_LEDGES[10][2])]
ICE2 = {"summit": ICE2_LEDGES[-1][2], "ledges": ICE2_LEDGES, "coins": ICE2_COINS, "beetles": ICE2_BEETLES, "start_x": 20,
        "movers": ICE2_MOVERS, "mushrooms": ICE2_MUSHROOMS, "items": ["peashooter"], "packs": 6,
        "easy_spots": {"peashooter": (ICE2_LEDGES[0][0] + 3, ICE2_LEDGES[0][2] - 1), "pack": (ICE2_LEDGES[0][1] - 3, ICE2_LEDGES[0][2] - 1)},
        "hints": [(3, GROUND - 14, "A harder rink: the gaps are back, and so are the beetles"),
                  (3, GROUND - 12, "The wide gap is crossed by riding the sliding ledge"),
                  (3, GROUND - 10, "A mushroom [(@o@)] throws you high: hold Up as you land for more. 'a': achievements")]}
ICE_CONFIGS = {HEDGE_LEVEL: HEDGE, 11: ICE, 12: ICE2}
HINTS_BY_LEVEL[12] = ICE2["hints"]

# level 13 is the grand tour, by far the biggest level: GRAND_W columns wide and as tall as level 8 (more than twice its area). It uses
# every mechanic in turn, left to right: an icy rink (the ice stops at GRAND_ICE_X), a sliding ledge, three mushrooms up to a
# long launch ledge, a chasm 60 columns wide that can only be crossed by gliding (hold Up while falling), and a
# windy mushroom tower on the far side. The umbrella is a secret: it is off the path, high above the rink. Beetles patrol all along and the pea-shooter is on the first ledge.
GRAND_W = 392
GRAND_ICE_X = 107
GRAND_TOWER_DX = 261  # the tower reuses level 6's mushroom tower, shifted right and 18 rows down so that it starts on the far ledge
GRAND_CHASM = (262, 322)  # the launch ledge ends and the far ledge begins
_rink = [(4, 26), (24, 46), (44, 66), (64, 86), (84, 106)]
_grand = [(x0, x1, GROUND - STEP * k) for k, (x0, x1) in enumerate(_rink, 1)]
_grand += [(133, 152, GROUND - 18), (150, 170, GROUND - 21), (158, 188, GROUND - 29), (176, 206, GROUND - 37), (196, 262, GROUND - 45),
           (322, 362, GROUND - 12)]
# the secret: a mushroom on the ground behind the start throws her up to a chain of sky ledges above the rink, ending at the umbrella
_secret = [(2, 22, GROUND - 9), (20, 40, GROUND - 13), (38, 58, GROUND - 17), (56, 76, GROUND - 20), (74, 94, GROUND - 24),
           (92, 112, GROUND - 28), (110, 130, GROUND - 32), (128, 148, GROUND - 36), (146, 166, GROUND - 40), (164, 184, GROUND - 44),
           (38, 58, GROUND - 24), (20, 40, GROUND - 28), (2, 22, GROUND - 32),
           (20, 40, GROUND - 36), (38, 58, GROUND - 40), (56, 76, GROUND - 44), (74, 94, GROUND - 48), (92, 112, GROUND - 52)]
_grand += _secret
_tower, _tower_mushrooms = mushroom_tower(LEVEL8_DRIFT)
_tower = [(x0 + GRAND_TOWER_DX, x1 + GRAND_TOWER_DX, floor + 18) for x0, x1, floor in _tower]
GRAND_MUSHROOMS = [(0, GROUND), (166, GROUND - 21), (182, GROUND - 29), (200, GROUND - 37)] + [(x + GRAND_TOWER_DX, floor + 18) for x, floor in _tower_mushrooms]
GRAND_MOVERS = [{"w": 12, "n": 5, "lo": 104, "hi": 124, "step": MOVER_STEP / 2}]  # level 7 height: overlaps the rink's last ledge and the one after the gap


def ledge_patrol(ledge, mushrooms):
    """A beetle's patrol on a ledge, kept clear of the mushroom at its end."""
    x0, x1, floor = ledge
    m = {f: mx for mx, f in mushrooms if x0 <= mx <= x1}.get(floor)  # only a mushroom on this ledge
    if m is None:
        return x0 + 2, x1 - ENEMY_W - 1, floor
    if m - x0 > x1 - (m + MUSH_W - 1):
        return x0 + 1, m - ENEMY_W - 1, floor
    return m + MUSH_W + 1, x1 - ENEMY_W + 1, floor


GRAND_BEETLES = [(36, 90, GROUND)] + [ledge_patrol(_grand[k], GRAND_MUSHROOMS) for k in (1, 3, 5, 7, 8, 9)]
GRAND_BEETLES += [(58, 68, GROUND - 20)]  # guards the way to the umbrella
GRAND_BEETLES += [ledge_patrol(_tower[k], GRAND_MUSHROOMS) for k in (1, 4, 7, 10, 13, 16)]
GRAND_COINS = [(x, GROUND - 1) for x in (40, 70, 100, 130, 175, 225, 285, 305)]  # the last two lie in the chasm
GRAND_COINS += [(114, GROUND - 18)]  # above the sliding ledge
GRAND_COINS += [(x0 + 2, floor - 7) for x0, floor in GRAND_MUSHROOMS]  # above every mushroom
GRAND_COINS += [(174, GROUND - 45)]  # the false route's consolation prize
GRAND_COINS += [(276, GROUND - 41), (294, GROUND - 36), (312, GROUND - 30)]  # along the glide
GRAND = {"summit": _tower[-1][2], "ledges": _grand + _tower, "coins": GRAND_COINS, "beetles": GRAND_BEETLES, "start_x": 8,
         "movers": GRAND_MOVERS, "mushrooms": GRAND_MUSHROOMS, "items": ["umbrella", "peashooter"], "packs": 8, "width": GRAND_W,
         "easy_spots": {"peashooter": (_rink[0][0] + 3, GROUND - STEP - 1), "pack": (_rink[0][1] - 3, GROUND - STEP - 1),
                        "umbrella": (102, GROUND - 53)},
         "hints": [(3, GROUND - 15, "The grand tour! Ice first: you slide, press Down to brake. Grab the pea shooter [P] (Space)"),
                   (3, GROUND - 13, "Press 'a' to see achievements; complete all achievements to finish the level."),
                   (108, GROUND - 24, "Ride the sliding ledge across the gap"),
                   (150, GROUND - 33, "Mushrooms throw you high: hold Up as you land for more"),
                   (200, GROUND - 52, "This chasm is far too wide to jump. Something to help must be hiding back near the start..."),
                   (200, GROUND - 50, "With the umbrella: jump off the end and hold Up while falling to glide. It drains stamina, so go straight across"),
                   (150, GROUND - 47, "Nothing up here but a view. Wrong way!"),
                   (262, GROUND - 66, "Gusts blow up high: hold Down to sit and brace")]}
ICE_CONFIGS[GRAND_LEVEL] = GRAND  # shares the shape of the ice tables (summit, ledges, coins, beetles...)
HINTS_BY_LEVEL[GRAND_LEVEL] = GRAND["hints"]
SCREEN_VIEW_H = 20  # rows needed to see the whole level (levels 1-4)
LEVEL4_BEETLES = [(148, 162, 3), (118, 184, 0),  # hill 2: just two, spaced out, so she can learn to shoot a beetle from range
                  (216, 224, 2), (225, 234, 3), (246, 258, 5), (259, 270, 4), (271, 282, 3), (283, 294, 2), (196, 250, 0)]  # hill 3  (patrol lo, patrol hi, ledge level)
NEST_SIZE = 3
COIN = "$"
COIN_TWINKLE_PERIOD = 30.0  # level 1: each dollar twinkles briefly this often
BIRD_FLOCKS = {1: [(28.0, 14.0, 4.0, GROUND - 17, -1)],
               4: [(24.0, 13.0, 0.0, GROUND - 18, -1), (31.0, 15.0, 9.0, GROUND - 13, 1)]}  # (every s, crossing s, offset, row, direction)
C_BIRD = "90"
PATCH_SIT_TIME = 1.2  # level 1: sitting on the springy patch this long drops her into the hidden chamber
CH_X0, CH_X1 = 24, 124  # the cavern under the grass: a room carved into the rock below level 1's ground
CH_TOP, CH_FLOOR = GROUND + 3, GROUND + 22
CH_LEDGES = [(CH_X0, CH_X1, CH_FLOOR),
             (26, 38, CH_FLOOR - 4), (32, 44, CH_FLOOR - 8), (26, 38, CH_FLOOR - 12), (32, 44, CH_FLOOR - 16), (26, 38, CH_FLOOR - 20),  # the stairs back up
             (70, 84, CH_FLOOR - 3), (82, 96, CH_FLOOR - 6), (94, 108, CH_FLOOR - 9), (104, 120, CH_FLOOR - 12)]
CH_GEM = (112, CH_FLOOR - 13)
# level 4's secret: invisible ledges that appear when she lands on them, zigzagging up past the top of the screen to a pink gem
SECRET4_DX, SECRET4_DY = 143, -6  # the secret sits above the top ledge of the third hill (244..262, level 5)
HIDDEN4 = [(x0 + SECRET4_DX, x1 + SECRET4_DX, floor + SECRET4_DY) for x0, x1, floor in
           [(90, 103, GROUND - 12), (74, 94, GROUND - 16), (88, 108, GROUND - 20), (74, 94, GROUND - 24),
            (88, 108, GROUND - 28), (74, 94, GROUND - 32), (88, 108, GROUND - 36)]]
# level 5's secret: jump from the left end of the low sliding ledge while it is near its leftmost position
HIDDEN5 = [(36, 52, GROUND - 13), (46, 60, GROUND - 17), (30, 46, GROUND - 21), (44, 58, GROUND - 25),
           (30, 46, GROUND - 29), (44, 58, GROUND - 33), (30, 46, GROUND - 37)]
# level 8's secret: a lone ledge half way up the tower, far out to the right. It can only be reached by walking off a high ledge
# and drifting down onto it (she covers about one column sideways for every two rows she falls). Jumping from its right end reveals a climb.
LONE8 = (106, 126, GROUND - 90)
HIDDEN8 = [(120, 134, GROUND - 94), (126, 140, GROUND - 98), (120, 134, GROUND - 102), (126, 140, GROUND - 106),
           (120, 134, GROUND - 110), (126, 140, GROUND - 114), (120, 134, GROUND - 118)]  # to the right, so a falling duck lands on the lone ledge first
# level 10's secret: when the rain starts, a cloud drifts back and forth beside the tower; riding it to the right end reaches a pink gem
CLOUD_DROP = 6  # rows the water falls when she first lands on the cloud
CLOUD_CFG = {"w": 10, "lo": 86, "hi": 128, "step": MOVER_STEP / 2}
CLOUD_FLOOR = GROUND - 51
# level 2's secret: a full chorus of quacks (MAX_QUACKS in one breath) on top of a hill makes a hidden ledge appear (hill 1's above hill 1, hill 2's above that one); once both are there the gem shows
LEVEL2_TOPS = [(50, 70, GROUND - 3 * STEP), (140, 160, GROUND - 3 * STEP)]  # the top ledge of each hill: where she has to quack
HIDDEN2 = [(56, 68, GROUND - 4 * STEP), (58, 70, GROUND - 5 * STEP)]  # the ledges that appear: one above hill 1's top, and a second stacked above it (the second chorus, on hill 2, builds it)
# level 3's secret: having MITES_FOR_SECRET mites stunned at the same moment makes a staircase of hidden ledges appear above hill 2, leading up to the gem
MITES_FOR_SECRET = 6
HIDDEN3 = [(x0 + LEVEL3_SHIFT, x1 + LEVEL3_SHIFT, y) for x0, x1, y in [(186, 200, GROUND - 4 * STEP), (196, 210, GROUND - 5 * STEP), (186, 200, GROUND - 6 * STEP), (196, 210, GROUND - 7 * STEP), (186, 200, GROUND - 8 * STEP)]]  # a zigzag up from hill 2's top ledge
REVEALED_LEVELS = (2, 3)  # levels whose hidden ledges are added when the secret is triggered, not at the start
HIDDEN_LEDGES = {2: HIDDEN2, 3: HIDDEN3, 4: HIDDEN4, 5: HIDDEN5, 8: HIDDEN8}
# level 7's secret: drowning while standing on the grass sinks her into a cavern where a mermaid revives her and a hidden room opens
MERMAID_LEVEL, MERMAID_X, MERMAID_REVIVE, ROOM_OPEN_SPEED, MERMAID_FLOAT = 7, 40, 2.5, 50.0, 3.5  # (mermaid column, seconds of revival, columns/s the rock opens)
MER_X0, MER_X1, ROOM_X0 = 4, SCREEN_W - 4, 52
MER_LEDGES = [(MER_X0, MER_X1, CH_FLOOR), (6, 18, CH_FLOOR - 4), (12, 24, CH_FLOOR - 8), (6, 18, CH_FLOOR - 12), (12, 24, CH_FLOOR - 16),
              (6, 18, CH_FLOOR - 20)]  # the floor and the stairs back up
MER_ROOM_LEDGES = [(54, 62, CH_FLOOR - 3), (60, 68, CH_FLOOR - 6), (66, 74, CH_FLOOR - 9)]  # the hidden room's steps, added when it opens
MER_GEM = (70, CH_FLOOR - 10)
# level 6's secret: walking to the right end of the summit ledge makes a mushroom sprout; it bounces her (with Up held) up to a pink gem
SECRET_TRIGGER = 95  # her centre column on the summit ledge that makes the mushroom appear
SECRET_MUSHROOM = (88, SUMMIT)
SECRET_GEM = (90, SUMMIT - 18)
MERMAID_SAYS = "Be careful little duck!"
MERMAID = [" .-. ", "(o.o)", " )~( ", "/~~~\\"]
GEM_SPOTS = {1: CH_GEM, 3: (193 + LEVEL3_SHIFT, GROUND - 8 * STEP - 1), 2: (64, GROUND - 5 * STEP - 1), 4: (98 + SECRET4_DX, GROUND - 37 + SECRET4_DY), 5: (38, GROUND - 38), 8: (130, GROUND - 119), 10: (134, CLOUD_FLOOR - 2), MERMAID_LEVEL: MER_GEM, 6: SECRET_GEM}
HINT_LEDGE4 = (244, 262, GROUND - 5 * STEP)  # the top ledge whose left end glows faintly while she stands on it
HINT_LEDGES = {4: (HINT_LEDGE4, "left"), 8: (LONE8, "right")}  # the ledge that hints at the hidden ledge, and which end glows
GEM_HINTS = {
    1: "Lay down, down and rest where the grass is most comfy.",
    2: "Shout from the top of each hill as long as your breath will last, then climb as high as the echoes.",
    3: "When enough little ones have been put to sleep, a stair will rise above the second hill.",
    4: "Not every step can be seen; take a leap of faith where the left edge gleams.",
    5: "Ride with the beetle's neighbour, then leap from where it begins.",
    6: "The top is not the end. Go right and the ground will answer.",
    7: "Sometimes the deep is kind. Take a last breath where the grass ends.",
    8: "Step off the edge, far from the climb, and a hidden ledge will catch you.",
    10: "When the sky weeps, something floats that is meant to be ridden.",
}
GEM_APPEARS_AFTER = 4  # level 4's gem only shows up once this many hidden ledges have been found
REVEAL_SPEED = 40.0  # columns a second that a hidden ledge spreads out from where she landed
GEM, C_GEM = "\u25c6", "1;95"
SQUISH_PATCH, SQUISH_TIME = (46, 60), 0.6  # level 1: a patch of springy grass in the middle
COINS_FOR_ACHIEVEMENT = 10
START_FULLNESS = 80.0
START_HAPPINESS = 60.0
HUNGER_RATE = 0.4  # fullness points lost per second
FOOD_VALUE = 12.0  # fullness gained per crumb
HUNGRY_BELOW = 25.0
RUN_DRAIN = 25.0  # stamina lost per second while running
GLIDE_DRAIN = 12.0  # stamina lost per second while gliding
STAMINA_REGEN = 12.0
TIRED_UNTIL = 25.0  # after running out, no running until stamina recovers this far
STAMINA_PER_CRUMB = 20.0
GLIDE_DELAY = 0.14  # seconds per row while gliding (falling is much faster)
BREATH_DRAIN = 10.0  # air lost per second while diving
BREATH_REGEN = 35.0
BREATH_MIN = 25.0  # can't dive again until she has caught her breath
SINK_DELAY = 0.18  # seconds per row sinking
RISE_SWIM_DELAY = 0.12
SWIM_SLOWDOWN = 3.0  # underwater strokes are slower than walking
BLACKOUT_PENALTY = 8.0
MAX_LIVES = 3
TANK_AIR_FACTOR = 3.0
PEA_COOLDOWN = 0.35
BEETLE_COUNT = 22
BEETLE_HP = 3
MAX_HEALTH = 50.0
BEETLE_DAMAGE = 20.0
BAT_DAMAGE = 12.0
BAT_STEP = 0.12  # seconds per column
BAT_AMPLITUDE = 3  # rows; its long, slow wave lets a crouching duck pass underneath
BAT_WAVELENGTH = 56  # columns
ENEMY_RESPAWN = 60.0
KILL_AMMO = 2
HIT_INVULN = 1.5
REGEN_PER_SEC = 0.8
BEETLE_LEGS = ["/| |\\", "\\| |/"]
BEETLE_TOP = [" ,^, ", "(o o)"]
BEETLE_HIT_TIME = 0.3  # seconds a beetle flashes after a pea hits it
BEETLE_HURT_EYES = ["(o o)", "(o x)", "(x x)"]  # by hit points lost: it stays battered
BEETLE_FLINCH = "(>_<)"
HEDGEHOG_HP = ARMADILLO_HP = 2
HEDGEHOG_WALK_STEP, HEDGEHOG_ROLL_STEP = 0.25, 0.07  # seconds per column: it rolls much faster than it walks
HEDGEHOG_CURL_TIME = 0.7  # warning at the top of its slope before it rolls
HEDGEHOG_BALL_TIME = 2.0  # it stays curled at the bottom, then uncurls
HEDGEHOG_WALK = [" ^^^ ", "(^^^o", " d d "]  # facing right; mirrored for left
HEDGEHOG_CURLING = [" ^^^ ", "(^^^)", " d d "]
HEDGEHOG_BALL = [[" \\|/ ", "-(@)-", " /|\\ "], [" /|\\ ", "-(@)-", " \\|/ "]]
ARMADILLO = [[" ___ ", "(###>", " d d "], [" ___ ", "(###>", " b b "]]  # facing right; mirrored for left
ARMADILLO_HIT_DAMAGE = 10.0  # a pea that bounced off its armor hurts the duck it comes back to
C_HEDGEHOG, C_ARMADILLO, C_BOUNCED = "38;5;137", "97", "91"
BAT_FRAMES = ["^(o)^", "v(o)v"]
C_BEETLE = "91"
C_BAT = "35"
PACK_AMMO = 8
MAX_AMMO = 99
PACK_RESPAWN = 90.0
PEA_RANGE = 40
PEA_STEP = 0.02
C_ITEM = "1;95"
C_PEA = "92"
UMBRELLA_ART = ["    ___    ", "  .'   '.  ", " /_._|_._\\ ", "     |     ", "     J     "]
PEASHOOTER_ART = ["            ", "   _______  ", "==|_______>  o", "  /_/       ", " (_)        "]
TANK_ART = ["    _[]_    ", "   /    \\   ", "  | O2   |  ", "  |      |  ", "   \\____/   "]
UMBRELLA_GLIDE = [" .-'''-. ", ["/_._|_._\\", "/__.|.__\\", "/._.|._.\\"], "    |    "]
ITEMS = {  # key: (name, tag drawn in the world, art, how it works)
    "umbrella": ("Umbrella", "[U]", UMBRELLA_ART, "Hold Up while falling to glide"),
    "peashooter": ("Pea-shooter", "[P]", PEASHOOTER_ART, "Press Space to shoot peas"),
    "tank": ("Oxygen tank", "[O]", TANK_ART, "Triple the air when diving"),
}
C_ROCK = "90"
C_AIR = "96"
PEARL_RESPAWN = 120.0
PEARL_HAPPINESS = 6.0
PEARL = "o"
C_PEARL = "1;97"
SLOW_BELOW = 10.0  # too hungry to walk at full speed
COIN_HAPPINESS = 4.0
QUACK_HAPPINESS = 1.5
HAPPY_AT = 90.0
TOAST_TIME = 3.5
C_ACHIEVEMENT = "1;93"
C_GOLD = "1;38;5;220"
RAINBOW = ["91", "38;5;208", "93", "92", "96", "94", "95"]
CELEBRATE_TIME = 12.0  # the "all achievements" party
BURST_LIFE = 1.4
SHAKE_TIME = 1.2
COIN_SOUND = "/System/Library/Sounds/Tink.aiff"
FANFARE_SOUND = "/System/Library/Sounds/Hero.aiff"
BANNER = ["ALL ACHIEVEMENTS UNLOCKED", "LEGENDARY DUCK"]

# ---- input --------------------------------------------------------------------------------
FIRST_REPEAT_DELAY = 0.8  # fallback: key-repeat starts after an initial delay
REPEAT_GAP = 0.25
HOLD_KEYS = {"left", "right", "space", "up"}
KITTY_EVENT = re.compile(rb"\x1b\[(\d*)(?:;(\d*)(?::(\d+))?)?(?:;[\d:]+)?([uABCD])")
ARROW = re.compile(rb"\x1b[\[O](?:1;(\d+))?([ABCD])")
ARROW_NAMES = {b"A": "up", b"B": "down", b"C": "right", b"D": "left"}
PLAIN_KEYS = {32: "space", 116: "egg", 102: "feed", 109: "mute", 119: "weather", 104: "hat", 80: "predator", 112: "pause",
              103: "friend", 105: "inventory", 115: "shoot", 97: "achievements", 84: "testmenu", 13: "enter", 10: "enter", 121: "yes", 110: "no", 113: "quit", 120: "quit", 114: "restart", 49: "level1", 50: "level2", 51: "level3", 52: "level4", 53: "level5", 54: "level6", 55: "level7", 56: "level8", 57: "level9", 48: "level10", 45: "level11", 61: "level12", 92: "level13", 93: "level14"}
KITTY_KEYS = {**PLAIN_KEYS, 27: "quit", 57441: "shift", 57447: "shift"}

BLANK = (" ", None)


def clamp(value, low, high):
    return min(high, max(low, value))


def sprite(lines, facing):
    width = max(len(line) for line in lines)
    lines = [line.ljust(width) for line in lines]
    if facing < 0:
        lines = [line[::-1].translate(MIRROR) for line in lines]
    return lines


# Quack and sparkle positions use "u": distance ahead of the duck's left edge when facing right,
# mirrored when facing left.
def quack_pos(i):
    return QUACK_U + i * QUACK_SPACING, BEAK_ROW + round(WAVE_AMPLITUDE * math.sin(i * math.pi / 2))


def new_sparkles(i):
    u0, y0 = quack_pos(i)
    sparkles = []
    for _ in range(3):
        u = u0 + random.randint(-2, 7)
        y = y0 + random.randint(-2, 2)
        if y == y0 and u0 - 1 <= u <= u0 + 6:
            y += random.choice((-1, 1))  # keep clear of the quack text
        sparkles.append((u, clamp(y, -2, DUCK_H - 1), random.choice(BUBBLES + STARS)))
    return sparkles


def quack_count(held):
    return int(held / QUACK_INTERVAL) % MAX_QUACKS + 1  # wraps after the last quack


def duck_lines(quacking, facing, step, eye="o", preen=0, feet=True, shades=False):
    beak = "v" if preen else (">>" if quacking else ">")
    wing = "~" if preen == 2 else "_"
    face = "==" if shades else " " + eye
    body = ["    __", f"___({face}){beak}", f"\\ <{wing}. )", " `---'"]
    if feet:
        body.append(FEET[step % 2])
    return sprite([line.ljust(DUCK_W) for line in body], facing)


def new_chick(x, facing, now, fy=GROUND):
    return {
        "x": x, "fy": fy, "facing": facing, "hop": False, "next": now, "born": now, "bonus": 0.0,
        "stage": "chick", "trait": random.choice(("loyal", "adventurous")), "mode": "follow",
        "target": 0, "mode_until": 0.0, "next_adventure": now + random.uniform(6, 12),
        "next_peep": now + random.uniform(3, 8), "peep_until": 0.0, "peep_text": "peep!",
    }


def new_adult(x, facing, now, fy=GROUND):
    return {"x": x, "fy": fy, "facing": facing, "next": now, "target": None,
            "pause_until": now + random.uniform(1, 3)}


def is_water(x):
    return any(p <= x < p + POND_W for p in PONDS)


def build_caves():
    """Water ('w') and air-pocket ('a') cells under each lake; anything else in the cave area is rock."""
    cave, pearls = {}, set()

    def carve(x0, x1, y0, y1, kind="w"):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                cave[(x, y)] = kind

    for i, p in enumerate(PONDS):
        rng = random.Random(500 + i)
        carve(p, p + POND_W - 1, GROUND, GROUND + 5)
        for y in range(GROUND + 6, GROUND + LAKE_DEPTH):  # the basin narrows into a shaft
            t = min(1.0, (y - GROUND - 5) / 6)
            carve(p + round(16 * t), p + POND_W - 1 - round(16 * t), y, y)
        pearls.add((p + POND_W // 2, GROUND + LAKE_DEPTH - 2))
        side = rng.choice((-1, 1))
        for k, depth in enumerate((10, 17, 24)):  # a winding tunnel and chamber off the shaft at each depth
            y, x, off = GROUND + depth, (p + 23 if side > 0 else p + 16), 0
            for _ in range(rng.randint(20, 26)):
                x += side
                off = clamp(off + rng.choice((-1, 0, 0, 1)), -1, 1)
                carve(x, x, y + off, y + off + 3)
            cx, cy, rx, ry = x + side * 4, y + off + 1, 6, 4
            for dx in range(-rx, rx + 1):
                for dy in range(-ry, ry + 1):
                    if (dx / rx) ** 2 + (dy / ry) ** 2 <= 1:
                        cave[(cx + dx, cy + dy)] = "w"
            if k < 2:  # the deepest chamber has no air pocket
                for dx in range(-3, 4):
                    top = min(yy for (xx, yy), kind in cave.items() if xx == cx + dx and cy - ry <= yy <= cy + ry)
                    carve(cx + dx, cx + dx, top, top + 1, "a")
            pearls |= {(cx - 3, cy + 2), (cx + 3, cy + 2)}
            if k == 2:
                pearls.add((cx, cy + 3))
            side = -side
    return cave, pearls


def cave_cell(x, y):
    if y < GROUND:
        return "a" if is_water(x) else None
    return CAVE.get((x, y))


def build_platforms():
    """Staircase-like towers of one-way ledges; each ledge overlaps the one below it."""
    rng = random.Random(321)
    platforms = []
    start = 40
    while start < WORLD_W - 30:
        for pond_x in PONDS:
            if pond_x - 20 <= start <= pond_x + POND_W + 4:
                start = pond_x + POND_W + 6
        direction = rng.choice((-1, 1))
        prev = None
        for level in range(1, rng.choice((2, 3, 4, 5, 6, 7, 9, MAX_LEVEL)) + 1):
            width = rng.randint(12, 18)
            if prev is None:
                x0 = start
            else:
                if rng.random() < 0.45:
                    direction = -direction
                for _ in range(2):  # flip once if the ledge would leave the world
                    x0 = prev[1] - PLATFORM_OVERLAP + 1 if direction > 0 else prev[0] + PLATFORM_OVERLAP - width
                    if 2 <= x0 and x0 + width < WORLD_W - 2:
                        break
                    direction = -direction
            if x0 < 2 or x0 + width >= WORLD_W - 2:
                break
            prev = (x0, x0 + width - 1)
            platforms.append((prev[0], prev[1], GROUND - STEP * level))
        start += 30 + rng.randint(0, 10)
    return platforms


def place_packs(count=None):
    spots = []
    if count is None:  # a full set; one pack is always near the start, next to the pea-shooter
        count = PACK_TOTAL
        if not count:
            return spots
        if EASY_SPOTS:
            spots.append(EASY_SPOTS["pack"])
        else:
            x0, x1, floor = START_LEDGES[1]
            spots.append(((x0 + x1) // 2, floor - 1))
        count -= 1
    for x0, x1, floor in random.sample(PLATFORMS, min(count, len(PLATFORMS))):
        spots.append((random.randint(x0 + 1, x1 - 1), floor - 1))
    return spots


def place_items(have):
    """Puts each item we don't own yet on its own random platform: {key: (x, y)}."""
    missing = [k for k in LEVEL_ITEMS if k not in have]
    spots = {}
    if "peashooter" in missing:  # always within reach of the start
        if EASY_SPOTS:
            spots["peashooter"] = EASY_SPOTS["peashooter"]
        else:
            x0, x1, floor = START_LEDGES[0]
            spots["peashooter"] = ((x0 + x1) // 2, floor - 1)
        missing.remove("peashooter")
    for key in [k for k in missing if EASY_SPOTS and k in EASY_SPOTS]:
        spots[key] = EASY_SPOTS[key]
        missing.remove(key)
    others = [p for p in PLATFORMS if p not in START_LEDGES]
    for key, (x0, x1, floor) in zip(missing, random.sample(others, len(missing))):
        spots[key] = (random.randint(x0 + 1, x1 - 1), floor - 1)
    return spots


BUCKET = 40


def support(x, row):
    """The feet row of the nearest floor at or below `row` under column x."""
    best = GROUND if row <= GROUND else WORLD_H  # below the grass only the cavern's ledges are floors
    for x0, x1, floor in PLATFORMS_BY_X[x // BUCKET] if 0 <= x < WORLD_W else ():
        if x0 <= x <= x1 and row <= floor < best:
            best = floor
    return best


def add_platform(p):
    for b in range(p[0] // BUCKET, p[1] // BUCKET + 1):
        PLATFORMS_BY_X[b].append(p)


def move_platform(old, new):
    for b in range(old[0] // BUCKET, old[1] // BUCKET + 1):
        PLATFORMS_BY_X[b].remove(old)
    add_platform(new)


def build_scenery():
    rng = random.Random(11)
    pond = {x for pond_x in PONDS for x in range(pond_x - 8, pond_x + POND_W + 4)}
    trees = [base + rng.randint(-6, 6) for base in range(15, WORLD_W - 8, 23)]
    low_ledges = [(x0, x1) for x0, x1, floor in PLATFORMS if floor == GROUND - STEP]
    trees = [x for x in trees if x not in pond and not any(x <= x1 and x + 6 >= x0 for x0, x1 in low_ledges)]
    flowers = [(x, rng.choice(C_FLOWERS)) for x in rng.sample(range(WORLD_W), WORLD_W // 5) if x not in pond]
    return trees, flowers


def configure_level(level):
    """Rebinds the module-level map data (world size, ledges, lakes, coins...) for the given game level."""
    global WORLD_W, PONDS, PLATFORMS, START_LEDGES, PLATFORMS_BY_X, TREES, FLOWERS, COINS, LEDGE_LEVEL
    global CAVE, PEARL_SPOTS, LEVEL_ITEMS, PACK_TOTAL, EASY_SPOTS, MOVERS, MUSHROOMS
    if level == 1:
        WORLD_W, PONDS = SCREEN_W, []
        PLATFORMS = [(x0, x1, GROUND - STEP * n) for x0, x1, n in LEVEL1_LEDGES]
        LEVEL_ITEMS, PACK_TOTAL, EASY_SPOTS = [], 0, None
    elif level == 2:
        WORLD_W, PONDS = LEVEL2_W, []
        PLATFORMS = [(x0, x1, GROUND - STEP * n) for x0, x1, n in LEVEL2_LEDGES]
        LEVEL_ITEMS, PACK_TOTAL, EASY_SPOTS = [], 0, None
    elif level == 3:
        WORLD_W, PONDS = LEVEL3_W, []
        PLATFORMS = [(x0, x1, GROUND - STEP * n) for x0, x1, n in LEVEL3_LEDGES]
        LEVEL_ITEMS, PACK_TOTAL = ["peashooter"], 8
        EASY_SPOTS = {"peashooter": LEVEL3_SHOOTER, "pack": LEVEL3_PACK}
    elif level == 5:
        WORLD_W, PONDS = LEVEL5_W, []
        PLATFORMS = [(x0, x1, GROUND - STEP * n) for x0, x1, n in LEVEL5_LEDGES]
        LEVEL_ITEMS, PACK_TOTAL = ["peashooter"], 5
        EASY_SPOTS = {"peashooter": (98, GROUND - 2 * STEP - 1), "pack": (30, GROUND - 1)}  # the pea-shooter needs the moving ledge
    elif level == 4:
        WORLD_W, PONDS = LEVEL4_W, []
        PLATFORMS = [(x0, x1, GROUND - STEP * n) for x0, x1, n in LEVEL4_LEDGES]
        LEVEL_ITEMS, PACK_TOTAL = ["peashooter"], 10
        EASY_SPOTS = {"peashooter": LEVEL4_SHOOTER, "pack": LEVEL4_PACK}
    elif level == 6:
        WORLD_W, PONDS = SCREEN_W, []
        moved = {GROUND - STEP * spec["n"] for spec in LEVEL6_MOVERS}
        PLATFORMS = [p for p in LEVEL6_LEDGES if p[2] not in moved]
        LEVEL_ITEMS, PACK_TOTAL = ["peashooter"], 4
        EASY_SPOTS = {"peashooter": LEVEL6_SHOOTER, "pack": LEVEL6_PACK}  # the shooter waits a third of the way up, past the mites
    elif level in ICE_LEVELS or level == HEDGE_LEVEL:
        WORLD_W, PONDS = SCREEN_W, []
        cfg = ICE_CONFIGS[level]
        PLATFORMS = list(cfg["ledges"])
        LEVEL_ITEMS, PACK_TOTAL, EASY_SPOTS = cfg["items"], cfg["packs"], cfg["easy_spots"]
    elif level == GRAND_LEVEL:
        WORLD_W, PONDS = GRAND_W, []
        PLATFORMS = list(GRAND["ledges"])
        LEVEL_ITEMS, PACK_TOTAL, EASY_SPOTS = GRAND["items"], GRAND["packs"], GRAND["easy_spots"]
    elif level in FLOODS:
        WORLD_W, PONDS = SCREEN_W, []
        cfg = FLOODS[level]
        PLATFORMS = [p for p in cfg["ledges"] if p[2] not in (LEVEL8_MOVER_ROWS if level == 8 else ())]  # sliding ledges replace some
        LEVEL_ITEMS, PACK_TOTAL, EASY_SPOTS = cfg.get("items", []), cfg.get("packs", 0), cfg.get("easy_spots")
    else:
        WORLD_W, PONDS = 2400, [150, 1000, 1800]  # the lakes: there are always at least three
        PLATFORMS = build_platforms()
        LEVEL_ITEMS, PACK_TOTAL = list(ITEMS), 14
        EASY_SPOTS = None
    MOVERS = LEVEL5_MOVERS if level == 5 else LEVEL6_MOVERS if level == 6 else LEVEL8_MOVERS if level == 8 else HEDGE["movers"] if level == HEDGE_LEVEL else ICE2["movers"] if level == 12 else GRAND_MOVERS if level == GRAND_LEVEL else []
    MUSHROOMS = list(LEVEL6_MUSHROOMS) if level == 6 else LEVEL8_MUSHROOMS if level == 8 else HEDGE["mushrooms"] if level == HEDGE_LEVEL else ICE2["mushrooms"] if level == 12 else GRAND_MUSHROOMS if level == GRAND_LEVEL else []
    CAVE, PEARL_SPOTS = build_caves()
    START_LEDGES = sorted(p for p in PLATFORMS if p[2] == GROUND - STEP)[:2]  # the first low ledges next to the duck's start
    PLATFORMS_BY_X = [[] for _ in range(WORLD_W // BUCKET + 2)]  # ledges grouped by x, for fast lookups
    for p in PLATFORMS:
        for b in range(p[0] // BUCKET, p[1] // BUCKET + 1):
            PLATFORMS_BY_X[b].append(p)
    for m in MOVERS:  # moving ledges are not in PLATFORMS (no coin, no items), only in the lookup buckets
        add_platform((m["lo"], m["lo"] + m["w"] - 1, GROUND - STEP * m["n"]))
    TREES, FLOWERS = ([], []) if level in ICE_LEVELS else build_scenery()  # nothing grows on the ice
    if level == GRAND_LEVEL:
        TREES, FLOWERS = [x for x in TREES if x >= GRAND_ICE_X + 3], [f for f in FLOWERS if f[0] >= GRAND_ICE_X]
    COINS = [((x0 + x1) // 2, floor - 1) for x0, x1, floor in PLATFORMS]  # one hovering over each ledge
    if level == 1:
        COINS += LEVEL1_COINS
    elif level == 2:
        COINS += LEVEL2_COINS
    elif level == 3:
        COINS += LEVEL3_COINS
    elif level == 4:
        COINS += LEVEL4_COINS
    elif level == 5:
        COINS += LEVEL5_COINS
    elif level == 6:
        COINS += LEVEL6_COINS
    elif level in ICE_CONFIGS:
        COINS += ICE_CONFIGS[level]["coins"]
    elif level in FLOODS:
        COINS += FLOODS[level]["coins"]
    LEDGE_LEVEL = [0] * WORLD_W  # highest ledge level per column, for the mini-map
    for x0, x1, floor in PLATFORMS:
        for x in range(x0, x1 + 1):
            LEDGE_LEVEL[x] = max(LEDGE_LEVEL[x], (GROUND - floor) // STEP)


configure_level(LAST_LEVEL)


class World:
    def __init__(self, now, level=1, hat=None, muted=False, gems=0):
        configure_level(level)
        if level == 1:
            for p in CH_LEDGES:
                add_platform(p)
        if level == MERMAID_LEVEL:
            for p in MER_LEDGES:
                add_platform(p)
        self.secret_shown = False  # level 6: the summit mushroom has sprouted
        self.mermaid_cave = self.mermaid_pending = False  # level 7: she sank through the grass into the mermaid's cavern
        self.float_t0 = self.float_x0 = None  # level 7: the drowned duck drifts down to the mermaid
        self.mermaid_t0 = self.room_open = None  # when she landed there, and when the hidden room opened
        if level == 8:
            add_platform(LONE8)
        self.hidden = HIDDEN_LEDGES.get(level, [])
        for p in self.hidden:
            if level not in REVEALED_LEVELS:  # their ledges only appear once the secret is triggered
                add_platform(p)
        self.max_stunned = 0  # most mites stunned at the same moment (not shown)
        self.revealed = {}  # hidden ledge -> (time, column) it appeared
        self.gems = self.gems_at_start = gems  # pink gems carry from level to level
        self.gem_taken = False
        self.level = level
        self.achievements = LEVEL_ACHIEVEMENTS[level]
        self.level_done = None  # when every achievement of this level was unlocked
        self.kills = 0
        self.beetle_target = BEETLE_COUNT if level == LAST_LEVEL else 0
        self.view_w = 80
        self.view_h = DEFAULT_VIEW_H
        self.x = {1: LEVEL1_START_X, 2: LEVEL2_START_X, 3: LEVEL3_START_X, 4: LEVEL4_START_X, 5: LEVEL5_START_X, 6: LEVEL6_START_X, HEDGE_LEVEL: HEDGE["start_x"], 11: ICE["start_x"], 12: ICE2["start_x"], GRAND_LEVEL: GRAND["start_x"]}.get(level) or FLOODS.get(level, {}).get("start_x", 30)
        self.feet = GROUND  # row of the duck's feet
        self.floor = GROUND  # row of the floor she last stood on
        self.airborne = False
        self.air_phase = None
        self.air_n = 0
        self.running = False  # shift held
        self.run_active = False
        self.ice = level in ICE_LEVELS  # she slides: see update_ice
        self.vel = 0.0  # ice: signed speed in columns per second
        self.slide_x = 0.0  # ice: the part of a column she has moved but not yet stepped
        self.slide_t = now
        self.tired = False
        self.stamina = 100.0
        self.up_held = False
        self.rise_rows = JUMP_ROWS
        self.plunged = {}  # mushroom (x0, floor) -> when she last landed on it
        self.wind = None  # the current gust: {dir, start, end, push}
        self.next_gust = now + 5.0 if level in (6, 8, GRAND_LEVEL) else float("inf")
        self.flood_cfg = FLOODS.get(level)
        self.flood = GROUND + 1 if self.flood_cfg else None  # row of the rising water's surface (levels 7 and 10)
        self.fish_t = now
        self.school = [{"x": random.uniform(0, WORLD_W - 3), "y": random.randint(FLOODS[level]["top"] + 2, GROUND - 2),
                        "dir": random.choice((-1, 1)), "speed": random.uniform(3.0, 7.0)} for _ in range(FLOOD_FISH)] if level in FLOODS else []
        self.drowned = None  # when she drowned: the dying animation, then a prompt to restart
        self.died = False  # level 3: knocked out, waiting for space to restart
        self.drown_t0 = None  # when her head went under the flood
        self.rain_t0 = None  # when the rain (and the water's acceleration) started
        self.surge_t0 = None  # when she passed the surge ledge and the water sped up again
        self.cloud_boarded, self.cloud_last, self.flood_drop = False, None, 0
        self.flood_t0 = None  # when the water started rising: as soon as she lands on the first ledge
        self.gliding = False
        self.breath = 100.0
        self.lives = MAX_LIVES
        self.inventory = set()
        self.item_spots = place_items(self.inventory)
        self.show_inventory = False
        self.peas = []
        self.next_shot = 0.0
        self.ammo = 0
        self.health = MAX_HEALTH
        self.invuln_until = 0.0
        self.enemies = []
        self.next_bat = 0.0
        self.enemy_respawns = []
        self.last_enemy_tick = 0.0
        self.packs = place_packs()
        self.pack_taken = []  # respawn times of collected packs
        self.game_over = False
        self.depth = 0  # rows below the water surface while swimming
        self.dive_dir = 0  # 1 sinking, -1 rising, 0 holding
        self.depth_next = 0.0
        self.pearls = set(PEARL_SPOTS)
        self.pearl_taken = {}
        self.pearls_found = 0
        self.air_next = 0.0
        self.cam = 0
        self.cam_y = SURFACE_H - self.view_h  # start looking at the ground floor
        self.facing = 1
        self.dirs = []  # held direction keys, most recent last
        self.step = 0
        self.next_step = 0.0
        self.walking = False
        self.sitting = False
        self.sit_start = 0.0
        self.egg_rolled = False
        self.quack_start = None
        self.shown = 0
        self.quack_texts = []
        self.sparkles = []
        self.behavior = None  # (name, start, duration)
        self.next_idle = now + random.uniform(*IDLE_GAP)
        self.thought = ("", 0.0)
        self.next_thought = now + random.uniform(*THOUGHT_GAP)
        self.survival = level == LAST_LEVEL  # hunger, mood and hats only exist in the full game
        self.hat = hat if self.survival else None
        self.last_input = now
        self.nom_until = 0.0
        self.was_in_pond = False
        self.was_diving = False
        self.next_bubble = 0.0

        self.eggs = []
        self.flying = None  # (start time, origin x, direction)
        self.flying_pos = None
        self.young = []
        self.adults = []
        self.crumbs = []
        self.ripples = []
        self.splashes = []
        self.friends = []
        self.next_friend = now + random.uniform(*FRIEND_EVERY)

        self.weather = "clear"
        self.next_weather = now + random.uniform(*WEATHER_EVERY)
        if level in FLOODS:
            self.next_weather = float("inf")  # the only weather is the flood's rain
        if self.ice:
            self.weather, self.next_weather = "snow", float("inf")  # it always snows on the rink
        self.particles = []  # screen-space [x, y]
        self.next_particle = now
        self.particle_tick = 0
        self.stars = [(random.random(), random.randrange(0, 5)) for _ in range(14)]

        self.muted = muted
        self.events = []
        self.unlocked = set()
        self.show_achievements = False
        self.confirm_quit = False
        self.quit_now = False
        self.paused = False
        self.goto_level = None  # set by the test menu
        self.movers = []
        self.confirm_restart = False
        self.restart_now = False
        self.test_menu = False  # undocumented: check achievements off by hand
        self.menu_cursor = 0
        self.toast = ("", 0.0)
        self.toast_queue = []
        self.celebrate_start = None
        self.golden = False  # the reward: a permanently golden duck
        self.bursts = []  # fireworks: (x, y, born, color)
        self.confetti = []
        self.next_burst = 0.0
        self.coins = set(COINS)
        self.predator = None
        self.next_predator = now + random.uniform(*PREDATOR_EVERY)
        self.notice = ("", 0.0)
        self.fullness = START_FULLNESS if self.survival else 100.0
        self.happiness = START_HAPPINESS
        self.last_needs = now
        self.hats_tried = set()
        self.friends_met = set()
        self.weathers_seen = set()
        if level == 1:
            self.next_predator = float("inf")  # the first level has no enemies at all
        if level in (5, 6, 8, HEDGE_LEVEL, 12, GRAND_LEVEL):
            for spec in MOVERS:
                lo, w, floor = spec["lo"], spec["w"], GROUND - STEP * spec["n"]
                m = {"x0": lo, "w": w, "floor": floor, "lo": lo, "hi": spec["hi"], "step": spec["step"], "dir": 1, "next": 0.0}
                self.movers.append(m)
                if spec.get("beetle"):
                    self.enemies.append({"kind": "beetle", "x": lo, "y": floor, "lo": lo, "hi": lo + w - ENEMY_W, "dir": 1,
                                         "hp": BEETLE_HP, "next": 0.0, "step": 0, "ride": m})
        for lo, hi, floor in (ICE_CONFIGS.get(level) or self.flood_cfg or {}).get("beetles", ()):
            self.enemies.append({"kind": "beetle", "x": lo, "y": floor, "lo": lo, "hi": hi, "dir": 1,
                                 "hp": BEETLE_HP, "next": 0.0, "step": 0})
        for i, (lo, hi, floor, up) in enumerate(ICE_CONFIGS.get(level, {}).get("hedgehogs", ())):
            self.enemies.append({"kind": "hedgehog", "x": lo if up > 0 else hi, "y": floor, "lo": lo, "hi": hi, "dir": up, "up": up,
                                 "hp": HEDGEHOG_HP, "next": now + 1.0 + 0.7 * i, "step": 0, "state": "ball"})  # curled until its first walk
        for lo, hi, floor in ICE_CONFIGS.get(level, {}).get("mites", ()):
            self.enemies.append({"kind": "mite", "x": lo, "y": floor, "lo": lo, "hi": hi,
                                 "dir": 1, "hp": 1, "next": 0.0, "step": 0, "stun": 0.0})
        for lo, hi, floor in ICE_CONFIGS.get(level, {}).get("armadillos", ()):
            self.enemies.append({"kind": "armadillo", "x": lo, "y": floor, "lo": lo, "hi": hi, "dir": 1,
                                 "hp": ARMADILLO_HP, "next": 0.0, "step": 0})
        if level == 2:
            for lo, hi, n in LEVEL2_MITES:
                self.enemies.append({"kind": "mite", "x": lo, "y": GROUND - STEP * n, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": 1, "next": 0.0, "step": 0, "stun": 0.0})
        if level == 3:
            for lo, hi, n in LEVEL3_MITES:
                self.enemies.append({"kind": "mite", "x": lo, "y": GROUND - STEP * n, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": 1, "next": 0.0, "step": 0, "stun": 0.0})
        if level == 6:
            for lo, hi, floor in LEVEL6_MITES:
                self.enemies.append({"kind": "mite", "x": lo, "y": floor, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": 1, "next": 0.0, "step": 0, "stun": 0.0})
            for lo, hi, floor in LEVEL6_BEETLES:
                self.enemies.append({"kind": "beetle", "x": lo, "y": floor, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": BEETLE_HP, "next": 0.0, "step": 0})
        if level == 5:
            for lo, hi, n in LEVEL5_BEETLES:
                self.enemies.append({"kind": "beetle", "x": lo, "y": GROUND - STEP * n, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": BEETLE_HP, "next": 0.0, "step": 0})
        if level == 4:
            for lo, hi, n in LEVEL4_MITES:
                self.enemies.append({"kind": "mite", "x": lo, "y": GROUND - STEP * n, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": 1, "next": 0.0, "step": 0, "stun": 0.0})
            for lo, hi, n in LEVEL4_BEETLES:
                self.enemies.append({"kind": "beetle", "x": lo, "y": GROUND - STEP * n, "lo": lo, "hi": hi,
                                     "dir": 1, "hp": BEETLE_HP, "next": 0.0, "step": 0})
        self.enemy_total = len(self.enemies)
        self.toast_queue.append(LEVEL_INTROS[level])
        self.snap_camera()

    # ---- input ----------------------------------------------------------------------------
    def request_quit(self, now):
        # q / x / Esc close the achievements list first, then ask before quitting
        self.last_input = now
        if self.confirm_restart:
            self.confirm_restart = False
        elif self.test_menu:
            self.test_menu = False
        elif self.show_achievements:
            self.show_achievements = False
        elif self.show_inventory:
            self.show_inventory = False
        else:
            self.confirm_quit = not self.confirm_quit

    def handle(self, name, pressed, now):
        self.last_input = now
        if self.confirm_quit and pressed:  # key releases still get through below
            if name == "yes":
                self.quit_now = True
            elif name == "no":
                self.confirm_quit = False
            return
        if self.died:
            if pressed and name == "space":
                self.restart_now = True
            return
        if self.drowned is not None:  # the only thing left to do is restart
            if pressed and name == "space" and now - self.drowned >= DROWN_ANIM and not self.mermaid_pending:
                self.restart_now = True
            return
        if self.mermaid_cave and self.room_open is None:  # the mermaid is reviving her
            return
        if name == "pause" and pressed and not self.confirm_restart and not self.test_menu:
            self.paused = not self.paused
            if self.paused:
                self.dirs, self.quack_start, self.up_held, self.running = [], None, False, False
                self.shown, self.sparkles, self.quack_texts = 0, [], []
            return
        if self.paused:
            return
        if self.confirm_restart and pressed:
            if name == "yes":
                self.restart_now = True
            elif name == "no":
                self.confirm_restart = False
            return
        if self.test_menu and pressed:
            if name == "up":
                self.menu_cursor = (self.menu_cursor - 1) % len(self.achievements)
            elif name == "down":
                self.menu_cursor = (self.menu_cursor + 1) % len(self.achievements)
            elif name in ("space", "enter"):
                self.toggle_achievement(self.achievements[self.menu_cursor][0], now)
            elif name == "testmenu":
                self.test_menu = False
            elif name.startswith("level") and int(name[5:]) <= LAST_LEVEL:
                self.goto_level = int(name[5:])
            return
        if name == "restart" and pressed and not self.test_menu:
            self.confirm_restart = True
            self.show_achievements = self.show_inventory = False
            self.dirs, self.quack_start = [], None
            return
        if name == "testmenu" and pressed:
            self.test_menu, self.show_achievements = True, False
            return
        if name == "shift":
            self.running = pressed and self.level == LAST_LEVEL  # running is only for the final level
            return
        if name == "space":
            if pressed and "peashooter" in self.inventory and self.ammo > 0:
                if self.quack_start is None:
                    self.shoot(now)
            elif pressed and self.quack_start is None:
                self.quack_start = now
                self.unlock("quack", now)
            elif not pressed:
                self.quack_start, self.shown, self.sparkles, self.quack_texts = None, 0, [], []
        elif name in ("left", "right"):
            direction = 1 if name == "right" else -1
            if direction in self.dirs:
                self.dirs.remove(direction)
            if pressed:
                self.dirs.append(direction)
                self.facing = direction
            elif self.dirs:
                self.facing = self.dirs[-1]
        elif name == "up":
            was_held, self.up_held = self.up_held, pressed
            if not pressed or was_held:
                return
            if self.sitting and self.depth:
                self.dive_dir = 0 if self.dive_dir < 0 else -1  # swim up, or hold depth
            elif self.sitting and self.dive_dir:
                self.dive_dir = 0
            elif self.sitting:
                self.sitting = False
            elif not self.airborne:
                self.airborne, self.air_phase, self.air_n, self.air_next = True, "rise", 0, now
                self.rise_rows = JUMP_ROWS
        elif not pressed:
            return
        elif name == "down":
            if self.airborne:
                pass
            elif self.sitting and self.in_pond():  # float first, then dive; press again to hold depth
                if self.dive_dir > 0 and self.depth:
                    self.dive_dir = 0
                elif self.breath >= BREATH_MIN or self.depth:
                    self.dive_dir = 1
            elif not self.sitting:
                self.sitting, self.sit_start, self.egg_rolled = True, now, False
            elif self.feet != GROUND and support(self.center(), self.feet + 1) < WORLD_H:  # down again on a ledge: drop through it (not the cavern floor)
                self.sitting, self.feet = False, self.feet + 1
                self.unlock("skydiver", now)
                self.airborne, self.air_phase, self.air_n, self.air_next = True, "fall", 0, now
        elif name == "egg":  # undocumented testing shortcut
            self.lay_egg(now)
        elif name == "friend":  # undocumented testing shortcut
            self.spawn_friend(now)
        elif name == "predator":  # undocumented testing shortcut
            self.spawn_predator(now)
        elif name == "feed" and self.survival:
            self.feed(now)
        elif name == "hat" and self.survival:
            self.hat = HAT_ORDER[(HAT_ORDER.index(self.hat) + 1) % len(HAT_ORDER)]
            self.hats_tried.add(self.hat)
            if self.hats_tried >= {h for h in HAT_ORDER if h}:
                self.unlock("fashion", now)
        elif name == "mute":
            self.muted = not self.muted
        elif name == "achievements":
            self.show_achievements = not self.show_achievements
        elif name == "inventory":
            self.show_inventory = not self.show_inventory
        elif name == "shoot":
            self.shoot(now)
        elif name == "weather":
            self.set_weather(WEATHERS[(WEATHERS.index(self.weather) + 1) % len(WEATHERS)], now)

    def toggle_achievement(self, key, now):
        if key in self.unlocked:
            self.unlocked.discard(key)
            self.golden, self.celebrate_start = False, None
        else:
            self.unlock(key, now)

    def still_to_do(self):
        return "Still to do: " + ", ".join(f"{t} ({h})" for k, t, h in self.achievements if k not in self.unlocked)

    def unlock(self, key, now):
        title = next((title for k, title, _ in self.achievements if k == key), None)
        if title and key not in self.unlocked:
            self.unlocked.add(key)
            self.toast_queue.append(f"Achievement unlocked: {title}")
            if len(self.unlocked) == len(self.achievements) and self.level == LAST_LEVEL:
                self.celebrate_start, self.golden = now, True
                if not self.muted:
                    self.events.append("fanfare")

    def update_level_goals(self, now):
        if self.level < LAST_LEVEL and not self.coins:
            self.unlock("allcoins", now)
        if self.level == 6 and not self.airborne and self.feet <= SUMMIT:
            self.unlock("summit", now)
        if self.flood_cfg and not self.airborne and self.feet <= self.flood_cfg["summit"]:
            self.unlock("summit", now)
        if self.level in ICE_CONFIGS and not self.airborne and self.feet <= ICE_CONFIGS[self.level]["summit"]:
            self.unlock("summit", now)
        if self.level in SLAYER_LEVELS and self.kills >= self.enemy_total:
            self.unlock("slayer", now)
        if self.level < LAST_LEVEL and self.level_done is None and len(self.unlocked) == len(self.achievements):
            self.level_done = now
            if not self.muted:
                self.events.append("fanfare")

    def ready_for_next_level(self, now):
        return self.level_done is not None and now - self.level_done >= LEVEL_DONE_DELAY

    def save_state(self, now):
        young = [{"x": c["x"], "fy": c["fy"], "facing": c["facing"], "trait": c["trait"],
                  "age": now - c["born"] + c["bonus"]} for c in self.young]
        return {
            "version": 17, "flood_age": None if self.flood_t0 is None or self.mermaid_cave else now - self.flood_t0,
            "rain_age": None if self.rain_t0 is None else now - self.rain_t0,
            "surge_age": None if self.surge_t0 is None else now - self.surge_t0, "level": self.level, "kills": self.kills, "unlocked": sorted(self.unlocked), "golden": self.golden, "hat": self.hat,
            "coins": [list(c) for c in COINS if c not in self.coins],
            "fullness": self.fullness, "happiness": self.happiness, "muted": self.muted,
            "hats_tried": sorted(h for h in self.hats_tried if h), "friends_met": sorted(self.friends_met),
            "weathers_seen": sorted(self.weathers_seen),
            "health": self.health, "ammo": self.ammo, "packs": [list(p) for p in self.packs],
            "gems": self.gems, "gems_start": self.gems_at_start, "gem_taken": self.gem_taken, "secret": self.secret_shown, "revealed": [self.hidden.index(p) for p in self.revealed],
            "inventory": sorted(self.inventory), "item_spots": {k: list(v) for k, v in self.item_spots.items()},
            "lives": self.lives, "stamina": self.stamina, "pearls_found": self.pearls_found,
            "x": (SQUISH_PATCH[0] if self.level == 1 else 40) if self.feet > GROUND else self.x, "floor": GROUND if self.feet > GROUND else self.floor, "facing": self.facing,
            "young": young,
            "adults": [{"x": a["x"], "fy": a["fy"], "facing": a["facing"]} for a in self.adults],
            "eggs": [{"x": e["x"], "y": e["y"], "age": now - e["born"]} for e in self.eggs if e["state"] == "egg"],
        }

    def load_state(self, data, now):
        self.unlocked = {k for k in data["unlocked"] if k in {a[0] for a in self.achievements}}
        self.golden = bool(data.get("golden")) and len(self.unlocked) == len(self.achievements) and self.level == LAST_LEVEL
        self.kills = clamp(int(data.get("kills", 0)), 0, self.enemy_total) if self.level in SLAYER_LEVELS else 0
        if self.level in SLAYER_LEVELS:
            self.enemies = self.enemies[self.kills:]
        self.hat = data["hat"] if self.survival and data.get("hat") in HAT_ORDER else None
        self.coins = set(COINS) - {tuple(c) for c in data["coins"]}
        if self.survival:
            self.fullness = clamp(float(data["fullness"]), 0.0, 100.0)
            self.happiness = clamp(float(data["happiness"]), 0.0, 100.0)
        self.muted = bool(data.get("muted"))
        self.hats_tried = set(data.get("hats_tried", []))
        self.friends_met = set(data.get("friends_met", [])) & set(FRIENDS)
        self.weathers_seen = set(data.get("weathers_seen", [])) & set(WEATHERS)
        self.lives = clamp(int(data.get("lives", MAX_LIVES)), 1, MAX_LIVES)
        self.health = clamp(float(data.get("health", MAX_HEALTH)), 1.0, MAX_HEALTH)
        self.ammo = clamp(int(data.get("ammo", 0)), 0, MAX_AMMO)
        if "packs" in data:
            self.packs = [(int(x), int(y)) for x, y in data["packs"]]
        self.inventory = {k for k in data.get("inventory", []) if k in LEVEL_ITEMS}
        self.item_spots = place_items(self.inventory)
        for key, spot in data.get("item_spots", {}).items():
            if key in self.item_spots and key != "peashooter" and len(spot) == 2:
                self.item_spots[key] = (int(spot[0]), int(spot[1]))
        self.stamina = clamp(float(data.get("stamina", 100.0)), 0.0, 100.0)
        self.pearls_found = max(0, int(data.get("pearls_found", 0)))
        self.gems = max(0, int(data.get("gems", 0)))
        self.gems_at_start = clamp(int(data.get("gems_start", self.gems)), 0, self.gems)
        self.gem_taken = bool(data.get("gem_taken")) and self.level in GEM_SPOTS
        if data.get("secret") and self.level == 6:
            self.show_secret_mushroom(now)
        self.revealed = {self.hidden[i]: (-99.0, 0) for i in data.get("revealed", []) if 0 <= int(i) < len(self.hidden)}
        if self.level in REVEALED_LEVELS:
            for p in self.revealed:
                add_platform(p)
        self.facing = 1 if data.get("facing", 1) >= 0 else -1
        self.x = clamp(int(data["x"]), 0, WORLD_W - DUCK_W)
        if self.flood is not None:
            age = data.get("flood_age")
            self.flood_t0 = None if age is None else now - float(age)
            rain_age = data.get("rain_age")
            if rain_age is not None:
                self.rain_t0 = now - float(rain_age)
                self.spawn_cloud()
            surge_age = data.get("surge_age")
            if surge_age is not None:
                self.surge_t0 = now - float(surge_age)
                self.set_weather("rain", now)
                self.next_weather = float("inf")
        floor = int(data["floor"])
        self.feet = self.floor = floor if support(self.center(), floor) == floor else GROUND
        for c in data["young"]:
            chick = new_chick(clamp(int(c["x"]), 0, WORLD_W - 4), c["facing"], now, int(c["fy"]))
            chick["bonus"], chick["trait"] = float(c["age"]), c["trait"] if c["trait"] in ("loyal", "adventurous") else "loyal"
            self.young.append(chick)
        for a in data["adults"]:
            self.adults.append(new_adult(clamp(int(a["x"]), 0, WORLD_W - ADULT_W), a["facing"], now, int(a["fy"])))
        for e in data["eggs"]:
            self.eggs.append({"x": clamp(int(e["x"]), 0, WORLD_W - 1), "y": int(e["y"]), "born": now - float(e["age"]),
                              "t0": now, "state": "egg", "ch": EGG})
        self.snap_camera()

    def pop_events(self):
        events, self.events = self.events, []
        return events

    def set_view(self, view_w, view_h=None):
        self.view_w = clamp(view_w, 10, WORLD_W)
        self.view_h = clamp(view_h or self.view_h, MIN_VIEW_H, WORLD_H)
        self.particles = [p for p in self.particles if p[0] < self.view_w and p[1] < self.view_h]
        self.cam = clamp(self.cam, 0, WORLD_W - self.view_w)
        self.cam_y = clamp(self.cam_y, 0, self.max_cam_y())

    def camera_target(self):
        return clamp(self.x + DUCK_W // 2 - self.view_w // 2, 0, WORLD_W - self.view_w)

    def camera_target_y(self):
        if self.level <= 5 and self.view_h >= SCREEN_VIEW_H and self.feet <= GROUND and self.floor - DUCK_H - 1 >= SURFACE_H - self.view_h:  # (unless she has climbed above the screen)
            return clamp(SURFACE_H - self.view_h, 0, self.max_cam_y())
        # Dead zone: the camera only scrolls when the duck gets within `buf` rows of an edge.
        # Jumps don't scroll it; the floor she stands on (or falls past) does.
        buf = clamp((self.view_h - DUCK_H) // 3, 1, VBUFFER)
        ref = (self.feet if self.airborne and self.rise_rows > JUMP_ROWS else max(self.floor, self.feet)) + self.depth  # bounces carry her above the floor
        highest = ref - DUCK_H  # head plus hat
        target = min(self.cam_y, highest - buf)
        target = max(target, ref + buf - (self.view_h - 1))
        return clamp(target, 0, self.max_cam_y())

    def max_cam_y(self):
        # the lake bed only scrolls into view while she is in the water
        return (WORLD_H if self.depth or self.feet > GROUND else SURFACE_H) - self.view_h

    def snap_camera(self):
        self.cam = self.camera_target()
        self.cam_y = self.camera_target_y()

    def sleeping(self, now):
        return now - self.last_input >= SLEEP_AFTER

    def lay_egg(self, now):
        if self.flying is None:
            origin = self.x - 1 if self.facing > 0 else self.x + DUCK_W
            self.flying = (now, origin, -self.facing, self.feet)

    def feed(self, now):
        ahead = self.x + DUCK_W + 2 if self.facing > 0 else self.x - 3
        for _ in range(CRUMBS_PER_FEED):
            x = clamp(ahead + self.facing * random.randint(0, 10), 0, WORLD_W - 1)
            self.crumbs.append({"x": x, "y": self.feet - 2, "next": now, "landed": False})

    def set_weather(self, weather, now):
        self.weather = weather
        self.weathers_seen.add(weather)
        if {"rain", "snow"} <= self.weathers_seen:
            self.unlock("weather", now)
        self.next_weather = now + random.uniform(*WEATHER_EVERY)
        self.particles = []

    def center(self):
        return self.x + DUCK_W // 2

    def in_pond(self):
        return not self.airborne and self.feet == GROUND and (self.depth > 0 or is_water(self.center()))

    def ground_visible(self):
        return self.cam_y + self.view_h > GROUND

    def pond_visible(self):
        return self.ground_visible() and bool(self.visible_ponds())

    def visible_ponds(self):
        return [p for p in PONDS if p < self.cam + self.view_w and p + POND_W > self.cam]

    # ---- helpers --------------------------------------------------------------------------
    def nearest_crumb(self, center, floor):
        crumbs = [c for c in self.crumbs if c["landed"] and c["y"] == floor]
        return min(crumbs, key=lambda c: abs(c["x"] - center)) if crumbs else None

    def eat(self, x, width, floor):
        eaten = [c for c in self.crumbs if c["landed"] and c["y"] == floor and x <= c["x"] < x + width]
        for crumb in eaten:
            self.crumbs.remove(crumb)
        return len(eaten)

    def add_splash(self, x, now):
        self.splashes.append((x, now))

    # ---- simulation -----------------------------------------------------------------------
    def update(self, now):
        if self.toast_queue and now >= self.toast[1]:
            self.toast = (self.toast_queue.pop(0), now + TOAST_TIME)
        self.update_celebration(now)
        if self.died:
            return
        if self.drowned is not None:  # everything else stands still while the duck sinks
            self.update_flood(now)
            self.update_weather(now)
            self.cam_y += clamp(self.camera_target_y() - self.cam_y, -1, 1)
            return
        self.update_depth(now)
        self.update_items(now)
        self.update_chamber(now)
        self.update_peas(now)
        self.update_mover(now)
        self.update_wind(now)
        self.update_flood(now)
        self.update_enemies(now)
        self.update_needs(now)
        self.update_duck(now)
        self.update_eggs(now)
        self.update_crumbs(now)
        self.update_friends(now)
        self.update_predator(now)
        self.update_young(now)
        self.update_adults(now)
        self.update_weather(now)
        self.update_level_goals(now)
        self.cam += clamp(self.camera_target() - self.cam, -2, 2)
        self.cam_y += clamp(self.camera_target_y() - self.cam_y, -1, 1)
        self.splashes = [s for s in self.splashes if now - s[1] < SPLASH_FRAME * len(SPLASH_ARC)]

    def update_school(self, now):
        dt, self.fish_t = min(now - self.fish_t, 0.5), now
        for fish in self.school:
            fish["x"] += fish["dir"] * fish["speed"] * dt
            if not 0 <= fish["x"] <= WORLD_W - 3:
                fish["dir"] = -fish["dir"]
                fish["x"] = clamp(fish["x"], 0, WORLD_W - 3)

    def update_flood(self, now):
        if self.flood is None:
            return
        self.update_school(now)
        if self.mermaid_pending and self.drowned is not None and now - self.drowned >= DROWN_ANIM:
            if self.float_t0 is None:
                self.float_t0, self.float_x0 = now, self.x
                self.notice = ("You sink through the grass...", now + NOTICE_TIME)
            p = (now - self.float_t0) / MERMAID_FLOAT
            if p >= 1:
                self.enter_mermaid_cave(now)
            else:  # she drifts down through the rock, swaying, towards the mermaid
                p = p * p * (3 - 2 * p)
                self.x = int(self.float_x0 + (MERMAID_X - 12 - self.float_x0) * p + 2 * math.sin(now * 3))
                self.feet = GROUND + 1 + int((CH_FLOOR - GROUND - 1) * p)
            return
        if self.flood_t0 is None and not self.airborne and self.feet < GROUND:
            self.flood_t0 = now
            self.toast_queue.append("The water is rising!")
        if self.drowned is not None:
            pass
        elif self.submerged():
            if self.drown_t0 is None:
                self.drown_t0 = now
            elif now - self.drown_t0 >= FLOOD_DROWN:
                self.drowned = now  # no lives to lose here: the level starts over once she presses space
                self.mermaid_pending = self.level == MERMAID_LEVEL and not self.airborne and self.feet == GROUND  # drowned on the grass: the mermaid saves her
                self.dirs, self.sitting, self.quack_start, self.running = [], False, None, False
                self.shown, self.sparkles, self.quack_texts = 0, [], []
        else:
            self.drown_t0 = None
        on_cloud = self.on_cloud()
        if on_cloud and not self.cloud_boarded:
            self.cloud_boarded, self.flood_drop = True, CLOUD_DROP  # the first landing lowers the water, once
        if on_cloud and self.cloud_last is not None:  # the water holds still while she rides the cloud
            dt = now - self.cloud_last
            self.flood_t0 = None if self.flood_t0 is None else self.flood_t0 + dt
            self.rain_t0 = None if self.rain_t0 is None else self.rain_t0 + dt
            self.surge_t0 = None if self.surge_t0 is None else self.surge_t0 + dt
        self.cloud_last = now
        if self.flood_t0 is not None:
            age = now - self.flood_t0
            cfg = self.flood_cfg
            if cfg["rain_ledge"] and self.rain_t0 is None and not self.airborne and self.feet <= cfg["ledges"][cfg["rain_ledge"] - 1][2]:
                self.rain_t0 = now
                self.set_weather("rain", now)
                self.next_weather = float("inf")
                self.toast_queue.append("Rain! The water is rising faster!")
                self.spawn_cloud()
            surge = cfg["surge"]
            if surge and self.surge_t0 is None and not self.airborne and self.feet <= cfg["ledges"][surge[0] - 1][2]:
                self.surge_t0 = now
                self.toast_queue.append("The water is surging!")
            rain = 0.0 if self.rain_t0 is None else now - self.rain_t0
            rise = cfg["speed"] * age + cfg["accel"] * rain * rain / 2
            if self.surge_t0 is not None:
                s = now - self.surge_t0
                rise += surge[1] * s + surge[2] * s * s / 2
            if cfg["max_speed"]:
                rise = self.capped_rise(cfg, now)
            self.flood = min(GROUND + 1, max(cfg["top"], GROUND + 1 - int(rise) + self.flood_drop))

    def capped_rise(self, cfg, now):
        """Integrates the water's speed in small steps so that it never exceeds cfg["max_speed"]."""
        step, rise, t = 0.1, 0.0, self.flood_t0
        while t < now:
            dt = min(step, now - t)
            mid = t + dt / 2
            v = cfg["speed"]
            if self.rain_t0 is not None and mid > self.rain_t0:
                v += cfg["accel"] * (mid - self.rain_t0)
            if self.surge_t0 is not None and mid > self.surge_t0:
                v += cfg["surge"][1] + cfg["surge"][2] * (mid - self.surge_t0)
            rise += min(v, cfg["max_speed"]) * dt
            t += dt
        return rise

    def wet(self):
        return self.flood is not None and self.flood <= self.feet

    def enter_mermaid_cave(self, now):
        """She has floated down to the mermaid's cavern; the flood is gone until she climbs out."""
        self.drowned = self.flood = self.flood_t0 = self.drown_t0 = self.float_t0 = None
        self.mermaid_pending, self.mermaid_cave = False, True
        self.rain_t0 = self.surge_t0 = None
        self.dirs, self.up_held, self.sitting = [], False, False
        self.x, self.facing = MERMAID_X - 12, 1
        self.feet = self.floor = CH_FLOOR
        self.airborne = False

    def submerged(self):
        return self.flood is not None and self.flood <= self.feet - 2  # her head is under

    def on_cloud(self):
        if self.level != 10 or self.airborne or self.drowned is not None:
            return False
        return any(m.get("cloud") and self.feet == m["floor"] and m["x0"] <= self.center() < m["x0"] + m["w"] for m in self.movers)

    def spawn_cloud(self):
        """Level 10: a cloud (a sliding ledge) drifts in from the right once the rain starts."""
        if self.level != 10 or self.movers:
            return
        m = {"x0": CLOUD_CFG["lo"], "w": CLOUD_CFG["w"], "floor": CLOUD_FLOOR, "lo": CLOUD_CFG["lo"], "hi": CLOUD_CFG["hi"], "step": CLOUD_CFG["step"], "dir": 1,
             "next": 0.0, "cloud": True}
        self.movers.append(m)
        add_platform((m["x0"], m["x0"] + m["w"] - 1, m["floor"]))
        self.toast_queue.append("A storm cloud drifts by...")

    def update_mover(self, now):
        for m in self.movers:
            self.step_mover(m, now)

    def step_mover(self, m, now):
        if now < m["next"]:
            return
        m["next"] = now + m["step"]
        if not m["lo"] <= m["x0"] + m["dir"] <= m["hi"]:
            m["dir"] = -m["dir"]
        d = m["dir"]
        old = (m["x0"], m["x0"] + m["w"] - 1, m["floor"])
        move_platform(old, (old[0] + d, old[1] + d, old[2]))
        m["x0"] += d
        if not self.airborne and self.feet == m["floor"] and old[0] <= self.center() <= old[1]:
            self.x = clamp(self.x + d, 0, WORLD_W - DUCK_W)
        for e in self.enemies:  # whatever stands on the ledge rides along
            if e.get("ride") is m:
                e["x"] += d
                e["lo"] += d
                e["hi"] += d
        for things, row in ((self.eggs, "y"), (self.crumbs, "y"), (self.young, "fy"), (self.adults, "fy")):
            for t in things:
                if t[row] == m["floor"] and old[0] <= t["x"] <= old[1]:
                    t["x"] += d

    def update_needs(self, now):
        dt = min(now - self.last_needs, 1.0)
        self.last_needs = now
        if self.level == 1:  # the tutorial has no hunger, mood or stamina to manage
            return
        if self.survival:
            self.fullness = max(0.0, self.fullness - HUNGER_RATE * dt * (0.5 if self.sleeping(now) else 1.0))
            mood = 0.7 * self.fullness + min(30.0, 6 * len(self.young) + 3 * len(self.adults))
            self.happiness += (mood - self.happiness) * min(1.0, dt * 0.15)
            self.cheer(0.0, now)
        self.update_stamina(dt, now)

    def update_stamina(self, dt, now):
        moving = bool(self.dirs) and not self.sitting
        self.run_active = self.running and moving and not self.tired
        self.gliding = self.airborne and self.air_phase == "fall" and self.up_held and not self.tired \
            and "umbrella" in self.inventory
        if self.run_active:
            self.stamina -= RUN_DRAIN * dt
        if self.gliding:
            self.stamina -= GLIDE_DRAIN * dt
        if not (self.run_active or self.gliding):
            self.stamina += STAMINA_REGEN * dt * (0.5 if self.fullness < HUNGRY_BELOW else 1.0)
        self.stamina = clamp(self.stamina, 0.0, 100.0)
        if self.stamina <= 0:
            self.tired = True
        elif self.tired and self.stamina >= TIRED_UNTIL:
            self.tired = False

        if (self.depth and cave_cell(self.center(), GROUND - 2 + self.depth) == "w"):  # head under water
            self.breath -= BREATH_DRAIN * dt
            if self.breath <= 0:
                self.black_out(now)
        else:
            self.breath += BREATH_REGEN * dt
        self.breath = clamp(self.breath, 0.0, self.breath_max())
        if self.depth:
            self.collect_pearls(now)
        for pearl, t in list(self.pearl_taken.items()):
            if now - t >= PEARL_RESPAWN:
                del self.pearl_taken[pearl]
                self.pearls.add(pearl)

    def fits(self, center, depth):
        head = GROUND - 2 + depth
        return all(cave_cell(x, y) for x in range(center - 2, center + 3) for y in (head, head + 1))

    def black_out(self, now):
        # out of air: she's washed up floating on the nearest lake's surface
        pond_x = min(PONDS, key=lambda p: abs(p + POND_W // 2 - self.center()))
        self.x = clamp(self.x, pond_x + 2, pond_x + POND_W - 3 - DUCK_W)
        self.depth, self.dive_dir, self.breath = 0, 0, 10.0
        self.cheer(-BLACKOUT_PENALTY, now)
        self.lose_life("Out of air!")

    def lose_life(self, reason):
        if self.level in NO_LIVES_LEVELS:  # no lives here: dying offers to start the level over
            self.died, self.dirs, self.sitting, self.quack_start, self.running = True, [], False, None, False
            return
        self.lives -= 1
        if self.lives <= 0:
            self.game_over, self.sitting, self.dirs = True, False, []
            self.quack_start = None
        else:
            self.toast_queue.append(f"{reason} {self.lives} {'life' if self.lives == 1 else 'lives'} left")

    def breath_max(self):
        return 100.0 * (TANK_AIR_FACTOR if "tank" in self.inventory else 1.0)

    def update_items(self, now):
        left, right = self.x, self.x + DUCK_W - 1
        top, bottom = (GROUND - 2 + self.depth, GROUND - 1 + self.depth) if self.depth else (self.feet - (DUCK_H - 1), self.feet)
        for key, (x, y) in list(self.item_spots.items()):
            if left <= x <= right and top <= y <= bottom:
                del self.item_spots[key]
                self.inventory.add(key)
                self.notice = (f"Found the {ITEMS[key][0]}!", now + NOTICE_TIME)
                if not self.muted:
                    self.events.append("coin")
        for pack in [p for p in self.packs if left <= p[0] <= right and top <= p[1] <= bottom]:
            self.packs.remove(pack)
            self.pack_taken.append(now + PACK_RESPAWN)
            self.ammo = min(MAX_AMMO, self.ammo + PACK_AMMO)
            self.notice = (f"Pea pack! +{PACK_AMMO} peas", now + NOTICE_TIME)
            if not self.muted:
                self.events.append("coin")
        for t in [t for t in self.pack_taken if now >= t]:  # a fresh pack turns up elsewhere
            self.pack_taken.remove(t)
            self.packs += place_packs(1)

    def update_chamber(self, now):
        """The pink gem secrets: level 1's patch drops her into a cavern, level 4 hides ledges that appear under her feet."""
        if self.hidden and self.level not in REVEALED_LEVELS and not self.airborne:
            for p in self.hidden:
                if p not in self.revealed and p[2] == self.feet and p[0] <= self.center() <= p[1]:
                    self.revealed[p] = (now, self.center())
        if self.level == 6 and not self.secret_shown and not self.airborne and self.feet == SUMMIT and self.center() >= SECRET_TRIGGER:
            self.show_secret_mushroom(now)
        if self.mermaid_cave:
            if self.mermaid_t0 is None and not self.airborne and self.feet == CH_FLOOR:
                self.mermaid_t0 = now
                self.notice = ("A mermaid revives the duck!", now + NOTICE_TIME)
            elif self.mermaid_t0 is not None and self.room_open is None and now - self.mermaid_t0 >= MERMAID_REVIVE:
                self.room_open = now
                for p in MER_ROOM_LEDGES:
                    add_platform(p)
                self.notice = ("A hidden room opens in the rock!", now + NOTICE_TIME)
            elif self.room_open is not None and not self.airborne and self.feet <= GROUND:
                self.mermaid_cave, self.flood, self.flood_t0 = False, GROUND + 1, None  # the water starts again once she climbs a ledge
                self.toast_queue.append("The water is back!")
        if self.level in GEM_SPOTS and not self.gem_taken and self.gem_visible():
            self.gem_hit(now)
        if self.level == 1 and not self.airborne and self.feet == GROUND and self.sitting and SQUISH_PATCH[0] <= self.center() <= SQUISH_PATCH[1] \
                and now - self.sit_start >= PATCH_SIT_TIME:
            self.sitting, self.airborne, self.air_phase, self.air_n, self.air_next = False, True, "fall", 0, now
            self.feet = GROUND + 1
            self.notice = ("You fell through the grass!", now + NOTICE_TIME)

    def quack_secret(self, now):
        """Level 2: a full chorus on top of a hill makes that hill's hidden ledge appear."""
        if self.level != 2 or self.airborne:
            return
        for (x0, x1, floor), p in zip(LEVEL2_TOPS, self.hidden):
            if p not in self.revealed and self.feet == floor and x0 <= self.center() <= x1:
                self.revealed[p] = (now, self.center())
                add_platform(p)
                self.notice = ("A hidden ledge appears!" if len(self.revealed) < len(self.hidden) else "Another ledge appears high above the first... something glitters!", now + NOTICE_TIME)

    def show_secret_mushroom(self, now):
        self.secret_shown = True
        MUSHROOMS.append(SECRET_MUSHROOM)
        self.plunged[SECRET_MUSHROOM] = now  # it pops up squashed
        self.notice = ("A mushroom sprouts!", now + NOTICE_TIME)

    def gem_visible(self):
        if self.level == 1:
            return self.feet > GROUND
        if self.level == MERMAID_LEVEL:
            return self.room_open is not None
        if self.level == 6:
            return self.secret_shown
        if self.level in REVEALED_LEVELS:
            return len(self.revealed) == len(self.hidden)
        if self.level == 10:
            return bool(self.movers) and self.cloud_boarded  # appears once she has jumped onto the cloud
        return self.hidden[GEM_APPEARS_AFTER - 1] in self.revealed

    def gem_hit(self, now):
        gx, gy = GEM_SPOTS[self.level]
        if self.x <= gx <= self.x + DUCK_W - 1 and self.feet - (DUCK_H - 1) <= gy <= self.feet:
            self.gem_taken = True
            self.gems += 1
            self.notice = (f"A pink gem! {GEM} {self.gems}", now + NOTICE_TIME)
            if not self.muted:
                self.events.append("coin")

    def shoot(self, now):
        if "peashooter" not in self.inventory or self.sitting or self.depth or now < self.next_shot:
            return
        self.next_shot = now + PEA_COOLDOWN
        if self.ammo <= 0:
            self.notice = ("Out of peas! Find a pea pack", now + NOTICE_TIME)
            return
        self.ammo -= 1
        if self.slippery():
            self.vel = clamp(self.vel - self.facing * ICE_RECOIL, -ICE_MAX, ICE_MAX)  # the kick
        x = self.center() + self.facing * (DUCK_W // 2 + 1)
        self.peas.append({"x": x, "y": self.feet - 2, "dir": self.facing, "left": PEA_RANGE, "next": now})

    def update_peas(self, now):
        live = []
        for pea in self.peas:
            if now >= pea["next"]:
                pea["x"] += pea["dir"]
                pea["left"] -= 1
                pea["next"] = now + PEA_STEP
            if pea["left"] <= 0 or not 0 <= pea["x"] < WORLD_W or self.pea_hits(pea, now) or self.pea_hits_duck(pea, now) or self.pea_hits_enemy(pea, now):
                continue
            live.append(pea)
        self.peas = live

    def spawn_beetle(self):
        for _ in range(30):
            if random.random() < 0.3:  # patrol a stretch of dry ground
                cx = random.randint(150, WORLD_W - 100)
                lo, hi, floor = cx - 15, cx + 15, GROUND
                if any(is_water(x) for x in range(lo - 6, hi + ENEMY_W + 6)):
                    continue
            else:
                lo, hi, floor = random.choice([p for p in PLATFORMS if p not in START_LEDGES])
                hi -= ENEMY_W - 1
                if hi - lo < 4:
                    continue
            x = random.randint(lo, hi)
            if floor == self.floor and abs(x - self.x) < 25:
                continue
            self.enemies.append({"kind": "beetle", "x": x, "y": floor, "lo": lo, "hi": hi, "dir": random.choice((-1, 1)),
                                 "hp": BEETLE_HP, "next": 0.0, "step": 0})
            return

    def spawn_bat(self, now):
        side = random.choice((-1, 1))
        base = clamp(self.feet - 5, self.cam_y + 1 + BAT_AMPLITUDE, self.cam_y + self.view_h - 2 - BAT_AMPLITUDE)
        x = int(self.cam) - ENEMY_W - 2 if side < 0 else int(self.cam) + self.view_w + 2
        self.enemies.append({"kind": "bat", "x": x, "y": base, "base": base, "dir": -side, "hp": 1, "next": now,
                             "born": now, "step": 0, "phase": random.uniform(0, 2 * math.pi)})

    def enemy_box(self, e):
        top = {"beetle": e["y"] - 2, "hedgehog": e["y"] - 2, "armadillo": e["y"] - 2, "mite": e["y"] - 1}.get(e["kind"], e["y"])
        return e["x"], e["x"] + (MITE_W if e["kind"] == "mite" else ENEMY_W) - 1, top, e["y"]

    def stun_mites(self, now):
        """A quack freezes every mite near enough to hear it."""
        for e in self.enemies:
            if e["kind"] == "mite" and abs(e["x"] + MITE_W // 2 - self.center()) <= STUN_RANGE and abs(e["y"] - self.feet) <= STUN_ROWS:
                e["stun"] = now + STUN_TIME
                self.unlock("stun", now)
        self.max_stunned = max(self.max_stunned, sum(e["kind"] == "mite" and e.get("stun", 0) > now for e in self.enemies))
        if self.level == 3 and sum(e["kind"] == "mite" and e.get("stun", 0) > now for e in self.enemies) >= MITES_FOR_SECRET and not self.revealed:
            for p in self.hidden:
                self.revealed[p] = (now, self.center())
                add_platform(p)
            self.notice = ("Hidden ledges appear above the second hill!", now + NOTICE_TIME)

    def update_enemies(self, now):
        beetles = sum(e["kind"] == "beetle" for e in self.enemies)
        for _ in range(max(0, self.beetle_target - beetles - len(self.enemy_respawns))):
            self.spawn_beetle()
        for t in [t for t in self.enemy_respawns if now >= t]:
            self.enemy_respawns.remove(t)
            self.spawn_beetle()
        if now >= self.next_bat and self.level >= LAST_LEVEL:
            self.next_bat = now + random.uniform(12, 25)
            if sum(e["kind"] == "bat" for e in self.enemies) < 2 and not self.depth:
                self.spawn_bat(now)
        keep = []
        for e in self.enemies:
            if now >= e["next"]:
                e["step"] += 1
                if e["kind"] == "hedgehog":
                    self.step_hedgehog(e, now)
                elif e["kind"] != "bat":
                    e["next"] = now + (MITE_STEP if e["kind"] == "mite" else 0.25)
                    e["x"] += e["dir"] if now >= e.get("stun", 0.0) else 0  # a stunned mite stays put
                    if not e["lo"] <= e["x"] <= e["hi"]:
                        e["x"] = clamp(e["x"], e["lo"], e["hi"])
                        e["dir"] = -e["dir"]
                else:
                    e["next"] = now + BAT_STEP
                    e["x"] += e["dir"]
                    wave = math.sin(2 * math.pi * (e["x"] * e["dir"]) / BAT_WAVELENGTH + e["phase"])
                    e["y"] = e["base"] - round(BAT_AMPLITUDE * wave)
            if e["kind"] == "beetle" and self.flood is not None and self.flood <= e["y"] - 2:
                self.kills += 1  # the rising water drowns it
                continue
            if e["kind"] == "bat" and (now - e["born"] > 20 or abs(e["x"] - self.x) > self.view_w + 30):
                continue
            keep.append(e)
        self.enemies = keep
        self.check_contact(now)
        dt = min(0.5, now - self.last_enemy_tick) if self.last_enemy_tick else 0.0
        self.last_enemy_tick = now
        if self.fullness > HUNGRY_BELOW:
            self.health = min(MAX_HEALTH, self.health + REGEN_PER_SEC * dt)

    def step_hedgehog(self, e, now):
        """Walks uphill, curls at the top, rolls back down, stays curled for a moment, then uncurls."""
        up, state = e["up"], e["state"]
        top, bottom = (e["hi"], e["lo"]) if up > 0 else (e["lo"], e["hi"])
        if state == "walk":
            e["x"] += up
            e["next"] = now + HEDGEHOG_WALK_STEP
            if (e["x"] - top) * up >= 0:
                e["x"], e["state"], e["next"] = top, "curl", now + HEDGEHOG_CURL_TIME
        elif state == "curl":
            e["state"], e["dir"], e["next"] = "roll", -up, now + HEDGEHOG_ROLL_STEP
        elif state == "roll":
            e["x"] -= up
            e["next"] = now + HEDGEHOG_ROLL_STEP
            if (e["x"] - bottom) * up <= 0:
                e["x"], e["state"], e["next"] = bottom, "ball", now + HEDGEHOG_BALL_TIME
        else:
            e["state"], e["dir"], e["next"] = "walk", up, now + HEDGEHOG_WALK_STEP

    def body_spans(self):
        """The duck's silhouette as {row: (left, right)}: just the body, not the hat or the empty corners of its box."""
        crouch = self.sitting and not self.in_pond()
        drop = 2 if crouch else 1 if (self.sitting or self.in_pond()) else 0
        lines = duck_lines(self.shown > 0, self.facing, 0, feet=not drop)
        if crouch:
            lines = lines[1:]
        top = self.feet - (DUCK_H - 1) + drop
        return {top + i: (self.x + len(line) - len(line.lstrip()), self.x + len(line.rstrip()) - 1)
                for i, line in enumerate(lines) if line.strip()}

    def check_contact(self, now):
        if self.depth or now < self.invuln_until:
            return
        spans = self.body_spans()
        for e in self.enemies:
            if now < e.get("stun", 0.0):
                continue  # stunned mites are harmless
            x0, x1, y0, y1 = self.enemy_box(e)
            if any(y0 <= y <= y1 and x0 <= right and x1 >= left for y, (left, right) in spans.items()):
                self.hurt(now, {"beetle": BEETLE_DAMAGE, "hedgehog": BEETLE_DAMAGE, "armadillo": BEETLE_DAMAGE, "mite": MITE_DAMAGE}.get(e["kind"], BAT_DAMAGE))
                return

    def hurt(self, now, damage):
        self.health -= damage
        self.invuln_until = now + HIT_INVULN
        if self.health <= 0:
            self.health, self.invuln_until = MAX_HEALTH, now + 3.0
            self.lose_life("Knocked out!")
        else:
            self.notice = ("Ouch!", now + 1.0)

    def pea_hits_duck(self, pea, now):
        """A pea that bounced off an armadillo's armor hurts the duck it flies back to (sitting or jumping gets under it)."""
        if not pea.get("hostile") or self.depth or now < self.invuln_until:
            return False
        span = self.body_spans().get(pea["y"])
        if span and span[0] <= pea["x"] <= span[1]:
            self.hurt(now, ARMADILLO_HIT_DAMAGE)
            return True
        return False

    def pea_hits_enemy(self, pea, now):
        for e in self.enemies:
            x0, x1, y0, y1 = self.enemy_box(e)
            if x0 <= pea["x"] <= x1 and y0 - 1 <= pea["y"] <= y1 + 1:
                armored = e["kind"] == "armadillo" and pea["dir"] != e["dir"]  # only a pea flying the way it faces (from behind) gets through
                if armored or (e["kind"] == "hedgehog" and e["state"] != "walk"):
                    if not pea.get("bounced"):
                        pea["dir"], pea["bounced"] = -pea["dir"], True
                        if armored:
                            pea["hostile"] = True
                        else:
                            pea["left"] = min(pea["left"], 4)
                            self.notice = ("Ping! Wait for it to uncurl", now + 1.5)
                    continue
                if pea.get("bounced") and e["kind"] in ("hedgehog", "armadillo"):
                    continue
                e["hp"] -= 1
                if e["hp"] <= 0:
                    self.enemies.remove(e)
                    self.ammo = min(MAX_AMMO, self.ammo + KILL_AMMO)
                    self.kills += 1
                    if e["kind"] == "beetle" and self.beetle_target:
                        self.enemy_respawns.append(now + ENEMY_RESPAWN)
                else:  # it flinches, is knocked back a column and stops for a moment
                    e["hit"] = now + BEETLE_HIT_TIME
                    e["next"] = max(e["next"], now + BEETLE_HIT_TIME)
                    e["x"] = clamp(e["x"] + pea["dir"], e["lo"], e["hi"])
                return True
        return False

    def pea_hits(self, pea, now):
        p = self.predator
        if not p or p["state"] == "flee":
            return False
        hawk = p["kind"] == "hawk"
        top, bottom = (p["y"], p["y"] + 1) if hawk else (GROUND - 1, GROUND)
        if p["x"] <= pea["x"] < p["x"] + (HAWK_W if hawk else FOX_W) and top - 1 <= pea["y"] <= bottom + 1:
            p["state"], p["dir"] = "flee", pea["dir"]
            self.unlock("scare", now)
            self.notice = ("Pew! It ran away!", now + NOTICE_TIME)
            return True
        return False

    def update_depth(self, now):
        if not self.sitting or (not self.depth and not is_water(self.center())):
            self.depth, self.dive_dir = 0, 0
            return
        if self.dive_dir and now >= self.depth_next:
            new = self.depth + self.dive_dir
            if new < 0 or not self.fits(self.center(), new):
                self.dive_dir = 0  # bumped into rock
                return
            self.depth = new
            self.depth_next = now + (SINK_DELAY if self.dive_dir > 0 else RISE_SWIM_DELAY)
            if not self.depth:
                self.dive_dir = 0

    def collect_pearls(self, now):
        head = GROUND - 2 + self.depth
        for pearl in [p for p in self.pearls if abs(p[0] - self.center()) <= 3 and head <= p[1] <= head + 2]:
            self.pearls.discard(pearl)
            self.pearl_taken[pearl] = now
            self.pearls_found += 1
            self.cheer(PEARL_HAPPINESS, now)
            if not self.muted:
                self.events.append("coin")

    def cheer(self, amount, now):
        if not self.survival:
            return  # mood is fixed outside the full game
        self.happiness = clamp(self.happiness + amount, 0.0, 100.0)
        if self.happiness >= HAPPY_AT:
            self.unlock("happy", now)

    def collect_coins(self, now):
        left, right, top = self.x, self.x + DUCK_W - 1, self.feet - (DUCK_H - 1)
        for coin in [c for c in self.coins if left <= c[0] <= right and top <= c[1] <= self.feet]:
            self.coins.discard(coin)
            self.cheer(COIN_HAPPINESS, now)
            if not self.muted:
                self.events.append("coin")
            if len(COINS) - len(self.coins) >= COINS_FOR_ACHIEVEMENT:
                self.unlock("coins", now)

    def update_celebration(self, now):
        if self.celebrate_start is None:
            return
        if now - self.celebrate_start >= CELEBRATE_TIME:
            self.celebrate_start, self.bursts, self.confetti = None, [], []
            return
        if now >= self.next_burst:
            self.next_burst = now + random.uniform(0.12, 0.4)
            self.bursts.append((random.randint(4, self.view_w - 5), random.randint(2, max(3, self.view_h * 2 // 3)),
                                now, random.choice(RAINBOW)))
        for _ in range(3):
            self.confetti.append((random.randrange(self.view_w), now, random.uniform(5, 12),
                                  random.choice("*+~o'"), random.choice(RAINBOW), random.random() * 6))
        self.bursts = [b for b in self.bursts if now - b[2] < BURST_LIFE]
        self.confetti = [c for c in self.confetti if (now - c[1]) * c[2] < self.view_h]

    def on_mushroom(self):
        center = self.center()
        return any(floor == self.feet and x0 <= center < x0 + MUSH_W for x0, floor in MUSHROOMS)

    def bounce(self, now):
        self.airborne, self.air_phase, self.air_n, self.air_next = True, "rise", 0, now
        self.rise_rows = BOUNCE_ROWS + (BOUNCE_BOOST if self.up_held else 0)
        center = self.center()
        for x0, floor in MUSHROOMS:
            if floor == self.feet and x0 <= center < x0 + MUSH_W:
                self.plunged[(x0, floor)] = now
        if not self.muted:
            self.events.append("boing")

    def update_wind(self, now):
        w = self.wind
        if w is None:
            if now >= self.next_gust:
                self.wind = {"dir": random.choice((-1, 1)), "start": now + GUST_WARN, "end": now + GUST_WARN + GUST_TIME, "push": 0.0}
                if self.feet <= WIND_ROW + 12:
                    self.notice = ("Gust coming!", now + GUST_WARN + 0.5)
            return
        if now >= w["end"]:
            self.wind, self.next_gust = None, now + random.uniform(*GUST_EVERY)
        elif now >= w["start"] and now >= w["push"]:
            blown = (now - w["start"]) / GUST_TIME
            interval = GUST_PUSH_START + (GUST_PUSH_END - GUST_PUSH_START) * min(blown, 1.0)  # accelerates
            columns = min(1 + int((now - max(w["push"], w["start"])) / interval), 4)  # a slow frame still blows her the full distance
            w["push"] = now + interval
            if not self.sitting and not self.depth and self.feet <= WIND_ROW:  # sitting braces against it
                self.x = clamp(self.x + w["dir"] * columns, 0, WORLD_W - DUCK_W)

    def slippery(self):
        return self.ice or (self.level == GRAND_LEVEL and self.center() < GRAND_ICE_X)

    def ice_at(self, x):
        return self.ice or (self.level == GRAND_LEVEL and x < GRAND_ICE_X)

    def coast(self, now):
        """Speed carried off the ice: she drifts on, losing it very fast on grass (and slowly in the air); once it is gone she just walks."""
        dt = clamp(now - self.slide_t, 0.0, 0.05)
        self.slide_t = now
        if not self.vel:
            return
        drag = (ICE_FRICTION if self.airborne else GRASS_DRAG) * dt
        self.vel = 0.0 if abs(self.vel) <= drag else self.vel - math.copysign(drag, self.vel)
        self.slide_x += self.vel * dt
        columns = int(self.slide_x)
        self.slide_x -= columns
        for _ in range(abs(columns)):
            new_x = self.x + (1 if columns > 0 else -1)
            if not 0 <= new_x <= WORLD_W - DUCK_W:
                self.vel = self.slide_x = 0.0
                break
            self.x = new_x

    def update_ice(self, now, direction):
        dt = clamp(now - self.slide_t, 0.0, 0.05)
        self.slide_t = now
        if direction:
            self.vel = clamp(self.vel + direction * (ICE_AIR_ACCEL if self.airborne else ICE_ACCEL) * dt, -ICE_MAX, ICE_MAX)
        elif not self.airborne:  # the brake is sitting; otherwise she just slows a little
            drag = (ICE_BRAKE if self.sitting else ICE_FRICTION) * dt
            self.vel = 0.0 if abs(self.vel) <= drag else self.vel - math.copysign(drag, self.vel)
        self.walking = abs(self.vel) >= 2.0
        self.slide_x += self.vel * dt
        columns = int(self.slide_x)
        self.slide_x -= columns
        for _ in range(abs(columns)):
            new_x = self.x + (1 if columns > 0 else -1)
            if not 0 <= new_x <= WORLD_W - DUCK_W:  # the edge of the rink is a wall
                self.vel = self.slide_x = 0.0
                break
            self.x = new_x
            if direction:  # sliding without a key held doesn't move her feet
                self.step += 1

    def update_air(self, now):
        if not self.airborne:
            if not self.sitting and support(self.center(), self.feet) > self.feet:
                self.airborne, self.air_phase, self.air_n, self.air_next = True, "fall", 0, now  # walked off a ledge
            elif not self.sitting and self.on_mushroom():
                self.bounce(now)
            return
        if now < self.air_next:
            return
        if self.air_phase == "rise":  # ledges are one-way: she passes up through them
            self.feet -= 1
            self.air_n += 1
            if self.air_n >= self.rise_rows:
                self.air_phase, self.air_n, self.air_next = "fall", 0, now + HANG_DELAY
            else:
                self.air_next = now + RISE_DELAYS[min(self.air_n, len(RISE_DELAYS) - 1)]
            return
        center = self.center()
        if support(center, self.feet) > self.feet:
            self.feet += 1
        if support(center, self.feet) == self.feet:
            self.airborne, self.floor = False, self.feet
            if self.on_mushroom() and not self.sitting:
                self.bounce(now)
                return
            if self.feet == GROUND - STEP * MAX_LEVEL:
                self.unlock("king", now)
        else:
            self.air_n += 1
            self.air_next = now + (GLIDE_DELAY if self.gliding else FALL_DELAYS[min(self.air_n, len(FALL_DELAYS) - 1)])

    def update_duck(self, now):
        self.update_air(now)
        if self.quack_start is not None:
            count = quack_count(now - self.quack_start)
            if count != self.shown:
                if count == 1:
                    self.sparkles, self.quack_texts = [], []
                self.sparkles += new_sparkles(count - 1)
                self.quack_texts.append(random.choice(QUACK_WORDS))
                self.shown = count
                self.cheer(QUACK_HAPPINESS, now)
                if count == MAX_QUACKS:
                    self.unlock("chorus", now)
                    self.quack_secret(now)
                if not self.muted:
                    self.events.append("quack")
                self.stun_mites(now)
                for chick in self.young:  # the chicks react to the noise
                    if random.random() < 0.5:
                        chick["peep_text"] = random.choice(("peep!", "chirp!", "!"))
                        chick["peep_until"] = now + 0.8

        if self.sitting and not self.egg_rolled and now - self.sit_start >= SIT_AFTER:
            self.egg_rolled = True  # one roll per sit session
            if self.fullness > 0 and random.random() < EGG_BASE_CHANCE + 0.6 * self.happiness / 100:
                self.lay_egg(now)

        direction = 0
        if not self.sitting or self.depth:  # she can swim sideways underwater
            if self.dirs:
                direction = self.facing
            elif self.sitting:
                pass
            else:
                crumb = None if self.airborne else self.nearest_crumb(self.center(), self.floor)
                if crumb:
                    direction = self.facing = 1 if crumb["x"] > self.center() else -1
        self.walking = bool(direction)
        slide = self.slippery()
        if slide:
            self.update_ice(now, direction)
            self.next_step = now  # no catching-up steps when she leaves the ice
        elif direction and now >= self.next_step:
            interval = WALK_INTERVAL * (1.6 if self.fullness < SLOW_BELOW else 1.0) * (RUN_FACTOR if self.run_active else 1.0) * (SWIM_SLOWDOWN if self.depth else FLOOD_SLOWDOWN if self.wet() else 1.0)
            n = min(1 + int((now - self.next_step) / interval), 8)  # running is faster than the loop tick
            for _ in range(n):
                cave = (MER_X0, MER_X1) if self.level == MERMAID_LEVEL else (CH_X0, CH_X1)  # underground she stays inside the cavern
                new_x = clamp(self.x + direction, cave[0] if self.feet > GROUND else 0, cave[1] - DUCK_W + 1 if self.feet > GROUND else WORLD_W - DUCK_W)
                if self.depth and not self.fits(new_x + DUCK_W // 2, self.depth):
                    break  # rock in the way
                self.x = new_x
                self.step += 1
            self.next_step = max(self.next_step + n * interval, now - interval)
            if self.in_pond():
                self.ripples.append((self.center() - direction * 5, now))
        elif not direction:
            self.step, self.next_step = 0, now
        if not slide:
            if direction:  # walking takes over at once: her speed must not add to the walking speed
                self.vel, self.slide_t = 0.0, now
            else:
                self.coast(now)

        in_pond = self.in_pond()
        diving = self.sitting and in_pond
        if in_pond != self.was_in_pond or diving != self.was_diving:
            self.add_splash(self.center(), now)
        self.was_in_pond, self.was_diving = in_pond, diving
        if self.depth >= 2:
            self.unlock("swimmer", now)
        if 2 <= self.depth <= 8 and now >= self.next_bubble:
            self.next_bubble = now + 0.35
            self.ripples.append((self.center() + random.randint(-3, 3), now))
        self.ripples = [r for r in self.ripples if now - r[1] < RIPPLE_FRAME_TIME * len(RIPPLE_FRAMES)]

        eaten = 0 if self.airborne else self.eat(self.x, DUCK_W, self.floor)
        if eaten:
            self.nom_until = now + NOM_TIME
            self.fullness = min(100.0, self.fullness + FOOD_VALUE * eaten)
            self.stamina = min(100.0, self.stamina + STAMINA_PER_CRUMB * eaten)
            if self.stamina >= TIRED_UNTIL:
                self.tired = False
            self.unlock("snack", now)
        self.collect_coins(now)
        if self.sleeping(now):
            self.unlock("owl", now)

        free = not (self.dirs or self.sitting or self.quack_start is not None
                    or self.airborne or self.walking or self.sleeping(now))
        if self.behavior and (not free or now - self.behavior[1] >= self.behavior[2]):
            self.behavior = None
        if free and self.behavior is None and now >= self.next_idle:
            name, duration = random.choice(IDLE_BEHAVIORS)
            self.behavior = (name, now, duration)
            self.next_idle = now + random.uniform(*IDLE_GAP)
        if free and now >= self.next_thought:
            thoughts = THOUGHTS if self.survival else [t for t in THOUGHTS if t != "hungry?"]  # no feeding outside the full game
            text = "so hungry..." if self.fullness < HUNGRY_BELOW and self.survival else random.choice(thoughts)
            self.thought = (text, now + THOUGHT_TIME)
            self.next_thought = now + random.uniform(*THOUGHT_GAP)
        self.update_air(now)  # notice a step off a ledge right away

    def update_eggs(self, now):
        for egg in self.eggs[:]:
            if egg["state"] == "egg":
                if now - egg["born"] < HATCH_AFTER:
                    continue
                egg["state"] = random.choice(("melting", "hatching"))
                egg["t0"] = now
            frames = MELT_FRAMES if egg["state"] == "melting" else HATCH_FRAMES
            idx = int((now - egg["t0"]) / ANIM_FRAME_TIME)
            if idx >= len(frames):
                self.eggs.remove(egg)
                if egg["state"] == "hatching":
                    self.young.append(new_chick(egg["x"], self.facing, now, egg["y"]))
                    self.unlock("hatchling", now)
                    if len(self.young) >= NEST_SIZE:
                        self.unlock("nest", now)
            else:
                egg["ch"] = frames[idx]

        self.flying_pos = None
        if self.flying:
            start, origin, direction, floor = self.flying
            idx = int((now - start) / EGG_FRAME_TIME)
            if idx >= len(EGG_ARC):
                x = clamp(origin + direction * EGG_ARC[-1][0], 0, WORLD_W - 1)
                row = support(x, floor)  # rolls off the ledge if she was sitting near the edge
                self.eggs.append({"x": x, "y": row, "born": now, "t0": now, "state": "egg", "ch": EGG})
                self.flying = None
                self.unlock("egg", now)
            else:
                dist, row = EGG_ARC[idx]
                self.flying_pos = (clamp(origin + direction * dist, 0, WORLD_W - 1), floor + row)

    def update_crumbs(self, now):
        for crumb in self.crumbs:
            if crumb["landed"] or now < crumb["next"]:
                continue
            if support(crumb["x"], crumb["y"]) == crumb["y"]:
                crumb["landed"] = True
            else:
                crumb["y"] += 1
                crumb["next"] = now + CRUMB_FALL

    def update_young(self, now):
        grown = []
        for slot, chick in enumerate(self.young):
            width = SPRITE_W[chick["stage"]]
            chick["bonus"] += GROWTH_PER_CRUMB * self.eat(chick["x"], width, chick["fy"])
            age = now - chick["born"] + chick["bonus"]
            if age >= GROW_TO_DUCK:
                grown.append(chick)
                continue
            if age >= GROW_TO_DUCKLING:
                chick["stage"] = "duckling"

            mode = chick["mode"]
            if mode == "follow" and chick["trait"] == "adventurous" and now >= chick["next_adventure"]:
                chick["next_adventure"] = now + random.uniform(6, 12)
                if random.random() < 0.5:
                    mode = chick["mode"] = "wander"
                    chick["target"] = clamp(self.x + random.randint(-WANDER_RANGE, WANDER_RANGE), 0, WORLD_W - width)
                    chick["mode_until"] = now + random.uniform(4, 8)
            if mode == "wander" and (chick["x"] == chick["target"] or now >= chick["mode_until"]):
                far = abs(chick["x"] - self.x) > LOST_DIST
                mode = chick["mode"] = "lost" if far and chick["trait"] == "adventurous" else "follow"
                chick["next_peep"] = now

            if now >= chick["next_peep"]:
                chick["peep_text"], chick["peep_until"] = "peep!", now + 0.8
                chick["next_peep"] = now + (random.uniform(1.2, 2.2) if mode == "lost" else random.uniform(6, 14))

            if mode == "lost" and abs(chick["x"] - self.x) <= FOUND_DIST:
                mode = chick["mode"] = "follow"
                chick["peep_text"], chick["peep_until"] = "!", now + 0.8
                self.unlock("rescue", now)

            self.fall(chick, width)
            if now < chick["next"]:
                continue
            self.climb(chick, width)
            crumb = self.nearest_crumb(chick["x"] + width // 2, chick["fy"])
            butterflies = [f for f in self.friends if f["kind"] == "butterfly"
                           and abs(f["x"] - chick["x"]) < CHASE_DIST and abs(f["y"] - chick["fy"]) < 8]
            if crumb:
                target = crumb["x"] - 1
            elif butterflies and mode != "lost":
                target = min(butterflies, key=lambda f: abs(f["x"] - chick["x"]))["x"]
            elif mode == "wander":
                target = chick["target"]
            elif mode == "lost":
                target = chick["x"]
            else:
                gap = CHICK_GAP * (slot + 1)
                target = self.x - gap if self.facing > 0 else self.x + DUCK_W + gap - 3
            target = clamp(target, 0, WORLD_W - width)
            if chick["x"] != target:
                chick["facing"] = 1 if target > chick["x"] else -1
                step = chick["x"] + chick["facing"]
                if support(step + width // 2, chick["fy"]) > chick["fy"] and self.floor <= chick["fy"]:
                    chick["next"] = now + CHICK_IDLE_HOP_INTERVAL  # won't leave a ledge unless mama is below
                else:
                    chick["x"] = step
                    chick["next"] = now + CHICK_INTERVAL
            else:
                chick["next"] = now + CHICK_IDLE_HOP_INTERVAL  # keep hopping in place
            chick["hop"] = not chick["hop"]

        for chick in grown:
            self.unlock("mama", now)
            self.young.remove(chick)
            self.adults.append(new_adult(chick["x"], chick["facing"], now, chick["fy"]))

    def fall(self, e, width):
        if support(e["x"] + width // 2, e["fy"]) > e["fy"]:
            e["fy"] += 1

    def climb(self, chick, width):
        # hop up a ledge to follow mama
        center = chick["x"] + width // 2
        above = chick["fy"] - STEP
        if self.floor < chick["fy"] and abs(center - self.center()) <= CLIMB_RANGE and support(center, above) == above:
            chick["fy"] = above

    def update_adults(self, now):
        for adult in self.adults:
            self.eat(adult["x"], ADULT_W, adult["fy"])
            self.fall(adult, ADULT_W)
            if now < adult["next"]:
                continue
            adult["next"] = now + ADULT_INTERVAL
            crumb = self.nearest_crumb(adult["x"] + ADULT_W // 2, adult["fy"])
            if crumb:
                target = crumb["x"] - ADULT_W // 2
            elif adult["target"] is None and now >= adult["pause_until"]:
                target = adult["target"] = adult["x"] + random.randint(-WANDER_RANGE, WANDER_RANGE)
            else:
                target = adult["target"]
            if target is None:
                continue
            target = clamp(target, 0, WORLD_W - ADULT_W)
            if adult["x"] != target:
                adult["facing"] = 1 if target > adult["x"] else -1
                step = adult["x"] + adult["facing"]
                if support(step + ADULT_W // 2, adult["fy"]) > adult["fy"]:
                    adult["target"], adult["pause_until"] = None, now + random.uniform(1.5, 4)  # ledge edge
                else:
                    adult["x"] = step
            elif not crumb:
                adult["target"] = None
                adult["pause_until"] = now + random.uniform(1.5, 4)

    def update_weather(self, now):
        if now >= self.next_weather:
            self.set_weather(random.choice([w for w in WEATHERS if w != self.weather]), now)
        if self.weather not in ("rain", "snow") or now < self.next_particle:
            return
        self.next_particle = now + PARTICLE_TICK
        self.particle_tick += 1
        for p in self.particles:
            if self.weather == "rain" or self.particle_tick % 2 == 0:
                p[1] += 1
            if self.weather == "snow":
                p[0] = clamp(p[0] + random.choice((-1, 0, 1)), 0, self.view_w - 1)
        self.particles = [p for p in self.particles if p[1] < self.view_h]
        spawns = 3 if self.weather == "rain" else int(random.random() < 0.6)
        self.particles += [[random.randrange(self.view_w), 0] for _ in range(spawns)]

    # ---- friends --------------------------------------------------------------------------
    def spawn_friend(self, now, kind=None):
        kinds = [k for k in FRIENDS if (k != "fish" or self.pond_visible()) and (k != "frog" or self.ground_visible())]
        kind = kind or random.choice(kinds)
        cam, view = self.cam, self.view_w
        self.friends_met.add(kind)
        if self.friends_met >= set(FRIENDS):
            self.unlock("nature", now)
        friend = {"kind": kind, "next": now, "until": now + random.uniform(15, 30), "hop": False}
        if kind == "butterfly":
            side = random.choice((-1, 1))
            friend.update(x=cam - 2 if side < 0 else cam + view + 1,
                          y=clamp(random.randint(self.cam_y + 1, self.cam_y + self.view_h - 5), 0, GROUND - 1),
                          dx=-side, wing=0)
        elif kind == "frog":
            if self.pond_visible() and random.random() < 0.5:
                pond_x = random.choice(self.visible_ponds())
                low, high = max(pond_x, cam), min(pond_x + POND_W - 5, cam + view - 5)
            else:
                low, high = cam + 2, cam + view - 6
            friend.update(x=random.randint(low, max(low, high)), dir=random.choice((-1, 1)),
                          next_croak=now + random.uniform(3, 8), croak_until=0.0)
        else:
            pond_x = random.choice(self.visible_ponds() or PONDS)
            x = random.randint(pond_x + 3, pond_x + POND_W - 8)
            friend.update(x=x, t0=now, dir=random.choice((-1, 1)), pos=(x, GROUND - 1))
            self.add_splash(x, now)
        self.friends.append(friend)

    def update_friends(self, now):
        if self.flood is not None:
            return  # no butterflies or frogs in the flood tower
        if now >= self.next_friend:
            self.next_friend = now + random.uniform(*FRIEND_EVERY)
            if len(self.friends) < MAX_FRIENDS:
                self.spawn_friend(now)
        for friend in self.friends[:]:
            getattr(self, "update_" + friend["kind"])(friend, now)

    # ---- predators ------------------------------------------------------------------------
    def prey(self, kind):
        """Chicks and eggs a predator could take; foxes only reach the ground floor."""
        found = [("chick", c, c["x"] + SPRITE_W[c["stage"]] // 2, c["fy"]) for c in self.young]
        found += [("egg", e, e["x"], e["y"]) for e in self.eggs if e["state"] == "egg"]
        return [p for p in found if kind == "hawk" or p[3] == GROUND]

    def spawn_predator(self, now, kind=None):
        if self.predator:
            return
        kinds = [k for k in ("fox", "hawk") if self.prey(k) and (k == "hawk" or self.ground_visible())]
        kind = kind or random.choice(kinds or ["hawk"])
        side = random.choice((-1, 1))
        x = self.cam - 10 if side < 0 else self.cam + self.view_w + 3
        self.predator = {"kind": kind, "x": x, "y": self.cam_y + 2, "dir": -side, "state": "hunt",
                         "next": now, "target": None}
        self.notice = (f"Look out! A {kind}!", now + NOTICE_TIME)

    def update_predator(self, now):
        p = self.predator
        if p is None:
            if now >= self.next_predator:
                self.next_predator = now + random.uniform(*PREDATOR_EVERY)
                if self.young or self.eggs:
                    self.spawn_predator(now)
            return
        if now < p["next"]:
            return
        hawk = p["kind"] == "hawk"
        p["next"] = now + (0.06 if hawk else 0.08)
        width = HAWK_W if hawk else FOX_W
        center = p["x"] + width // 2

        if p["state"] == "hunt" and self.shown > 0 and abs(center - self.center()) <= SCARE_DIST:
            p["state"] = "flee"
            p["dir"] = 1 if center >= self.center() else -1
            self.unlock("scare", now)
            self.notice = ("Quack! It ran away!", now + NOTICE_TIME)

        if p["state"] == "flee":
            p["x"] += p["dir"] * (2 if hawk else 1)
            if hawk:
                p["y"] = max(self.cam_y + 1, p["y"] - 1)
            if self.off_screen(p["x"], 12):
                self.predator = None
            return

        # hunting: pick (or keep) a target
        options = self.prey(p["kind"])
        target = next((o for o in options if o[1] is p["target"]), None)
        if target is None:
            if not options:
                p["state"] = "flee"
                return
            target = min(options, key=lambda o: abs(o[2] - center))
            p["target"] = target[1]
        _, thing, tx, trow = target
        for chick in self.young:  # the chicks know trouble when they see it
            if abs(chick["x"] - center) < 15 and now >= chick["peep_until"]:
                chick["peep_text"], chick["peep_until"] = "eep!", now + 0.6

        dx = tx - center
        if hawk:
            if p["state"] == "hunt":
                p["y"] = self.cam_y + 2
                if abs(dx) <= 1:
                    p["state"] = "dive"
            if p["state"] == "dive":
                p["y"] += 1
        if abs(dx) > 1:
            p["dir"] = 1 if dx > 0 else -1
            p["x"] += p["dir"]
        caught = (hawk and p["state"] == "dive" and p["y"] + 1 >= trow - 1) or (not hawk and abs(dx) <= 2)
        if caught:
            if target[0] == "chick":
                self.young.remove(thing)
                self.notice = (f"Oh no! A {p['kind']} took a chick!", now + NOTICE_TIME)
            else:
                self.eggs.remove(thing)
                self.notice = (f"Oh no! A {p['kind']} took an egg!", now + NOTICE_TIME)
            p["state"], p["target"] = "flee", None
            p["dir"] = 1 if center >= self.center() else -1

    def off_screen(self, x, margin=4):
        return x < self.cam - margin or x > self.cam + self.view_w + margin

    def update_butterfly(self, f, now):
        if now < f["next"]:
            return
        f["next"] = now + 0.15
        f["wing"] ^= 1
        leaving = now >= f["until"]
        if leaving:
            f["dx"] = 1 if f["x"] > self.cam + self.view_w / 2 else -1
        else:
            if random.random() < 0.1:
                f["dx"] = -f["dx"]
            if f["x"] < self.cam:
                f["dx"] = 1
            elif f["x"] >= self.cam + self.view_w:
                f["dx"] = -1
        f["x"] += f["dx"]
        f["y"] = clamp(f["y"] + random.choice((-1, 0, 0, 1)), self.cam_y, min(GROUND - 1, self.cam_y + self.view_h - 4))
        if leaving and self.off_screen(f["x"]):
            self.friends.remove(f)

    def update_frog(self, f, now):
        if now < f["next"]:
            return
        leaving = now >= f["until"]
        f["next"] = now + 0.4
        f["hop"] = False
        if leaving:
            f["dir"] = 1 if f["x"] > self.cam + self.view_w / 2 else -1
        elif random.random() < 0.4:
            return  # rest
        elif random.random() < 0.3:
            f["dir"] = -f["dir"]
        f["x"] = clamp(f["x"] + f["dir"], -8, WORLD_W + 8)
        f["hop"] = True
        if now >= f["next_croak"]:
            f["croak_until"] = now + 1.0
            f["next_croak"] = now + random.uniform(6, 12)
        if leaving and self.off_screen(f["x"], 6):
            self.friends.remove(f)

    def update_fish(self, f, now):
        idx = int((now - f["t0"]) / FISH_FRAME)
        if idx >= len(FISH_ARC):
            self.add_splash(f["x"] + f["dir"] * FISH_ARC[-1][0], now)
            self.friends.remove(f)
        else:
            dist, row = FISH_ARC[idx]
            f["pos"] = (f["x"] + f["dir"] * dist, row)

    # ---- status line and mini-map ----------------------------------------------------------
    def status(self):
        if self.level == 1:  # only what the level asks for
            got = len(COINS) - len(self.coins)
            return [to_ansi([(ch, C_COIN) for ch in f"{COIN} {got}/{len(COINS)}"]), ""]
        def meter(label, value, width=10, bad=False):
            color = "91" if value < HUNGRY_BELOW or bad else "92"
            return [(ch, color if ch == "#" else None) for ch in f"{label} [{bar(value, width)}]"]

        got = len(COINS) - len(self.coins)
        text = [(ch, C_ACHIEVEMENT) for ch in f"Lv{self.level}"] + [(" ", None)] * 2
        text += [(ch, C_COIN) for ch in f"{COIN} {got}/{len(COINS)}"]
        row = text
        if self.survival:
            row += [(" ", None)] * 3 + meter("Fed", self.fullness) + [(" ", None)] * 3 + meter("Happy", self.happiness)
        row += [(" ", None)] * 3 + meter("HP", self.health * 100 / MAX_HEALTH, 6)
        if self.level in (LAST_LEVEL, GRAND_LEVEL):  # running only exists in the full game, the umbrella glide also on the grand tour
            row += [(" ", None)] * 3 + meter("Run" if self.level == LAST_LEVEL else "Glide", self.stamina, 6, self.tired)
        if self.flood is None:
            if PONDS:  # no lakes, no air meter
                row += [(" ", None)] * 3 + meter("Tank" if "tank" in self.inventory else "Air", self.breath / self.breath_max() * 100, 6)
            if self.level not in NO_LIVES_LEVELS:
                row += [(" ", None)] * 3 + [(ch, "91") for ch in "\u2665" * self.lives + "-" * (MAX_LIVES - self.lives)]
        else:  # the flood level has no air meter or lives: three seconds under the water is fatal
            rows_to_water = self.flood - self.feet
            text = "DROWNING!" if self.submerged() else f"Water {max(rows_to_water, 0)} below"
            row += [(" ", None)] * 3 + [(ch, "91" if rows_to_water < 6 else C_WATER) for ch in text]
        row += [(" ", None)] * 3 + [(ch, C_PEARL) for ch in f"{PEARL} {self.pearls_found}"]
        row += [(" ", None)] * 3 + [(ch, C_GEM) for ch in f"{GEM} {self.gems}"]
        row += [(" ", None)] * 3 + [(ch, C_PEA) for ch in f"Peas {self.ammo}"]
        return [to_ansi(row), to_ansi(self.minimap())]

    def minimap(self):
        n = self.view_w
        scale = WORLD_W / n
        blocks = " ▁▂▃▄▅▆▇█"
        view_lo, view_hi = int(self.cam / scale), int((self.cam + self.view_w) / scale)
        cells = []
        for i in range(n):
            x0, x1 = int(i * scale), max(int(i * scale) + 1, int((i + 1) * scale))
            level = max(LEDGE_LEVEL[x0:x1])
            if level:
                cell = [blocks[min(8, -(-level * 8 // MAX_LEVEL))], "38;5;130"]
            elif is_water(x0):
                cell = ["~", "34"]
            else:
                cell = ["_", "32"]
            cells.append(cell)
        for chick in self.young + self.adults:
            cells[min(n - 1, int(chick["x"] / scale))] = ["c", "33"]
        cells[min(n - 1, int(self.center() / scale))] = ["D", C_GOLD]
        for i in range(view_lo, min(n, view_hi + 1)):  # the visible part of the world
            cells[i][1] += ";7"
        return [tuple(c) for c in cells]

    # ---- drawing --------------------------------------------------------------------------
    def squish_grass(self, put, now):
        """Level 1: a patch of the green ground line that dents under the duck and wobbles back."""
        me = self.center()
        on_patch = self.feet == GROUND and SQUISH_PATCH[0] <= me <= SQUISH_PATCH[1]
        if on_patch:
            self.squish_at, self.squish_x = now, me
        age = now - getattr(self, "squish_at", -99.0)
        for x in range(SQUISH_PATCH[0], SQUISH_PATCH[1] + 1):  # the grass line dents under her and wobbles back
            dent = max(0, 4 - abs(x - getattr(self, "squish_x", 0))) if age < SQUISH_TIME else 0
            if dent and on_patch:
                put(x, GROUND + 1, "_" if dent > 2 else "-", C_GRASS)
            elif dent:
                put(x, GROUND + 1, "-~"[int(age * 14 + x) % 2], C_GRASS)

    def draw_hidden(self, put, now):
        """Level 4's invisible ledges spread out from where she landed, with a sparkle at the leading edge."""
        if not self.gem_taken and self.gem_visible():
            put(GEM_SPOTS[self.level][0], GEM_SPOTS[self.level][1], GEM, C_GEM if int(now * 3) % 2 else "95")
        for p, (t0, cx) in self.revealed.items():
            reach = (now - t0) * REVEAL_SPEED
            for x in range(p[0], p[1] + 1):
                if abs(x - cx) <= reach:
                    put(x, p[2] + 1, "=", C_GEM)
                elif abs(x - cx) <= reach + 3:
                    put(x, p[2] + 1, "*", C_STAR)

    def draw_cavern(self, put, now):
        """The rock under the grass with the cavern carved out of it (levels 1 and 7; only drawn once the camera has scrolled down)."""
        mer = self.level == MERMAID_LEVEL
        x0, x1 = (MER_X0, MER_X1) if mer else (CH_X0, CH_X1)
        gx, gy = GEM_SPOTS[self.level]
        open_to = x1  # the mermaid's hidden room is solid rock until it opens
        if mer:
            open_to = ROOM_X0 - 1 if self.room_open is None else min(x1, ROOM_X0 - 1 + int((now - self.room_open) * ROOM_OPEN_SPEED))
            for dy, line in enumerate(MERMAID):
                for dx, ch in enumerate(line):
                    put(MERMAID_X + dx, CH_FLOOR - 3 + dy, ch, "96")
            if self.mermaid_t0 is not None and self.room_open is None:
                for i, dx in enumerate((-1, 2, 5)):
                    put(MERMAID_X + dx, CH_FLOOR - 5 - int(now * 2 + i) % 3, "\u2665", "91")
            if self.mermaid_t0 is not None and now - self.mermaid_t0 < MERMAID_REVIVE + 2.0:
                for i, ch in enumerate(MERMAID_SAYS):
                    put(MERMAID_X - 10 + i, CH_FLOOR - 9, ch, "1;96")
        if not self.gem_taken and (not mer or open_to >= gx):
            put(gx, gy, GEM, C_GEM if int(now * 3) % 2 else "95")
        for i, ch in enumerate("Climb the stairs to get out" if mer else "Climb the stairs on the left to get out"):
            put(x0 + (22 if mer else 4) + i, CH_TOP + 2, ch, C_HINT)
        for y in range(max(self.cam_y, GROUND + 2), min(self.cam_y + self.view_h, WORLD_H - 1) + 1):
            for x in range(int(self.cam), int(self.cam) + self.view_w + 1):
                if x0 <= x <= min(x1, open_to) and CH_TOP <= y <= CH_FLOOR + 1:
                    put(x, y, "V" if y == CH_TOP and x % 7 == 0 else "\u00a0", C_ROCK)
                elif (x * 5 + y * 3) % 17 == 0:
                    put(x, y, "*", "35")
                else:
                    put(x, y, "#", C_ROCK)

    def draw_birds(self, put, now):
        """Flocks of birds cross the sky (levels 1 and 4): (every seconds, crossing seconds, time offset, row, direction)."""
        for period, cross, offset, row, direction in BIRD_FLOCKS[self.level]:
            t = (now + offset) % period
            if t < cross:
                progress = int(t / cross * (WORLD_W + 20))
                lead = WORLD_W + 4 - progress if direction < 0 else progress - 16
                for i, (dx, dy) in enumerate(((0, 0), (4, 1), (8, -1), (11, 1))):
                    put(lead + dx, row + dy, "v^"[int(now * 3 + i) % 2], C_BIRD)

    def draw_level1_decor(self, put, now):
        """A passing flock of birds and an occasional twinkle on a dollar (all just decoration)."""
        self.draw_birds(put, now)
        for x, y in self.coins:
            if (now + x * 3.7) % COIN_TWINKLE_PERIOD < 0.4:
                put(x, y - 1, "*", C_STAR)

    def frame(self, now):
        grid = [[BLANK] * WORLD_W for _ in range(WORLD_H)]

        solid = set()  # blank cells inside sprites that must hide scenery behind them

        def put(x, y, ch, color=None):
            if 0 <= x < WORLD_W and 0 <= y < WORLD_H and ch != " " and grid[y][x][0] == " " and (x, y) not in solid:
                grid[y][x] = (ch, color)

        def put_text(x, y, text, color=None):
            for dx, ch in enumerate(text):
                put(x + dx, y, ch, color)

        def put_sprite(x, bottom, lines, color=None, opaque=False):
            for dy, line in enumerate(lines):
                y = bottom - len(lines) + 1 + dy
                for dx, ch in enumerate(line):
                    put(x + dx, y, ch, color(dy, dx, ch) if callable(color) else color)
                if opaque and line.strip():
                    lo, hi = len(line) - len(line.lstrip()), len(line.rstrip())
                    solid.update((x + dx, y) for dx in range(lo, hi))

        sleeping = self.sleeping(now)
        celebrating = self.celebrate_start is not None
        facing = self.facing
        in_pond = self.in_pond()
        diving = self.sitting and in_pond
        crouch = self.sitting and not in_pond
        drop = 2 if crouch else 1 if (self.sitting or in_pond) else 0
        top = self.feet - 2 + self.depth if diving else self.feet - (DUCK_H - 1) + drop
        sink = 0 if self.drowned is None or self.float_t0 is not None else min(DROWN_SINK, int((now - self.drowned) / 0.15))
        top += sink

        behavior = self.behavior[0] if self.behavior else None
        eye = "x" if self.drowned is not None else "-" if sleeping or behavior == "blink" else "o"
        preen = 1 + int((now - self.behavior[1]) / 0.3) % 2 if behavior == "preen" else 0
        look = -facing if behavior == "look" else facing
        lines = duck_lines(self.shown > 0, look, self.step, eye, preen, feet=not drop,
                           shades=self.hat == "shades")
        if crouch:
            lines = lines[1:]  # squashed down, with the head still showing
        if diving:
            lines = lines[:2]  # only the head stays above the water

        def duck_color(dy, dx, ch):
            if dy == 1 and ch in "<>v":
                return C_BEAK
            if ch == "=" and dy == 1:
                return C_SHADES
            if dy == 4:
                return C_BEAK
            if celebrating:
                return RAINBOW[(dx + int(now * 10)) % len(RAINBOW)]
            if self.submerged():
                return C_DROWNING
            if now < self.invuln_until and int(now * 10) % 2:
                return "91"  # hurt flash
            return C_GOLD if self.golden else C_DUCK

        put_sprite(self.x, top + len(lines) - 1, lines, duck_color, opaque=True)
        if self.gliding:
            canopy = UMBRELLA_GLIDE[1][int(now * 8) % 3]
            hat_h = len(HATS[self.hat][0]) if self.hat in HATS and HATS[self.hat] else 0
            base = top - 1 - hat_h
            put_text(self.x, base - 2, UMBRELLA_GLIDE[0], C_ITEM)
            put_text(self.x, base - 1, canopy, C_ITEM)
            put_text(self.x, base, UMBRELLA_GLIDE[2], C_ITEM)
        hat = "crown" if celebrating else self.hat
        if hat in HATS and HATS[hat]:
            art, color = HATS[hat]
            put_sprite(self.x, top - 1, sprite([("  " + line).ljust(DUCK_W) for line in art], look), color)

        def label_x(text):
            return self.x + DUCK_W + 1 if facing > 0 else self.x - 1 - len(text)

        if sleeping:
            phase = int(now * 1.5) % 3
            front = self.x + DUCK_W + 1 if facing > 0 else self.x - 2
            if phase < 2:
                put(front, top - 1, "z", C_ZZZ)
            if phase > 0:
                put(front + 1, top - 2, "Z", C_ZZZ)
        elif now < self.nom_until:
            put_text(label_x("nom"), top - 1, "nom", C_TEXT)
        elif now < self.thought[1]:
            label = f"({self.thought[0]})"
            put_text(label_x(label), top - 1, label, C_TEXT)

        if self.flying_pos:
            put(*self.flying_pos, EGG, C_EGG)
        for egg in self.eggs:
            put(egg["x"], egg["y"], egg["ch"], C_EGG)
        for crumb in self.crumbs:
            put(crumb["x"], crumb["y"], CRUMB, C_CRUMB)
        for x0, floor in MUSHROOMS:
            squashed = now - self.plunged.get((x0, floor), -9) < MUSH_PLUNGE
            put_sprite(x0, floor, MUSHROOM_SQUASHED if squashed else MUSHROOM, lambda dy, dx, ch: C_MUSHROOM if dy == 0 else "97")
        if self.level == 10 and self.gem_visible() and not self.gem_taken:
            put(*GEM_SPOTS[10], GEM, C_GEM if int(now * 3) % 2 else "95")
        if self.level == 6 and self.secret_shown and not self.gem_taken:
            put(*SECRET_GEM, GEM, C_GEM if int(now * 3) % 2 else "95")
        if self.wind and now >= self.wind["start"]:
            for k in range(40):  # streaks race past, leaving the hint column on the left readable
                row = 2 + (k * 7) % (WIND_ROW - 1)
                x = 45 + int(k * 41 + (now - self.wind["start"]) * 45 * self.wind["dir"]) % (WORLD_W - 49)
                put_text(x, row, "~~~~", C_WIND)
        for e in self.enemies:
            if e["kind"] == "beetle":
                flinch = e.get("hit", 0) > now
                eyes = BEETLE_FLINCH if flinch else BEETLE_HURT_EYES[min(BEETLE_HP - e["hp"], len(BEETLE_HURT_EYES) - 1)]
                put_sprite(e["x"], e["y"], [BEETLE_TOP[0], eyes, BEETLE_LEGS[e["step"] % 2]], "1;97" if flinch else C_BEETLE)
            elif e["kind"] == "hedgehog":
                flinch = e.get("hit", 0) > now
                if e["state"] in ("roll", "ball"):
                    lines = HEDGEHOG_BALL[e["step"] % 2 if e["state"] == "roll" else 0]
                else:
                    lines = HEDGEHOG_CURLING if e["state"] == "curl" else sprite(HEDGEHOG_WALK, e["dir"])
                put_sprite(e["x"], e["y"], lines, "1;97" if flinch else C_HEDGEHOG)
            elif e["kind"] == "armadillo":
                flinch = e.get("hit", 0) > now
                put_sprite(e["x"], e["y"], sprite(ARMADILLO[e["step"] % 2], e["dir"]), "93" if flinch else C_ARMADILLO)
            elif e["kind"] == "mite":
                stunned = now < e["stun"]
                put_sprite(e["x"], e["y"], [MITE_STUNNED if stunned else MITE_TOP, MITE_LEGS[0] if stunned else MITE_LEGS[e["step"] % 2]], "93" if stunned else C_MITE)
                if stunned:
                    put_text(e["x"], e["y"] - 2, MITE_STARS[int(now * 4) % 2], "93")
            else:
                put_text(e["x"], e["y"], BAT_FRAMES[int(now * 8) % 2], C_BAT)
        for key, (x, y) in self.item_spots.items():
            put_text(x - 1, y, ITEMS[key][1], C_ITEM)
        for x, y in self.packs:
            put_text(x - 1, y, "(o)", C_PEA)
        for x, y in self.coins:  # after the enemies: put() keeps whatever was drawn first, so enemies cover coins
            put(x, y, COIN, C_COIN)
        for pea in self.peas:
            put(pea["x"], pea["y"], "o", C_BOUNCED if pea.get("hostile") else C_PEA)

        for f in self.friends:
            if f["kind"] == "butterfly":
                put_text(f["x"], f["y"], BUTTERFLY[f["wing"]], C_BUTTERFLY)
            elif f["kind"] == "frog":
                y = GROUND - (1 if f["hop"] else 0)
                put_text(f["x"], y, FROG, C_FROG)
                if now < f["croak_until"]:
                    put_text(f["x"] - 1, y - 1, "ribbit", C_TEXT)
            else:
                x, y = f["pos"]
                put_text(x, y, sprite([FISH], f["dir"])[0], C_FISH)

        if self.predator:
            p = self.predator
            if p["kind"] == "fox":
                put_sprite(p["x"], GROUND, sprite(FOX, p["dir"]), C_FOX)
            else:
                put_sprite(p["x"], p["y"] + 1, sprite(HAWK[int(now * 6) % 2], p["dir"]), C_HAWK)

        for chick in self.young:
            lines = sprite(CHICK if chick["stage"] == "chick" else DUCKLING, chick["facing"])
            bottom = chick["fy"] - (1 if chick["hop"] else 0)
            put_sprite(chick["x"], bottom, lines, C_CHICK if chick["stage"] == "chick" else C_DUCKLING)
            if now < chick["peep_until"]:
                put_text(chick["x"] - 1, bottom - len(lines), chick["peep_text"], C_CHICK)
        for adult in self.adults:
            put_sprite(adult["x"], adult["fy"], sprite(ADULT, adult["facing"]), C_ADULT)

        for i in range(min(self.shown, len(self.quack_texts))):
            u, y = quack_pos(i)
            x = self.x + u if facing > 0 else self.x + 3 - u
            put_text(x, top + y, self.quack_texts[i], C_QUACK)
        for u, y, ch in self.sparkles:
            x = self.x + u if facing > 0 else self.x + DUCK_W - 1 - u
            put(x, top + y, ch, C_BUBBLE if ch in BUBBLES else C_STAR)

        for x, born in self.splashes:
            idx = int((now - born) / SPLASH_FRAME)
            for dx in (-3, -1, 1, 3):
                height = SPLASH_ARC[min(idx, len(SPLASH_ARC) - 1)] - (abs(dx) // 3)
                put(x + dx, GROUND - 1 - max(0, height), "'" if abs(dx) == 3 else "°", C_SPLASH)
        for x, born in self.ripples:
            put(x, GROUND, RIPPLE_FRAMES[int((now - born) / RIPPLE_FRAME_TIME)], C_RIPPLE)
        wave = int(now * 3)
        for pond_x in PONDS:
            for x in range(pond_x, pond_x + POND_W):
                put(x, GROUND, "-" if (x + wave) % 3 == 0 else "~", C_WATER)

        lo, hi = int(self.cam) - 12, int(self.cam) + self.view_w + 12  # only draw what the camera can see
        for m in self.movers:  # sliding ledges are drawn first so they pass in front of trees
            glint = self.level == 5 and m is self.movers[1] and self.hidden[0] not in self.revealed and not self.airborne \
                and self.feet == m["floor"] and m["x0"] <= self.center() <= m["x0"] + 3  # hint: its left 4 = glow faintly under her feet
            for x in range(max(m["x0"], lo), min(m["x0"] + m["w"] - 1, hi) + 1):
                glow = glint and 0 <= x - m["x0"] - int(now * 0.8) % 3 <= 1
                if m.get("cloud"):
                    put(x, m["floor"] + 1, "~", "97")
                    for dy, row in ((0, " (~~~~~~) "), (-1, "   .--.   ")):  # a rounded, fluffy top (the duck is drawn in front of it)
                        put(x, m["floor"] + dy, row[x - m["x0"]], "97")
                    put(x, m["floor"] + 2, "'" if (x + int(now * 4)) % 3 == 0 else " ", C_WATER)  # rain falls from it
                else:
                    put(x, m["floor"] + 1, "=", "35" if glow else C_PLATFORM)
        for x in TREES:
            if lo <= x <= hi:
                put_sprite(x, GROUND, TREE, lambda dy, dx, ch: C_TRUNK if dy >= 2 else C_LEAF)
        for x, color in FLOWERS:
            if lo <= x <= hi:
                put(x, GROUND, "*", color)
        near = {p for bucket in PLATFORMS_BY_X[max(0, lo) // BUCKET:max(0, hi) // BUCKET + 1] for p in bucket}
        for x0, x1, floor in near:
            if (x0, x1, floor) in self.hidden:
                continue
            hint = HINT_LEDGES.get(self.level)
            glint = hint and (x0, x1, floor) == hint[0] and self.hidden[0] not in self.revealed and not self.airborne and self.feet == floor \
                and (x0 <= self.center() <= x0 + 3 if hint[1] == "left" else x1 - 3 <= self.center() <= x1)
            for x in range(max(x0, lo), min(x1, hi) + 1):
                if glint and 0 <= (x - x0 if hint[1] == "left" else x1 - x) - int(now * 0.8) % 3 <= 1:  # a hint: two neighbouring = within the end 4 faintly turn pink
                    put(x, floor + 1, "=", "35")
                else:
                    put(x, floor + 1, "=", C_ICE if self.ice_at(x) else C_PLATFORM)
        if self.hidden:
            self.draw_hidden(put, now)
        for x, y in self.pearls:
            if lo <= x <= hi:
                put(x, y, PEARL, C_PEARL)
        if self.level == 1:
            self.squish_grass(put, now)
        for x in range(max(0, lo), min(WORLD_W, hi + 1)):
            if not is_water(x):
                put(x, GROUND + 1, "=", C_ICE if self.ice_at(x) else C_GRASS)
        y_lo, y_hi = max(GROUND + 1, self.cam_y), min(GROUND + LAKE_DEPTH, self.cam_y + self.view_h)
        for pond_x in PONDS:
            for x in range(max(pond_x - CAVE_MARGIN, lo), min(pond_x + POND_W + CAVE_MARGIN, hi + 1)):
                for y in range(y_lo, y_hi + 1):
                    kind = CAVE.get((x, y))
                    if kind == "w":
                        put(x, y, "-" if (x + y + wave) % 4 == 0 else "~", C_WATER)
                    elif kind == "a":
                        put(x, y, ".", C_AIR)
                    elif y >= GROUND + 2:
                        put(x, y, "#", C_ROCK)

        if self.flood is not None:
            surface = int(self.flood)
            for fish in self.school:  # drawn before the water so they show through it
                if fish["y"] > surface and lo <= fish["x"] <= hi:
                    put_text(int(fish["x"]), fish["y"], sprite([FISH], fish["dir"])[0], C_FISH)
            for y in range(max(surface, self.cam_y), min(GROUND + 1, self.cam_y + self.view_h) + 1):
                for x in range(max(0, lo), min(WORLD_W, hi + 1)):
                    if y == surface:
                        put(x, y, "-" if (x + wave) % 3 == 0 else "~", C_WATER)
                    elif (x + y + wave) % 4 == 0:
                        put(x, y, "~", C_WATER)

        if self.drowned is not None:  # bubbles float up from the sinking duck
            age = now - self.drowned
            for i, dx in enumerate((-3, 0, 3, -1, 2)):
                rise = (age * 6 + i * 2.5) % 12
                y = int(self.feet - 2 + sink - rise)
                if y >= int(self.flood):
                    put(self.center() + dx, y, "o" if rise < 6 else ".", C_DROWNING)

        for x, row, text in HINTS_BY_LEVEL.get(self.level, ()):
            put_text(x, row, text, C_HINT)

        if self.level == 4:
            self.draw_birds(put, now)  # after the hints so the birds never cover them
        if self.level == 1:
            self.draw_level1_decor(put, now)
        if self.level in (1, MERMAID_LEVEL) and self.cam_y + self.view_h > GROUND + 2:
            self.draw_cavern(put, now)

        # screen-space layers: sky and weather ignore the world scroll
        view = [row[int(self.cam):int(self.cam) + self.view_w] for row in grid[self.cam_y:self.cam_y + self.view_h]]

        if celebrating and now - self.celebrate_start < SHAKE_TIME:
            for y, row in enumerate(view):
                shake = random.choice((-1, 0, 1))
                view[y] = row[shake:] + row[:shake] if shake else row

        def sky(x, y, ch, color):
            if 0 <= x < self.view_w and 0 <= y < self.view_h and ch != " " and view[y][x][0] == " ":
                view[y][x] = (ch, color)

        if celebrating:
            for x0, y0, born, color in self.bursts:
                age = now - born
                char = "*" if age < 0.45 * BURST_LIFE else "+" if age < 0.8 * BURST_LIFE else "."
                for ring, (count, speed) in enumerate(((16, 9), (8, 5))):
                    for i in range(count):
                        angle = 2 * math.pi * i / count + ring * 0.4
                        sky(x0 + round(math.cos(angle) * age * speed * 2),
                            y0 + round(math.sin(angle) * age * speed + 5 * age * age),
                            char, color if ring == 0 else "97")
            for x0, born, speed, char, color, phase in self.confetti:
                age = now - born
                sky(x0 + round(math.sin(age * 3 + phase) * 2), int(age * speed), char, color)

        for x, y in self.particles:
            if self.cam_y + y >= GROUND:  # weather stops at the ground, never falls underground
                continue
            sky(x, y, "'" if self.weather == "rain" else "*", C_RAIN if self.weather == "rain" else C_SNOW)
        if self.weather != "clear":
            drift = int(now / 0.8)
            for base in (6, 38, 70):
                x0 = (base + drift) % (self.view_w + 12) - 6
                for dy, line in enumerate(CLOUD):
                    for dx, ch in enumerate(line):
                        sky(x0 + dx, dy, ch, C_CLOUD)
        if sleeping:
            for dy, line in enumerate(MOON):
                for dx, ch in enumerate(line):
                    sky(self.view_w - 8 + dx, dy, ch, C_MOON)
            for i, (fraction, y) in enumerate(self.stars):
                sky(int(fraction * self.view_w), y, "*+."[(int(now * 2) + i) % 3], C_STAR)

        def columns(entries):
            # two columns when the list would not fit the screen's height
            if len(entries) + 6 <= self.view_h:
                return entries
            half = (len(entries) + 1) // 2
            left, right = entries[:half], entries[half:]
            w = max(len(e) for e in left)
            return [e.ljust(w) + "   " + (right[i] if i < len(right) else "") for i, e in enumerate(left)]

        def overlay(lines, color, top=None):
            color_of = color if callable(color) else (lambda dy, dx, ch: color)
            # drawn over everything, centred horizontally
            top = (self.view_h - len(lines)) // 2 if top is None else top
            for dy, line in enumerate(lines):
                line = line[:self.view_w]
                x0 = (self.view_w - len(line)) // 2
                for dx, ch in enumerate(line):
                    if 0 <= top + dy < self.view_h:
                        view[top + dy][x0 + dx] = (ch, color_of(dy, dx, ch))

        if now < self.toast[1]:
            overlay([f" {self.toast[0]} "], C_ACHIEVEMENT, top=0)
        elif self.level == 1 and self.level_done is None and len(self.unlocked) < len(self.achievements):
            overlay([f" {self.still_to_do()} "], C_ACHIEVEMENT, top=0)
        if now < self.notice[1]:
            overlay([f" {self.notice[0]} "], "1;91", top=1)
        if celebrating:
            width = max(len(line) for line in BANNER) + 6
            phase = int(now * 8)
            border = "".join("*+"[(i + phase) % 2] for i in range(width + 4))
            body = [f" * {line.center(width - 2)} * " for line in BANNER]
            overlay([border] + [" " * (width + 4)] + body + [" " * (width + 4), border],
                    lambda dy, dx, ch: RAINBOW[(dx + dy + phase) % len(RAINBOW)] if ch != " " else None,
                    top=max(0, self.view_h // 2 - 3))
        if self.level_done is not None and not self.game_over:
            phase = int(now * 8)
            overlay([f"  LEVEL {self.level} COMPLETE!  ", f"  get ready for level {self.level + 1}...  "],
                    lambda dy, dx, ch: RAINBOW[(dx + dy + phase) % len(RAINBOW)] if ch != " " else None,
                    top=max(0, self.view_h // 2 - 1))
        if self.game_over:
            overlay(["+---------------------------+", "|         GAME OVER         |",
                     "|  y: start over   q: quit  |", "+---------------------------+"], "1;91")
        elif self.died:
            overlay(["+------------------------------------+", "|           THE DUCK DIED            |",
                     "|  Press space to restart the level  |", "+------------------------------------+"], "1;91")
        elif self.drowned is not None and now - self.drowned >= DROWN_ANIM and not self.mermaid_pending:
            overlay(["+-----------------------------+", "|        YOU DROWNED!         |",
                     "|   Press space to restart    |", "+-----------------------------+"], "1;94")
        elif self.paused:
            overlay(["+-----------------+", "|     PAUSED      |", "|   p: resume     |", "+-----------------+"], C_TEXT)
        elif self.confirm_restart:
            overlay(["+----------------------------------+", "|  Restart this level?  (y / n)    |",
                     "+----------------------------------+"], C_TEXT)
        elif self.confirm_quit:
            overlay(["+---------------------+", "|  Quit?  (y / n)     |", "+---------------------+"], C_TEXT)
        elif self.test_menu:
            entries = [f"{'>' if i == self.menu_cursor else ' '} [{'x' if key in self.unlocked else ' '}] {title}"
                       for i, (key, title, _) in enumerate(self.achievements)]
            entries = columns(entries)
            width = max(len(e) for e in entries)
            rows = ["TEST MENU".center(width), ""] + entries
            rows += ["", "up/down  space: toggle".center(width),
                     "1-9, 0 (10), - (11), = (12), \\ (13), ] (14): jump to that level".center(width), "T / esc: close".center(width)]
            overlay(["+" + "-" * (width + 2) + "+"] + [f"| {row.ljust(width)} |" for row in rows]
                    + ["+" + "-" * (width + 2) + "+"], C_ACHIEVEMENT)
        elif self.show_inventory:
            slot = 15
            columns_ = []
            for key, (name, _, art, how) in ITEMS.items():
                have = key in self.inventory
                lines = [row.ljust(13) for row in art] if have else [" " * 13] * 2 + ["      ?      "] + [" " * 13] * 2
                columns_.append([row.center(slot) for row in lines] + [(name if have else "???").center(slot)])
            rows = ["INVENTORY".center(slot * 3), ""]
            rows += ["".join(col[i] for col in columns_) for i in range(len(columns_[0]))]
            rows += [""] + [f"{ITEMS[k][0]}: {ITEMS[k][3]}" if k in self.inventory else "???" for k in ITEMS]
            rows += ["", f"Pink gems: {self.gems}"]
            if self.level in GEM_HINTS:
                hint = "You've found this level's gem." if self.gem_taken else GEM_HINTS[self.level]
                rows += [""] + textwrap.wrap(f"Hint: {hint}", slot * 3)
            rows += ["", "press i to close".center(slot * 3)]
            width = max(len(row) for row in rows)
            overlay(["+" + "-" * (width + 2) + "+"] + [f"| {row.ljust(width)} |" for row in rows]
                    + ["+" + "-" * (width + 2) + "+"], C_ITEM)
        elif self.show_achievements:
            marks = [("x" if key in self.unlocked else " ", title, hint) for key, title, hint in self.achievements]
            full = [f"[{mark}] {title} - {hint}" for mark, title, hint in marks]
            entries = full if len(full) + 6 <= self.view_h else columns([f"[{m}] {t}" for m, t, _ in marks])
            width = max(len(e) for e in entries)
            header = (f"Level {self.level} achievements {len(self.unlocked)}/{len(self.achievements)}"
                      if len(self.unlocked) < len(self.achievements)
                      else "* ALL ACHIEVEMENTS UNLOCKED *")
            rows = [header.center(width), ""]
            rows += entries
            rows += ["", "press a to close".center(width)]
            overlay(["+" + "-" * (width + 2) + "+"] + [f"| {row.ljust(width)} |" for row in rows]
                    + ["+" + "-" * (width + 2) + "+"], C_TEXT)

        return [to_ansi(row) for row in view]


def bar(value, width=10):
    filled = round(value / 100 * width)
    return "#" * filled + "-" * (width - filled)


def to_ansi(row):
    while row and row[-1][0] == " ":
        row = row[:-1]
    if not USE_COLOR:
        return "".join(ch for ch, _ in row)
    out, current = [], None
    for ch, color in row:
        color = color if ch != " " else None
        if color != current:
            out.append(f"\x1b[{color}m" if color else "\x1b[0m")
            current = color
        out.append(ch)
    if current:
        out.append("\x1b[0m")
    return "".join(out)


class Input:
    """Turns raw terminal bytes into (key name, pressed) events."""

    def __init__(self, kitty):
        self.kitty = kitty
        self.held = {}  # fallback: key -> (last seen, repeating)

    def poll(self, data, now):
        return self.parse_kitty(data) if self.kitty else self.parse_plain(data, now)

    def parse_kitty(self, data):
        events = []
        for m in KITTY_EVENT.finditer(data):
            final, event = m.group(4), int(m.group(3) or 1)
            code = int(m.group(1) or 0)
            if int(m.group(2) or 1) - 1 & 1 and 97 <= code <= 122:  # shift: Kitty reports the unshifted key
                code -= 32
            name = KITTY_KEYS.get(code) if final == b"u" else ARROW_NAMES[final]
            if final != b"u" and event != 3:  # arrows carry the shift modifier
                events.append(("shift", bool(int(m.group(2) or 1) - 1 & 1)))
            if name and (event != 2 or name in HOLD_KEYS):
                events.append((name, event != 3))
        return events

    def parse_plain(self, data, now):
        # Without key-up events, a gap in key repeats means the key was released.
        names = []
        def arrow(m):
            names.append(("shift", bool(int(m.group(1) or 1) - 1 & 1)))
            names.append(ARROW_NAMES[m.group(2)])
            return b""

        rest = ARROW.sub(arrow, data)
        if rest == b"\x1b":
            names.append("quit")
        names += [PLAIN_KEYS[b] for b in rest if b in PLAIN_KEYS]

        events = []
        for name in names:
            if isinstance(name, tuple):
                events.append(name)
                continue
            if name not in HOLD_KEYS:
                events.append((name, True))
                continue
            last, repeating = self.held.get(name, (None, False))
            if last is None:
                events.append((name, True))
            repeating = last is not None and (repeating or now - last < REPEAT_GAP)
            self.held[name] = (now, repeating)
        for name, (last, repeating) in list(self.held.items()):
            if now - last > (REPEAT_GAP if repeating else FIRST_REPEAT_DELAY):
                del self.held[name]
                events.append((name, False))
        return events


HELP_LEVEL1 = ["Space: quack   Left/Right: walk   Up: jump   Down: sit / drop through a ledge   a: achievements   r: restart   p: pause   q / x / Esc: exit", ""]
HELP_LEVELS_4_TO_8 = ["Space: quack (shoot with the pea-shooter)   Left/Right: walk   Down: sit/float/dive   Up: jump/glide/surface",
                      "i: inventory   m: mute   w: weather   a: achievements   r: restart level   p: pause   q / x / Esc: exit"]
HELP = ["Space: quack (shoot with the pea-shooter)   Left/Right: walk (Shift: run)   Down: sit/float/dive   Up: jump/glide/surface   f: feed   h: hat",
        "i: inventory   m: mute   w: weather   a: achievements   r: restart level   p: pause   q / x / Esc: exit"]


def draw_help(cols, level):
    for i, line in enumerate(HELP_LEVEL1 if level == 1 else HELP if level == LAST_LEVEL else HELP_LEVELS_4_TO_8):
        sys.stdout.write(f"\x1b[{i + 1};1H\x1b[K{line[:cols]}")


def draw_status(lines):
    for i, line in enumerate(lines):
        sys.stdout.write(f"\x1b[{3 + i};1H{line}\x1b[0m\x1b[K")


def draw(frame):
    for i, line in enumerate(frame):
        sys.stdout.write(f"\x1b[{CANVAS_ROW + i};1H{line}\x1b[0m\x1b[K")
    sys.stdout.flush()


def supports_key_release(fd):
    # Kitty keyboard protocol: reports real key-up events (kitty, ghostty, WezTerm, iTerm2...)
    sys.stdout.write("\x1b[?u\x1b[c")
    sys.stdout.flush()
    reply = b""
    while select.select([fd], [], [], 0.3)[0]:
        reply += os.read(fd, 64)
        if reply.endswith(b"c"):
            break
    return b"\x1b[?" in reply and b"u" in reply.split(b"\x1b[?", 1)[1][:6]


class Sound:
    def __init__(self):
        self.players = []
        self.use_afplay = bool(shutil.which("afplay")) and os.path.exists(QUACK_SOUND)

    def coin(self):
        if self.use_afplay and os.path.exists(COIN_SOUND):
            self.players = [p for p in self.players if p.poll() is None]
            self.players.append(subprocess.Popen(["afplay", COIN_SOUND],
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def boing(self):
        if self.use_afplay and os.path.exists(BOING_SOUND):
            self.players = [p for p in self.players if p.poll() is None]
            self.players.append(subprocess.Popen(["afplay", BOING_SOUND],
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def fanfare(self):
        if self.use_afplay and os.path.exists(FANFARE_SOUND):
            self.players.append(subprocess.Popen(["afplay", FANFARE_SOUND],
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        else:
            self.quack()

    def quack(self):
        if not self.use_afplay:
            sys.stdout.write("\a")
            sys.stdout.flush()
            return
        self.players = [p for p in self.players if p.poll() is None]
        self.players.append(subprocess.Popen(["afplay", QUACK_SOUND],
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


def shift_rows(data, by):
    """Moves every row coordinate in an old save down by `by` rows."""
    try:
        data["coins"] = [[x, y + by] for x, y in data["coins"]]
        data["packs"] = [[x, y + by] for x, y in data.get("packs", [])]
        data["item_spots"] = {k: [v[0], v[1] + by] for k, v in data.get("item_spots", {}).items() if len(v) == 2}
        data["floor"] = int(data["floor"]) + by
        for key in ("young", "adults"):
            for c in data[key]:
                c["fy"] = int(c["fy"]) + by
        for e in data["eggs"]:
            e["y"] = int(e["y"]) + by
    except (KeyError, TypeError, ValueError):
        pass  # load_state rejects a broken save


SAVE_PATH = os.environ.get("DUCK_SAVE") or os.path.expanduser("~/.duck_save.json")
SAVE_EVERY = 20.0


def read_save():
    try:
        with open(SAVE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_save(world, now):
    try:
        tmp = SAVE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(world.save_state(now), f)
        os.replace(tmp, SAVE_PATH)
    except OSError:
        pass


TITLE_ART = r"""
__     ___ _            ____          _          _
\ \   / (_) |__   ___  / ___|___   __| | ___  __| |
 \ \ / /| | '_ \ / _ \| |   / _ \ / _` |/ _ \/ _` |
  \ V / | | |_) |  __/| |__| (_) | (_| |  __/ (_| |
   \_/  |_|_.__/ \___| \____\___/ \__,_|\___|\__,_|

   ____             _      ____
  |  _ \ _   _  ___| | __ / ___| __ _ _ __ ___   ___
  | | | | | | |/ __| |/ /| |  _ / _` | '_ ` _ \ / _ \
  | |_| | |_| | (__|   < | |_| | (_| | | | | | |  __/
  |____/ \__,_|\___|_|\_\ \____|\__,_|_| |_| |_|\___|
""".strip("\n").split("\n")

SPLASH_SCENE_H = 8  # butterfly sky, duck, ground


def splash_scene(width, tick):
    """Renders one frame of the walking-duck scene (built from the game's own sprites)."""
    grid = [[(" ", "")] * width for _ in range(SPLASH_SCENE_H)]

    def draw(x, bottom, lines, color, beak=None):
        for dy, line in enumerate(reversed(lines)):
            for dx, ch in enumerate(line):
                if ch != " " and 0 <= x + dx < width and 0 <= bottom - dy < SPLASH_SCENE_H:
                    grid[bottom - dy][x + dx] = (ch, beak if beak and ch == ">" else color)

    ground = SPLASH_SCENE_H - 1
    feet_row = ground - 1
    for x in range(width):
        grid[ground][x] = ("=", C_GRASS)
    for x in range(4, width, 9):
        grid[feet_row][x] = ("*", C_FLOWERS[(x // 9) % len(C_FLOWERS)])

    stop = width // 2 - 8  # where the duck ends up
    walking = tick < stop + DUCK_W
    duck_x = min(tick, stop + DUCK_W) - DUCK_W  # starts off the left edge
    draw(duck_x, feet_row, duck_lines(not walking and tick % 40 in (6, 7, 8), 1, tick // 3), C_DUCK, C_BEAK)

    for n in range(3):  # ducklings trail behind mama, a little further back each
        young = DUCKLING if n < 2 else CHICK
        x = duck_x - 6 - n * 5
        hop = 1 if (not walking and (tick // 4 + n) % 7 == 0) or (walking and (tick // 3 + n) % 2) else 0
        draw(x, feet_row - hop, sprite(young, 1), C_CHICK if n == 2 else C_DUCKLING, C_BEAK)

    frog_x = min(width - 7, width // 2 + 20)
    jump = 1 if tick % 40 in (10, 11, 12) else 0
    draw(frog_x, feet_row - jump, ["(-.-)" if tick % 30 > 27 else FROG], C_FROG)
    if not walking and 30 < tick % 60 < 45:
        draw(frog_x - 1, feet_row - 2, ["ribbit!"], C_TEXT)

    for n in range(2):  # butterflies flutter above the duck's head
        phase = tick * 0.12 + n * 3.1
        bx = duck_x + 4 + round(7 * math.sin(phase)) * (1 if n == 0 else -1) + n * 2
        by = 1 + round(math.sin(phase * 1.7 + n) * 0.9) + n
        draw(bx, by, [BUTTERFLY[(tick // 3) % 2]], C_BUTTERFLY)

    if not walking and tick % 24 < 8:  # a heart floats up from the ducklings now and then
        draw(stop - 8, feet_row - 3 - tick % 24 // 3, ["<3"], "91")

    return ["".join(f"\x1b[{c}m{ch}\x1b[0m" if c else ch for ch, c in row) for row in grid]


def term_size():
    """The live terminal size (shutil would trust a stale COLUMNS/LINES environment variable)."""
    try:
        return os.get_terminal_size(sys.stdout.fileno())
    except OSError:
        return shutil.get_terminal_size()


def too_small(size):
    return size.columns < MIN_COLS or size.lines < MIN_ROWS


def wait_for_size(fd):
    """Pauses until the terminal is at least MIN_COLS x MIN_ROWS, telling the user to resize it (q quits)."""
    shown = None
    while True:
        size = term_size()
        if not too_small(size):
            return
        if size != shown:
            shown = size
            narrow, short = size.columns < MIN_COLS, size.lines < MIN_ROWS
            wish = "larger" if narrow and short else "wider" if narrow else "taller"
            lines = [f"Please make your console {wish}.", "",
                     f"Vibe Coded Duck Game needs at least {MIN_COLS} columns x {MIN_ROWS} rows;",
                     f"this window is only {size.columns} wide x {size.lines} tall.", "", "(press q to quit)"]
            out = ["\x1b[0m\x1b[2J"]
            mid = size.lines // 2 + 1
            center = size.columns // 2 + 1
            if narrow:  # arrows on the side edges point outwards
                out.append(f"\x1b[{mid};1H\x1b[1;93m<----\x1b[0m")
                out.append(f"\x1b[{mid};{max(1, size.columns - 4)}H\x1b[1;93m---->\x1b[0m")
            if short:  # and arrows at the top and bottom
                for row, glyph in ((1, "^"), (2, "|"), (size.lines - 1, "|"), (size.lines, "v")):
                    out.append(f"\x1b[{row};{center}H\x1b[1;93m{glyph}\x1b[0m")
            top = max(1, (size.lines - len(lines)) // 2 + 1)
            for i, line in enumerate(lines):
                out.append(f"\x1b[{top + i};{max(1, (size.columns - len(line)) // 2 + 1)}H{line[:size.columns]}")
            sys.stdout.write("".join(out))
            sys.stdout.flush()
        if select.select([fd], [], [], 0.1)[0]:
            data = os.read(fd, 64)
            if b"q" in data or b"\x03" in data or b"\x04" in data or b"99;5u" in data:
                raise SystemExit


def paint_title(size):
    """Draws the static part of the splash; returns the rows used by the scene and the prompt."""
    logo_w = max(len(l) for l in TITLE_ART)
    total = len(TITLE_ART) + 1 + SPLASH_SCENE_H + 3
    top = max(1, (size.lines - total) // 2 + 1)
    out = ["\x1b[2J"]
    for i, line in enumerate(TITLE_ART):
        col = max(1, (size.columns - logo_w) // 2 + 1)
        out.append(f"\x1b[{top + i};{col}H\x1b[1;36m{line}\x1b[0m")
    scene_row = top + len(TITLE_ART) + 1
    prompt_row = scene_row + SPLASH_SCENE_H + 1
    name = "~ Vibe Coded Duck Game ~"
    out.append(f"\x1b[{prompt_row};{max(1, (size.columns - len(name)) // 2 + 1)}H\x1b[1;97m{name}\x1b[0m")
    sys.stdout.write("".join(out))
    return scene_row, prompt_row


def splash(fd):
    """Shows an animated title screen until a key is pressed."""
    size = None
    tick = 0
    while True:
        new_size = term_size()
        if new_size != size:
            if too_small(new_size):
                wait_for_size(fd)
                new_size = term_size()
            size = new_size
            scene_row, prompt_row = paint_title(size)
        rows = splash_scene(size.columns - 1, tick)
        frame = "".join(f"\x1b[{scene_row + i};1H{row}" for i, row in enumerate(rows))
        if tick % 20 < 14:
            hint = "press any key to start"
            frame += f"\x1b[{prompt_row + 1};{max(1, (size.columns - len(hint)) // 2 + 1)}H\x1b[2m{hint}\x1b[0m"
        else:
            frame += f"\x1b[{prompt_row + 1};1H\x1b[2K"
        sys.stdout.write(frame)
        sys.stdout.flush()
        if select.select([fd], [], [], 0.08)[0]:
            break
        tick += 1
    key = os.read(fd, 1)
    if key in (b"\x03", b"\x04"):
        raise SystemExit
    while select.select([fd], [], [], 0.05)[0]:
        os.read(fd, 64)  # swallow the rest of an escape sequence


def ask_resume(fd):
    """Asks whether to resume the saved game; returns True to resume."""
    wait_for_size(fd)
    sys.stdout.write("\x1b[2J\x1b[1;1HSaved game found.  r: resume   n: start over   q: quit")
    sys.stdout.flush()
    while True:
        key = os.read(fd, 1).lower()
        if key in (b"r", b"\r", b"\n"):
            return True
        if key == b"n":
            return False
        if key in (b"q", b"\x03", b"\x04"):
            raise SystemExit


def main():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    kitty = False
    world = None
    clk = {"off": 0.0, "at": None}  # game clock = real time minus time spent paused

    def gclock():
        return (clk["at"] if clk["at"] is not None else time.monotonic()) - clk["off"]

    sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[?25l")  # alternate screen: resizing can't corrupt scrollback
    try:
        tty.setcbreak(fd)
        splash(fd)
        saved = None if "--new" in sys.argv else read_save()
        if saved and not ask_resume(fd):
            saved = None
        sys.stdout.write("\x1b[2J")
        kitty = supports_key_release(fd)
        if kitty:
            sys.stdout.write("\x1b[>11u")  # disambiguate + event types + all keys

        level = 1
        if saved:  # saves from before levels were the old "level 2" game; before the tutorial level, levels were one lower
            version = saved.get("version", 1)
            level = saved.get("level", 2) + (1 if version < 2 else 0)
            if version < 3 and level >= 2:  # the moving-ledge level was inserted later
                level += 1
            if version < 4 and level in (2, 3):  # ...and then swapped with the arena level
                level = 5 - level
            if version < 5 and level >= 4:  # the mushroom level was inserted before the full game
                level += 1
            if version < 7 and level >= 5:  # the flood tower was inserted before the full game
                level += 1
            if version < 9 and level >= 5:  # the medium flood level was inserted before the flood tower
                level += 1
            if version < 10 and level >= 6:  # the combined level was inserted before the flood tower
                level += 1
        if saved and saved.get("version", 1) < 6:
            shift_rows(saved, SKY_ADDED)  # the sky grew, so every saved row moved down
        if saved and saved.get("version", 1) < 8:
            shift_rows(saved, SKY_EXTRA)
            if level == 7:
                saved = None  # the flood tower got taller, so an old save of it no longer fits; it starts over
        if saved and saved.get("version", 1) < 12 and level >= 8:
            level += 1  # the ice rink was inserted before the full game
        if saved and saved.get("version", 1) < 13 and level >= 9:
            level += 1  # the second ice rink was inserted before the full game
        if saved and saved.get("version", 1) < 14 and level >= 10:
            level += 1  # the grand tour was inserted before the full game
        if saved and saved.get("version", 1) < 11:
            shift_rows(saved, SKY_MORE)
            if level == 6:
                saved = None  # level 6 got taller, so an old save of it no longer fits; it starts over
        if saved and saved.get("version", 1) < 15 and level >= 2:
            level += 1  # the mite level was inserted as level 2
        if saved and saved.get("version", 1) < 16 and level >= 2:
            level += 1  # the small stunning level was inserted as level 2
        if saved and saved.get("version", 1) < 17 and level >= 9:
            level += 1  # the hedgehog level was inserted as level 9
        world = World(time.monotonic(), level if level in LEVEL_ACHIEVEMENTS else 1)
        if saved:
            try:
                world.load_state(saved, time.monotonic())
            except (KeyError, TypeError, ValueError):
                world = World(time.monotonic(), 1)  # ignore a damaged save
        next_save = time.monotonic() + SAVE_EVERY
        keys = Input(kitty)
        sound = Sound()
        size = None
        last_frame = last_status = None
        while True:
            new_size = term_size()
            if too_small(new_size):  # pause until the window is big enough again
                world.dirs, world.running, world.quack_start, world.up_held = [], False, None, False
                wait_for_size(fd)
                world.last_input = gclock()
                keys = Input(kitty)
                size = last_frame = last_status = None
                new_size = term_size()
            if new_size != size:
                size = new_size
                world.set_view(size.columns - 1, size.lines - CANVAS_ROW + 1)
                world.snap_camera()
                sys.stdout.write("\x1b[2J")
                draw_help(size.columns, world.level)
                last_frame = last_status = None

            ready, _, _ = select.select([fd], [], [], 0.01)
            real = time.monotonic()
            if world.paused and clk["at"] is None:
                clk["at"] = real
            elif not world.paused and clk["at"] is not None:
                clk["off"] += real - clk["at"]
                clk["at"] = None
            now = gclock()
            data = os.read(fd, 64) if ready else b""
            for name, pressed in keys.poll(data, now):
                if world.game_over:
                    if pressed and name in ("yes", "enter"):
                        world = World(now)
                        size = last_frame = last_status = None
                    elif pressed and name == "quit":
                        return
                    continue
                if name == "quit":
                    if pressed:
                        world.request_quit(now)
                else:
                    world.handle(name, pressed, now)
            if size is None:
                continue  # restarted: redo the view setup
            if world.quit_now:
                return
            if world.goto_level:  # test menu: skip to a level
                world = World(now, world.goto_level, world.hat, world.muted, world.gems)
                size = last_frame = last_status = None
                continue
            if world.restart_now:  # same level from scratch; only the hat and mute setting carry over
                world = World(now, world.level, world.hat, world.muted, world.gems_at_start)
                size = last_frame = last_status = None
                continue
            if not world.game_over and not world.paused:
                world.update(now)
            if world.ready_for_next_level(now):  # inventory, health and the rest start fresh in the next level
                world = World(now, world.level + 1, world.hat, world.muted, world.gems)
                next_save = now + SAVE_EVERY
                size = last_frame = last_status = None
                continue
            if now >= next_save and not world.game_over:
                next_save = now + SAVE_EVERY
                write_save(world, now)
            for event in world.pop_events():
                if event == "quack":
                    sound.quack()
                elif event == "fanfare":
                    sound.fanfare()
                elif event == "coin":
                    sound.coin()
                elif event == "boing":
                    sound.boing()
            status = world.status()
            if status != last_status:
                draw_status(status)
                last_status = status
            frame = world.frame(now)
            if frame != last_frame:
                draw(frame)
                last_frame = frame
    finally:
        if world and world.game_over:
            try:
                os.remove(SAVE_PATH)  # a finished game isn't resumable
            except OSError:
                pass
        elif world:
            write_save(world, gclock())
        if kitty:
            sys.stdout.write("\x1b[<u")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

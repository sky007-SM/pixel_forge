# ============================================================
# Sound for Shards of Aetheria.
#
# The audio engine looks effects up in assets.sounds.SFX and tunes in
# assets.sounds.SONGS. install() adds this game's entries (names start with
# "sh_"); this module is then unloaded (the data lives on in the sounds
# tables). game.exit() removes every "sh_" entry again, so nothing stays in
# RAM after the game exits and the system files are never edited.
#
# Effect segment: (f_start, f_end, ticks, kind)   tick = 10 ms
#   kind 0 tone / slide, 1 noise, 2 silence
# Song: (unit ticks, gap ticks, "NOTE[/units] ...")
# ============================================================
from assets import sounds

SFX = {
    # ---- Kiro ----
    "sh_jump": ((330, 640, 6, 0),),
    "sh_jump2": ((520, 980, 7, 0),),
    "sh_atk0": ((600, 300, 4, 0),),
    "sh_atk1": ((700, 350, 4, 0),),
    "sh_atk2": ((900, 200, 7, 0),),
    "sh_pound": ((500, 120, 8, 0),),
    "sh_land": ((260, 90, 6, 1),),
    "sh_spike": ((300, 1200, 5, 0), (1200, 1200, 3, 0)),
    "sh_dash": ((200, 1400, 8, 0),),
    "sh_void": ((900, 100, 14, 0),),
    "sh_denied": ((196, 196, 3, 0), (0, 0, 1, 2), (160, 160, 3, 0)),
    "sh_hurt": ((600, 150, 10, 0),),
    "sh_fall": ((700, 90, 22, 0),),
    # ---- combat ----
    "sh_hit": ((400, 200, 3, 0),),
    "sh_kill": ((500, 900, 3, 0), (900, 1500, 4, 0)),
    "sh_stomp": ((300, 700, 3, 0), (700, 1000, 3, 0)),
    "sh_block": ((1800, 2400, 2, 1), (900, 900, 3, 0)),
    "sh_impale": ((1500, 200, 4, 1), (180, 120, 8, 0)),
    "sh_boom": ((300, 60, 10, 1), (80, 50, 14, 0)),
    # ---- pick-ups / meter ----
    "sh_coin": ((1319, 1319, 2, 0), (1760, 1760, 4, 0)),
    "sh_heart": ((880, 880, 3, 0), (1175, 1175, 3, 0), (1568, 1568, 6, 0)),
    "sh_orb": ((600, 1500, 8, 0),),
    "sh_cp": ((784, 784, 3, 0), (988, 988, 3, 0), (1319, 1319, 8, 0)),
    "sh_ready0": ((1047, 1047, 3, 0), (1568, 1568, 5, 0)),
    "sh_ready1": ((880, 880, 3, 0), (1319, 1319, 3, 0), (1760, 1760, 6, 0)),
    "sh_ready2": ((440, 440, 3, 0), (659, 659, 3, 0), (880, 880, 3, 0), (1319, 1319, 6, 0)),
    # ---- world / enemies ----
    "sh_rock": ((180, 60, 6, 1),),
    "sh_collapse": ((150, 70, 10, 1), (70, 50, 10, 0)),
    "sh_rumble": ((60, 90, 6, 1),),
    "sh_rift": ((200, 700, 10, 0),),
    "sh_tele": ((1600, 300, 8, 0), (300, 1600, 6, 0)),
    "sh_shoot": ((900, 500, 5, 0),),
    "sh_charge": ((150, 450, 14, 0),),
    "sh_wave": ((220, 100, 9, 1),),
    # ---- Void King ----
    "sh_b_intro": ((120, 80, 20, 0), (0, 0, 4, 2), (240, 100, 30, 0)),
    "sh_b_warn": ((1500, 1500, 3, 0), (0, 0, 2, 2), (1500, 1500, 3, 0)),
    "sh_b_swing": ((800, 120, 8, 0),),
    "sh_b_slam": ((180, 50, 16, 1),),
    "sh_b_beam0": ((150, 1500, 100, 0),),
    "sh_b_beam1": ((90, 110, 100, 0),),
    "sh_b_phase": ((1500, 200, 20, 0), (200, 1500, 20, 0), (1500, 200, 30, 0)),
    "sh_b_die": ((600, 40, 80, 0), (300, 80, 60, 1)),
    # ---- flow ----
    "sh_clear": ((523, 523, 6, 0), (659, 659, 6, 0), (784, 784, 6, 0), (1047, 1047, 20, 0)),
    "sh_menu": ((880, 880, 3, 0), (1320, 1320, 5, 0)),
    "sh_story": ((660, 660, 3, 0),),
    "sh_start": ((330, 330, 4, 0), (440, 440, 4, 0), (660, 660, 10, 0)),
    "sh_dive": ((900, 300, 8, 0),),
    "sh_bump": ((200, 120, 3, 0),),
    "sh_qblock": ((660, 880, 3, 0), (1320, 1320, 6, 0)),
    "sh_flag": ((1320, 330, 30, 0), (0, 0, 3, 2), (523, 659, 4, 0), (784, 1047, 14, 0)),
    "sh_chain": ((988, 988, 2, 0), (1319, 1319, 2, 0), (1760, 1760, 4, 0)),
}

SONGS = {
    "sh_title": (12, 1, "C5/2 G4 C5 E5/2 G5/2 E5 C5 D5/2 G4/2 -/1 B4 D5 G5/3 -/1 "
                        "A4/2 C5/2 E5/2 A5/3 G5 E5 D5/2 C5/4 -/2"),
    "sh_forest": (13, 1, "E5 G5 C6/2 B5 G5 E5/2 D5 F5 A5/2 G5 F5 D5/2 C5 E5 G5/2 E5 D5 C5/2 "
                         "D5 E5 F5 G5 A5/2 G5/2 E5/2 -/1 C5 E5 G5 C6/2 A5 F5 D5/2 G5 E5 C5/2 "
                         "D5/2 G4/2 C5/4 -/2"),
    "sh_ash": (10, 1, "A4/2 A4 C5 E5/2 D5 C5 A4/2 G4/2 G4 B4 D5/2 C5 B4 G4/2 F4/2 F4 A4 C5/2 "
                      "B4 A4 F4/2 E4/2 G#4 B4 E5/2 D5 C5 B4/2 A4/4 -/2"),
    "sh_castle": (16, 2, "A3/3 -/1 E4/2 A4/3 -/1 G4/2 F4/3 E4/2 D4/3 -/1 C4/2 B3/3 E4/4 -/2 "
                         "F4/3 -/1 C5/2 A4/3 G#4/2 E4/4 -/4"),
    "sh_boss": (8, 1, "A3 A3 E4 A3 A3 G4 A3 F4 A3 A3 E4 A3 A3 G4 B3 F#4 "
                      "C4 C4 G4 C4 C4 A#4 C4 G4 B3 B3 F#4 B3 B3 A4 B3 G4"),
    "sh_story": (20, 2, "E5/2 B4 G4/2 -/1 A4/2 C5/2 E5/3 -/1 D5/2 B4 G4/2 F#4/2 E4/4 -/4"),
    "sh_boss2": (7, 1, "E3 E3 B3 E3 E3 D4 E3 C4 E3 E3 B3 E3 E3 D4 F#3 C4 "
                       "G3 G3 D4 G3 G3 F4 G3 D4 F#3 F#3 C4 F#3 F#3 E4 F#3 D4"),
    "sh_win": (9, 1, "C5 E5 G5 C6/2 G5 C6 E6/2 -/1 D6 C6 B5 C6/4 -/2 E6 D6 C6 G5/6"),
}



def install():
    sounds.SFX.update(SFX)
    sounds.SONGS.update(SONGS)

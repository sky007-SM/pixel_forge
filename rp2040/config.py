# ============================================================
# PIXEL FORGE - hardware + system configuration
# Shrike Lite (RP2040 + SLG47910 FPGA) retro console
# ============================================================

def rgb(r, g, b):
    """8-bit RGB -> RGB565."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


# ---------------- Display transport (PIO + DMA -> FPGA -> LCD) ----------------
DISPLAY_DATA_PINS = (0, 1, 2, 3)   # must be consecutive; first pin = PIO out_base
DISPLAY_CLOCK_PIN = 14             # PIO side-set bit 0
DISPLAY_STROBE_PIN = 15            # PIO side-set bit 1 (must be clock pin + 1)
DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240
DISPLAY_PIO_FREQ = 20_200_000      # tuned for a 90 MHz FPGA clock
TARGET_FPS = 30

FLASH_FPGA = True
FPGA_BITSTREAM = "pixel_forge.bin"
FPGA_BOOT_MS = 700                 # FPGA LCD init time after flashing

# ---------------- Controls ----------------
BUTTON_A_PIN = 6
BUTTON_B_PIN = 7
BUTTON_X_PIN = 8
BUTTON_Y_PIN = 9
BUTTON_ACTIVE_LOW = True
BUTTON_DEBOUNCE_MS = 35

JOYSTICK_X_PIN = 26                # ADC0
JOYSTICK_Y_PIN = 27                # ADC1
JOYSTICK_SW_PIN = 18
JOYSTICK_ACTIVE_LOW = True
JOYSTICK_DEADZONE = 9000           # out of +-32768
JOYSTICK_INVERT_X = False
JOYSTICK_INVERT_Y = False          # default: stick up -> negative Y (screen coords)

# ---------------- RGB LED / audio ----------------
RGB_LED_R_PIN = 19
RGB_LED_G_PIN = 20
RGB_LED_B_PIN = 21
RGB_LED_ACTIVE_LOW = False

AUDIO_LEFT_PIN = 22
AUDIO_RIGHT_PIN = 23
AUDIO_ENABLED = True              # set True once the amp/speaker is wired (pins stay untouched until then)
AUDIO_VOLUME = 3                   # 0 (mute) .. 4

# ---------------- System ----------------
SAVE_PATH = "data/saves.json"
GC_LOW_WATER = 40000               # collect garbage in a frame gap below this many free bytes
DEBUG_FPS = False
DEBUG_MEM = False                  # print free heap after each scene is built

# ---------------- System UI palette (RGB565) ----------------
C_BG0 = rgb(10, 12, 22)
C_BG1 = rgb(13, 16, 28)
C_PANEL = rgb(22, 27, 46)
C_PANEL_HI = rgb(40, 32, 38)
C_TEXT = rgb(235, 238, 250)
C_TEXT_DIM = rgb(112, 122, 150)
C_EMBER = rgb(255, 122, 24)
C_EMBER_DARK = rgb(120, 48, 12)
C_EMBER_HOT = rgb(255, 214, 90)
C_RED = rgb(214, 60, 36)

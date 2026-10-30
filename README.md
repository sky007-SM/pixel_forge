# PIXEL FORGE

A retro handheld game console built on the **Vicharak Shrike Lite**
(RP2040 + Renesas **SLG47910 ForgeFPGA**). The RP2040 runs MicroPython games and
renders a 320×240 RGB565 picture one scanline at a time; a small FPGA design turns the
pixel stream into the LCD's SPI signals. Boot screen, menu, pause menu, loading
screens, saves, PWM audio and several games share one polished interface.

## Features
- 320×240 landscape display, 30 fps target, scanline renderer (no frame buffer)
- Boot animation, game menu with previews, shutdown prompt (LCD goes white, then exits)
- Shared pause menu (Resume / Restart / Quit), fade transitions, loading / leaving screens
- Non-blocking PWM music + sound effects (timer driven, off by default)
- JSON save system (best scores, unlocks, money), written atomically
- Memory-safe design for the Pico's small heap (1-bit text, banded buffers, code unloading)
- Games: **Flappy Bird**, **Tetris** (3 levels), **ForgeRacer** (top-down racer, with 4 tracks and 6 cars),
   **Shards of Aetheria** (platformer, with 9 levels in total)

## Hardware
| Function | RP2040 GPIO |
|---|---|
| Display data bits 0-3 | 0, 1, 2, 3 |
| Display clock / strobe | 14 / 15 |
| Buttons A / B / X / Y | 6 / 7 / 8 / 9 (active low) |
| Joystick X / Y / switch | 26 (ADC0) / 27 (ADC1) / 18 |
| RGB LED R / G / B | 19 / 20 / 21 |
| Audio L / R (PWM) | 22 / 23 (currently using only Left as single output) |

Check the physical wiring against your Shrike Lite pinout and HMI module before powering up.

## How the display works
```
 RP2040 core ──renders scanlines──▶ DMA ──▶ PIO (4-bit data + clk + strobe)
                                                   │
                                                   ▼
                              ForgeFPGA (SLG47910): nibbles → bytes → FIFO → SPI master
                                                   │
                                                   ▼
                                        320×240 SPI LCD (RGB565)
```
Every pixel is stored pre-swapped for the PIO, so a row buffer is DMA'd straight out with no
packing step. The CPU composes the next row while DMA sends the current one.

## FPGA design (ForgeFPGA / SLG47910)
The bitstream `pixel_forge.bin` (flashed at boot with `shrike.flash()`) contains the
`lcd_top` Verilog module:
- **Clock:** the on-chip 50 MHz oscillator drives the PLL; the fabric runs on the PLL output of 90MHz.
- **Input stage:** `strobe`, `clk`, `data[3:0]` from the RP2040 are synchronised into the PLL
  clock domain; two nibbles (rising clock edges) make one byte.
- **FIFO:** 16-byte FIFO between the stream and the SPI engine (no flow control, so the
  RP2040 stream must be slower than the SPI drain, see table below).
- **SPI master:** mode 0, MOSI/SCLK/DC/CS driven from a state machine. With `SPI_HALF_DIV = 1`
  it needs about 18 FPGA clocks per byte; SCLK = FPGA clock / 2.
- **LCD sequencer:** hardware reset pulse, init commands, then every frame it sets the full
  address window and streams exactly 320 × 240 × 2 = 153,600 bytes.
- **Delays** (reset / sleep-out) are cycle counts, so they must be recalculated if you change
  the PLL clock.

| FPGA clock | PLL setting (REFDIV / FBDIV / POST1 / POST2) | Max stream | Suggested `DISPLAY_PIO_FREQ` |
|---|---|---|---|
| 90 MHz | 1 / 27 / 5 / 3 | ≈ 5.0 MB/s | 20_200_000 |

Rule of thumb: stream rate = `DISPLAY_PIO_FREQ × 4 / 17` bytes/s must stay a few percent below
`FPGA_clock / 18`. A full frame is 153,600 bytes, which sets the maximum frame rate.
Rebuild the bitstream with Renesas **ForgeFPGA Workshop** (Go Configure Software Hub) and put
the resulting `FPGA_bitstream_MCU.bin` in the board's root.

## Install
1. Flash MicroPython for the Pico (Shrike Lite) and the Shrike library.
2. Copy the project to the board **keeping the folder layout**, with
   `FPGA_bitstream_MCU.bin` and `main.py` in the root (Thonny, `mpremote`, or `rshell`).
3. Reset the board. It boots, loads the FPGA, plays the boot screen and opens the menu.

### Precompile with `tools/make_mpy.py` (recommended)
Importing `.py` files makes the board compile them in RAM first, which needs a lot of temporary
memory. Precompiled `.mpy` files load directly: smaller, faster and much less heap
fragmentation.
```bash
pip install mpy-cross            # or use the mpy-cross from your MicroPython release
python tools/make_mpy.py         # writes everything to build/
```
Copy the **contents of `build/`** to the board. `main.py` and `config.py` stay as `.py`
(so you can still edit pins and settings); delete the `.py` copies of the other files on
the board so the `.mpy` versions are imported.

## Configuration (`config.py`)
| Setting | Meaning |
|---|---|
| `DISPLAY_PIO_FREQ` | PIO clock, must match the FPGA clock (see table above) |
| `TARGET_FPS` | frame pacing (30) |
| `FPGA_BOOT_MS` | wait for the FPGA's LCD init after flashing |
| `AUDIO_ENABLED`, `AUDIO_VOLUME` | PWM audio on GPIO22/23 (off by default), volume 0-4 |
| `JOYSTICK_INVERT_X/Y`, `JOYSTICK_DEADZONE` | stick direction and dead zone |
| `DEBUG_FPS`, `DEBUG_MEM` | print frame rate / free heap to the console |

## Controls
Menu: stick = move, **A** = select, **B** = power menu. In games: **Y** = pause menu
(Resume / Restart / Quit). Each game lists its own controls on its screen.

## Project layout
```
main.py            entry point (flashes FPGA, builds boot art while the LCD initialises)
config.py          pins, display and system settings
hardware/          display (PIO+DMA), input, led, audio
system/            renderer, scene manager, boot, menu, pause, loading, save manager
assets/            fonts (1-bit text), logo, menu previews, sounds
games/             flappy_bird/, tetris/, racer/, shards/, ...
tools/make_mpy.py  precompile to .mpy
data/saves.json    saved scores and unlocks
```
Games are scenes: implement `steps()` (build assets), `update(dt, inp)`, `draw(r)` (emit exactly
240 rows through `r.kick`) and `exit()`, then add the game to the list in `system/menu.py`.

## Memory notes (RP2040 heap is small)
- Text is stored as 1-bit masks; overlays are drawn from rectangles, not pixel buffers.
- No single pixel buffer larger than 4 KB; big data is split into bands.
- A game's code is unloaded when you leave it; saves are written only on static screens.
- Use `.mpy` files, and `DEBUG_MEM = True` to see the free heap after each scene loads.

## Status
The console offers smooth gameplay for all four games and has been extensively playtested.

## License
Add your license here.

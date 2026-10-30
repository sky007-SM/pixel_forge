# ============================================================
# Display transport: FPGA flash, PIO pixel stream, DMA row feeder
#
# Pixels are stored as "P16" values: RGB565 with the nibbles of
# each byte swapped, so a row buffer can be DMA'd straight into
# the PIO with no packing step. Two pixels = one 32-bit word.
# PIO0 / state machine 0 / DMA DREQ 0 are assumed.
# ============================================================
import time, array
import machine, rp2, micropython
from machine import Pin
import config


def P16(c):
    h = c >> 8
    l = c & 255
    return (((h & 15) << 4) | (h >> 4)) | ((((l & 15) << 4) | (l >> 4)) << 8)


@rp2.asm_pio(
    out_init=(rp2.PIO.OUT_LOW,) * 4,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=32,
    sideset_init=(rp2.PIO.OUT_LOW, rp2.PIO.OUT_LOW),
)
def _pixel_stream():
    # data settles one cycle before the clock rising edge;
    # strobe drops for one cycle after every 32-bit word (2 pixels)
    wrap_target()
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    out(pins, 4).side(0b10)
    nop().side(0b11)
    nop().side(0b00)
    wrap()


@micropython.viper
def dma_kick(base: int, src: int):
    # queue one 160-word scanline; waits only if the previous row is still running
    p = ptr32(base)
    while p[3] & 0x01000000:        # CTRL_TRIG.BUSY
        pass
    p[5] = src                      # AL1_READ_ADDR
    p[7] = 160                      # AL1_TRANS_COUNT_TRIG: count + start


@micropython.viper
def dma_wait(base: int):
    p = ptr32(base)
    while p[3] & 0x01000000:
        pass


class Display:
    def __init__(self):
        self.sm = None
        self.dma = None
        self.base = 0
        self.ready_at = 0
        self._dummy = array.array("I", [0] * 160)

    def start(self):
        """Flash the FPGA and start the PIO/DMA transport. Returns immediately;
        the FPGA keeps initialising the LCD in the background."""
        if config.FLASH_FPGA:
            import shrike
            shrike.flash(config.FPGA_BITSTREAM)
        self.ready_at = time.ticks_add(time.ticks_ms(), config.FPGA_BOOT_MS)
        self.sm = rp2.StateMachine(
            0, _pixel_stream,
            freq=config.DISPLAY_PIO_FREQ,
            out_base=Pin(config.DISPLAY_DATA_PINS[0]),
            sideset_base=Pin(config.DISPLAY_CLOCK_PIN),
        )
        self.dma = rp2.DMA()
        ctrl = self.dma.pack_ctrl(size=2, inc_read=True, inc_write=False, treq_sel=0)
        self.dma.config(read=self._dummy, write=0x50200010, count=160,
                        ctrl=ctrl, trigger=False)
        self.base = 0x50000000 + self.dma.channel * 0x40
        self.sm.active(1)

    def is_ready(self):
        return time.ticks_diff(self.ready_at, time.ticks_ms()) <= 0

    def wait_ready(self):
        left = time.ticks_diff(self.ready_at, time.ticks_ms())
        if left > 0:
            time.sleep_ms(left)

    def wait(self):
        dma_wait(self.base)

    def stop(self):
        """Stop the pixel stream and free the DMA channel (the LCD keeps its last frame)."""
        try:
            dma_wait(self.base)
            self.sm.active(0)
            self.dma.close()
        except Exception:
            pass

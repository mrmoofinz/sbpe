import colorsys
import logging
import time

from _remote import ffi, lib
from manager import PluginBase
import util

FLAGS = {
    'drawHUD': True,
    'drawTiles': True,
    'drawEdge': True,
    'drawScatter': True,
    'drawUniform': True,
    'drawHitBoxes': False,
    'drawBoxes': False
}


class Plugin(PluginBase):
    def onInit(self):
        # self.config.option('menu_bg', 0xff1d264d, 'color')
        self.config.option('centered', 1, 'int')
        self.config.option('max_bg_value', 0.3, 'float')
        self.config.option('hide_cursor_after', 1, 'float')
        self.config.options('bool', FLAGS)
        self.config.option('replace_effects', True, 'bool')

        self._shake = 0
        self._flash = 0

        self.effecttxt = util.PlainText(size=30, color=0xffffff00)

    def afterUpdate(self):
        for f in FLAGS:
            self.refs[f][0] = getattr(self.config, f)

        tdt = self.config.hide_cursor_after
        if tdt > 0:
            dt = time.perf_counter() - self.refs.lastMove
            visible = lib.SDL_ShowCursor(-1)
            if dt > tdt and visible == 1:
                lib.SDL_ShowCursor(0)
            if dt <= tdt and visible == 0:
                lib.SDL_ShowCursor(1)

        menu = self.refs.MainMenu
        if menu != ffi.NULL:
            # cancel logo flash animation
            if menu.logo != ffi.NULL and menu.logo.anim != 0:
                menu.logo.anim = 0

        gc = self.refs.GameClient
        if gc == ffi.NULL:
            return

        # disable autokick
        gc.sinceKeypress = 0

        # reduce background brightness if needed
        bg = self.refs.stage[0].backgroundColor
        r, g, b = ((bg >> 16) & 0xff, (bg >> 8) & 0xff, bg & 0xff)
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if v > self.config.max_bg_value:
            v = self.config.max_bg_value
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            bg = ((int(r * 255) & 0xff) << 16) +\
                ((int(g * 255) & 0xff) << 8) +\
                (int(b * 255) & 0xff)
            self.refs.stage[0].backgroundColor = bg | 0xff000000

        wv = self.refs.WorldView

        if wv == ffi.NULL:
            self._shake = 0
            self._flash = 0
            return

        if self.config.centered == 1:
            # centered camera (old style)
            wv.offsetsInitialized = False
            if wv.playerBounds.x != wv.worldBounds.x:
                wv.playerBounds.x = wv.worldBounds.x
                wv.playerBounds.y = wv.worldBounds.y
                wv.playerBounds.w = wv.worldBounds.w
                wv.playerBounds.h = wv.worldBounds.h

        elif self.config.centered == 2:
            # centered, allow camera outside world bounds
            wv.offsetsInitialized = False
            if wv.playerBounds.x == wv.worldBounds.x:
                wv.playerBounds.x = wv.worldBounds.x - 100000
                wv.playerBounds.y = wv.worldBounds.y - 100000
                wv.playerBounds.w = wv.worldBounds.w + 200000
                wv.playerBounds.h = wv.worldBounds.h + 200000

        if self.config.replace_effects:
            if wv.shakePos < wv.shakeDuration and wv.shakeMagnitude > 0:
                self._shake = time.perf_counter() + wv.shakeDuration / 1000
            wv.shakeMagnitude = 0

            flashduration = wv.flashStart + wv.flashHold + wv.flashEnd
            if wv.flashPos < flashduration and wv.flashColor != 0:
                self._flash = time.perf_counter() + flashduration / 1000
            wv.flashColor = 0

    def onPresent(self):
        if self.config.replace_effects:
            ct = time.perf_counter()
            s = []
            if self._shake > ct:
                s = ['SHAKE']
            if self._flash > ct:
                s += ['FLASH']
            if len(s) > 0:
                self.effecttxt.text = '[{}]'.format(', '.join(s))
                self.effecttxt.draw(self.refs.windowW // 2, 30, anchorX=0.5)

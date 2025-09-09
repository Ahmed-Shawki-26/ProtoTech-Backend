#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2013-2014 Paulo Henrique Silva <ph.silva@gmail.com>

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from .render import RenderSettings

COLORS = {
    # ... (existing colors are unchanged) ...
    'black': (0.0, 0.0, 0.0),
    'white': (1.0, 1.0, 1.0),
    'red': (1.0, 0.0, 0.0),
    'green': (0.0, 1.0, 0.0),
    'yellow': (1.0, 1.0, 0),
    'blue': (0.0, 0.0, 1.0),
    'fr-4': (0.290, 0.345, 0.0),
    'green soldermask': (0.0, 0.412, 0.278),
    'blue soldermask': (0.059, 0.478, 0.651),
    'red soldermask': (0.968, 0.169, 0.165),
    'black soldermask': (0.298, 0.275, 0.282),
    'purple soldermask': (0.2, 0.0, 0.334),
    'enig copper': (0.694, 0.533, 0.514),
    'hasl copper': (0.871, 0.851, 0.839),
    'yellow soldermask': (0.98, 0.9, 0.2),
    'dull gold copper': (0.8, 0.7, 0.4),
    'white soldermask': (0.92, 0.92, 0.92),

    # === NEW COLORS FOR MATERIAL-BASED THEMES ===
    'aluminum_base': (0.82, 0.83, 0.84),
    'flex_polyimide': (0.9, 0.65, 0.2),
    'rogers_white': (1.0, 1.0, 1.0),
    'flex_amber_polyimide': (0.88, 0.60, 0.25), # A rich amber/orange color
    'flex_copper': (0.75, 0.50, 0.35),         # A duller, reddish copper for traces
    'flex_pad_gold': (0.90, 0.80, 0.60),        # A light gold/tinned color for exposed pads
}


SPECTRUM = [
    (0.804, 0.216, 0),
    (0.78, 0.776, 0.251),
    (0.545, 0.451, 0.333),
    (0.545, 0.137, 0.137),
    (0.329, 0.545, 0.329),
    (0.133, 0.545, 0.133),
    (0, 0.525, 0.545),
    (0.227, 0.373, 0.804),
]


class Theme(object):

    def __init__(self, name=None, **kwargs):
        self.name = 'Default' if name is None else name
        self.background = kwargs.get('background', RenderSettings(COLORS['fr-4']))
        self.topsilk = kwargs.get('topsilk', RenderSettings(COLORS['white']))
        self.bottomsilk = kwargs.get('bottomsilk', RenderSettings(COLORS['white'], mirror=True))
        self.topmask = kwargs.get('topmask', RenderSettings(COLORS['green soldermask'], alpha=0.85, invert=True))
        self.bottommask = kwargs.get('bottommask', RenderSettings(COLORS['green soldermask'], alpha=0.85, invert=True, mirror=True))
        self.top = kwargs.get('top', RenderSettings(COLORS['hasl copper']))
        self.bottom = kwargs.get('bottom', RenderSettings(COLORS['hasl copper'], mirror=True))
        self.drill = kwargs.get('drill', RenderSettings(COLORS['black']))
        self.ipc_netlist = kwargs.get('ipc_netlist', RenderSettings(COLORS['red']))
        self._internal = kwargs.get('internal', [RenderSettings(x) for x in SPECTRUM])
        self._internal_gen = None

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def internal(self):
        if not self._internal_gen:
            self._internal_gen = self._internal_gen_func()
        return next(self._internal_gen)

    def _internal_gen_func(self):
        for setting in self._internal:
            yield setting

    def get(self, key, noneval=None):
        val = getattr(self, key, None)
        return val if val is not None else noneval


THEMES = {
    'default': Theme(),
    'OSH Park': Theme(name='OSH Park',
                      background=RenderSettings(COLORS['purple soldermask']),
                      top=RenderSettings(COLORS['enig copper']),
                      bottom=RenderSettings(COLORS['enig copper'], mirror=True),
                      topmask=RenderSettings(COLORS['purple soldermask'], alpha=0.85, invert=True),
                      bottommask=RenderSettings(COLORS['purple soldermask'], alpha=0.85, invert=True, mirror=True),
                      topsilk=RenderSettings(COLORS['white'], alpha=0.8),
                      bottomsilk=RenderSettings(COLORS['white'], alpha=0.8, mirror=True)),

    'Blue': Theme(name='Blue',
                  topmask=RenderSettings(COLORS['blue soldermask'], alpha=0.8, invert=True),
                  bottommask=RenderSettings(COLORS['blue soldermask'], alpha=0.8, invert=True)),

    'Transparent Copper': Theme(name='Transparent',
                                background=RenderSettings((0.9, 0.9, 0.9)),
                                top=RenderSettings(COLORS['red'], alpha=0.5),
                                bottom=RenderSettings(COLORS['blue'], alpha=0.5),
                                drill=RenderSettings((0.3, 0.3, 0.3))),

    'Transparent Multilayer': Theme(name='Transparent Multilayer',
                                    background=RenderSettings((0, 0, 0)),
                                    top=RenderSettings(SPECTRUM[0], alpha=0.8),
                                    bottom=RenderSettings(SPECTRUM[-1], alpha=0.8),
                                    drill=RenderSettings((0.3, 0.3, 0.3)),
                                    internal=[RenderSettings(x, alpha=0.5) for x in SPECTRUM[1:-1]]),

    # === NEW CUSTOM THEMES ===
    'Golden Yellow': Theme(name='Golden Yellow',
                           background=RenderSettings(COLORS['yellow soldermask']),
                           top=RenderSettings(COLORS['dull gold copper']),
                           bottom=RenderSettings(COLORS['dull gold copper'], mirror=True),
                           topmask=RenderSettings(COLORS['yellow soldermask'], alpha=0.8, invert=True),
                           bottommask=RenderSettings(COLORS['yellow soldermask'], alpha=0.8, invert=True, mirror=True),
                           topsilk=RenderSettings(COLORS['black']),
                           bottomsilk=RenderSettings(COLORS['black'], mirror=True)),

    'Modern White': Theme(name='Modern White',
                          background=RenderSettings(COLORS['white soldermask']),
                          top=RenderSettings(COLORS['hasl copper']),
                          bottom=RenderSettings(COLORS['hasl copper'], mirror=True),
                          topmask=RenderSettings(COLORS['white soldermask'], alpha=0.8, invert=True),
                          bottommask=RenderSettings(COLORS['white soldermask'], alpha=0.8, invert=True, mirror=True),
                          topsilk=RenderSettings(COLORS['black']),
                          bottomsilk=RenderSettings(COLORS['black'], mirror=True)),


    # === NEW THEMES FOR DIFFERENT MATERIALS ===

    'Aluminum': Theme(name='Aluminum',
        background=RenderSettings((0.82, 0.83, 0.84)),  # لا بأس بالخلفية الحالية
        top=RenderSettings((0.55, 0.45, 0.35)),         # نحاس داكن أو دافئ
        bottom=RenderSettings((0.55, 0.45, 0.35), mirror=True),
        topmask=RenderSettings((0.95, 0.95, 0.95), alpha=0.6, invert=True),
        bottommask=RenderSettings((0.95, 0.95, 0.95), alpha=0.6, invert=True, mirror=True),
        topsilk=RenderSettings((0.0, 0.0, 0.0), alpha=1.0),
        bottomsilk=RenderSettings((0.0, 0.0, 0.0), alpha=1.0, mirror=True),
        drill=RenderSettings((0.1, 0.1, 0.1), alpha=0.9)
    ),

    'Flex': Theme(name='Flex',
        background=RenderSettings((0.933, 0.933, 0.0), alpha=1.0),
        top=RenderSettings((0.55, 0.5, 0.0)),  # نحاس أغمق لزيادة التباين
        bottom=RenderSettings((0.55, 0.5, 0.0), mirror=True),
        topmask=RenderSettings((0.933, 0.933, 0.0), alpha=0.6, invert=True),  # قناع شفاف أكثر
        bottommask=RenderSettings((0.933, 0.933, 0.0), alpha=0.6, invert=True, mirror=True),
        topsilk=RenderSettings((0.0, 0.0, 0.0), alpha=1.0),  # سيلكس أسود واضح
        bottomsilk=RenderSettings((0.0, 0.0, 0.0), alpha=1.0, mirror=True),
        drill=RenderSettings((0.0, 0.0, 0.0), alpha=0.9)
    ),



}


# Add a copy of Aluminum for Copper Core as they look similar
THEMES['Copper Core'] = THEMES['Aluminum']
"""Choose a matching Qt/Chromium renderer before either creates a device."""
from __future__ import annotations

import os
import re
import sys


def configure_graphics(environ=None, platform=None):
    env = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    # The WebEngine camera path can make a physical D3D11 device disappear on
    # some Windows drivers.  WARP keeps the Qt and Chromium contexts on the
    # same software adapter, so opening the camera cannot kill the renderer.
    # Hardware remains available as an explicit opt-in.
    mode = env.get('JARVIS_GRAPHICS_MODE', 'compat' if platform == 'win32' else 'auto').lower().strip()
    if platform != 'win32' or mode == 'auto':
        return 'auto'
    # Qt and ANGLE must select the same adapter.
    compatible = mode == 'compat'
    env.pop('QT_QUICK_BACKEND', None)
    env.pop('QT_D3D_ADAPTER_INDEX', None)
    env['QSG_RHI_BACKEND'] = 'd3d11'
    env['QSG_RHI_PREFER_SOFTWARE_RENDERER'] = '1' if compatible else '0'
    flags = env.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
    flags = re.sub(r'(?<!\S)--(?:use-gl|use-angle)(?:=\S+|\s+\S+)', '', flags)
    flags = re.sub(r'(?<!\S)--disable-(?:gpu|software-rasterizer)(?![\w-])', '', flags)
    # DirectShow capture avoids creating an Intel D3D device for webcam frames.
    disabled = set()
    def collect_features(match):
        disabled.update(item for item in match.group(1).split(',') if item)
        return ''
    flags = re.sub(r'(?<!\S)--disable-features(?:=|\s+)(\S+)', collect_features, flags)
    disabled.update({'MediaFoundationVideoCapture', 'MediaFoundationD3D11VideoCapture', 'MediaFoundationD3D11VideoCaptureZeroCopy'})
    angle = 'd3d11-warp' if compatible else 'd3d11'
    env['QTWEBENGINE_CHROMIUM_FLAGS'] = (flags.strip() + ' --use-gl=angle --use-angle=' + angle + ' --disable-features=' + ','.join(sorted(disabled))).strip()
    return 'compat' if compatible else 'hardware'


GRAPHICS_MODE = configure_graphics()

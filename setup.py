from setuptools import Extension, find_packages, setup

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None

import numpy as np

packages = find_packages(include=["jingle_dmx"])

extensions = [
    Extension(
        name="audio_core",
        sources=["audio_core.pyx"],
        include_dirs=[np.get_include()],
    )
]

if cythonize is not None:
    extensions = cythonize(extensions, language_level=3)

setup(
    name="jingle-dmx",
    packages=packages,
    py_modules=[
        "base_dmx",
        "dynamic_thresholds",
        "laser",
        "light_strip",
        "main",
        "show_controller",
        "spotlight",
        "stinger",
        "strobe",
        "usb_mic",
        "service_start",
    ],
    ext_modules=extensions,
)

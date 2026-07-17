# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

import numpy as np
cimport numpy as cnp

ctypedef cnp.float32_t float32_t


cpdef tuple fast_rms_peak(cnp.ndarray[float32_t, ndim=1] audio):
    """Compute RMS and peak for a mono float32 array.

    Parameters
    ----------
    audio : 1D np.ndarray[np.float32]
        Audio samples.
    """
    cdef Py_ssize_t i, n = audio.shape[0]
    cdef double acc = 0.0
    cdef double peak = 0.0
    cdef double v

    for i in range(n):
        v = audio[i]
        acc += v * v
        if v < 0:
            v = -v
        if v > peak:
            peak = v

    if n == 0:
        return 0.0, 0.0

    cdef double rms = (acc / n) ** 0.5
    return rms, peak

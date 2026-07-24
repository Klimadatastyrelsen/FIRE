"""
API modul til beregning af statistik og regressionsanalyse

Modulet er engelsksproget, da mange fagtermer er lettest at
anvende på engelsk.
"""

from numpy import ndarray


class Normalizer:
    """
    Simple class for resizing a data set

    Only works on 1D arrays for now.

    Main use case is to recenter and rescale a data set in case of numerical instabilities
    during inversion problems.

    If `Normalizer` is instantiated with a data set, it's original center/span is recorded,
    and thus can be used to "denormalize" inversion results.

    Usage:
    Normalize data to range [-5, 5]::

        normalized = Normalizer().normalize(data, center=0, span=10)

    Normalize data to range [-5 ,5], do some data transformation (e.g. inversion)
    and then denormalize to original size::

        normalizer = Normalizer(data)

        normalized = normalizer.normalize(data, center=0, span=10)
        transformed = Transform(normalized)

        denormalized = normalizer.denormalize(transformed)
    """

    def __init__(self, data: ndarray = None):
        self.original_center = None
        self.original_span = None

        # Record original center/span
        if data is not None:
            self.original_center = self._center(data)
            self.original_span = self._span(data)

    def _center(self, data: ndarray):
        """Get center of data"""
        return max((data) + min(data)) / 2

    def _span(self, data: ndarray):
        """Get the span of data"""
        return max(data) - min(data)

    def recenter(self, data: ndarray, new_center: float = 0) -> ndarray:
        """Recenter data around a new center"""
        return (data - self._center(data)) + new_center

    def rescale(self, data: ndarray, new_span: float) -> ndarray:
        """Rescale data to new span (with the same center)"""
        scale_factor = new_span / self._span(data)
        center = self._center(data)
        return (data - center) * scale_factor + center

    def normalize(self, data: ndarray, center: float = 0, span: float = 2) -> ndarray:
        """
        Normalize data by both recentering and rescaling

        Normalized data will be in the interval center ± span/2
        Defaults correspond to the interval [-1, 1]
        """
        recentered = self.recenter(data, center)
        return self.rescale(recentered, span)

    def denormalize(self, data: ndarray) -> ndarray:
        """Denormalize, i.e. move data into its original center/span"""
        if self.original_center is None or self.original_span is None:
            raise ValueError("Original center and span of data is unknown.")
        return self.normalize(data, self.original_center, self.original_span)


# expose classes and functions
from fire.api.statistik.least_squares import *
from fire.api.statistik.hypothesis_test import *
from fire.api.statistik.visualizations import *
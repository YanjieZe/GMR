"""
This is where all the task primitives are defined
"""
import numpy as np

from .core import BasePlotterTask


class DrawXDLines(BasePlotterTask):
    _lines: np.ndarray
    _color: str
    _line_width: int
    _alpha: float
    _influence_lim: bool

    def __init__(
        self,
        task_name: str,
        lines: np.ndarray,
        color: str = "blue",
        line_width: int = 2,
        alpha: float = 1.0,
        influence_lim: bool = True,
    ) -> None:
        super().__init__(task_name=task_name, task_type=self.__class__.__name__)
        self._color = color
        self._line_width = line_width
        self._alpha = alpha
        self._influence_lim = influence_lim
        self.update(lines)

    @property
    def influence_lim(self) -> bool:
        return self._influence_lim

    @property
    def raw_data(self):
        return self._lines

    @property
    def color(self):
        return self._color

    @property
    def line_width(self):
        return self._line_width

    @property
    def alpha(self):
        return self._alpha

    @property
    def dim(self):
        raise NotImplementedError

    @property
    def name(self):
        return "{}DLines".format(self.dim)

    def update(self, lines):
        self._lines = np.array(lines)
        shape = self._lines.shape
        assert shape[-1] == self.dim and shape[-2] == 2 and len(shape) == 3

    def __getitem__(self, index):
        return self._lines[index]

    def __len__(self):
        return self._lines.shape[0]

    def __iter__(self):
        yield self


class DrawXDDots(BasePlotterTask):
    _dots: np.ndarray
    _color: str
    _marker_size: int
    _alpha: float
    _influence_lim: bool

    def __init__(
        self,
        task_name: str,
        dots: np.ndarray,
        color: str = "blue",
        marker_size: int = 10,
        alpha: float = 1.0,
        influence_lim: bool = True,
    ) -> None:
        super().__init__(task_name=task_name, task_type=self.__class__.__name__)
        self._color = color
        self._marker_size = marker_size
        self._alpha = alpha
        self._influence_lim = influence_lim
        self.update(dots)

    def update(self, dots):
        self._dots = np.array(dots)
        shape = self._dots.shape
        assert shape[-1] == self.dim and len(shape) == 2

    def __getitem__(self, index):
        return self._dots[index]

    def __len__(self):
        return self._dots.shape[0]

    def __iter__(self):
        yield self

    @property
    def influence_lim(self) -> bool:
        return self._influence_lim

    @property
    def raw_data(self):
        return self._dots

    @property
    def color(self):
        return self._color

    @property
    def marker_size(self):
        return self._marker_size

    @property
    def alpha(self):
        return self._alpha

    @property
    def dim(self):
        raise NotImplementedError

    @property
    def name(self):
        return "{}DDots".format(self.dim)


class DrawXDTrail(DrawXDDots):
    @property
    def line_width(self):
        return self.marker_size

    @property
    def name(self):
        return "{}DTrail".format(self.dim)


class Draw2DLines(DrawXDLines):
    @property
    def dim(self):
        return 2


class Draw3DLines(DrawXDLines):
    @property
    def dim(self):
        return 3


class Draw2DDots(DrawXDDots):
    @property
    def dim(self):
        return 2


class Draw3DDots(DrawXDDots):
    @property
    def dim(self):
        return 3


class Draw2DTrail(DrawXDTrail):
    @property
    def dim(self):
        return 2


class Draw3DTrail(DrawXDTrail):
    @property
    def dim(self):
        return 3


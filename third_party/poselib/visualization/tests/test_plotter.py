from typing import cast

import matplotlib.pyplot as plt
import numpy as np

from ..core import BasePlotterTask, BasePlotterTasks
from ..plt_plotter import Matplotlib3DPlotter
from ..simple_plotter_tasks import Draw3DDots, Draw3DLines

task = Draw3DLines(task_name="test", 
    lines=np.array([[[0, 0, 0], [0, 0, 1]], [[0, 1, 1], [0, 1, 0]]]), color="blue")
task2 = Draw3DDots(task_name="test2", 
    dots=np.array([[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]]), color="red")
task3 = BasePlotterTasks([task, task2])
plotter = Matplotlib3DPlotter(cast(BasePlotterTask, task3))
plt.show()

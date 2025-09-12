"""
The base abstract classes for plotter and the plotting tasks. It describes how the plotter
deals with the tasks in the general cases
"""
from typing import List


class BasePlotterTask(object):
    _task_name: str  # unique name of the task
    _task_type: str  # type of the task is used to identify which callable

    def __init__(self, task_name: str, task_type: str) -> None:
        self._task_name = task_name
        self._task_type = task_type

    @property
    def task_name(self):
        return self._task_name

    @property
    def task_type(self):
        return self._task_type

    def get_scoped_name(self, name):
        return self._task_name + "/" + name

    def __iter__(self):
        """Should override this function to return a list of task primitives
        """
        raise NotImplementedError


class BasePlotterTasks(object):
    def __init__(self, tasks) -> None:
        self._tasks = tasks

    def __iter__(self):
        for task in self._tasks:
            yield from task


class BasePlotter(object):
    """An abstract plotter which deals with a plotting task. The children class needs to implement
    the functions to create/update the objects according to the task given
    """

    _task_primitives: List[BasePlotterTask]

    def __init__(self, task: BasePlotterTask) -> None:
        self._task_primitives = []
        self.create(task)

    @property
    def task_primitives(self):
        return self._task_primitives

    def create(self, task: BasePlotterTask) -> None:
        """Create more task primitives from a task for the plotter"""
        new_task_primitives = list(task)  # get all task primitives
        self._task_primitives += new_task_primitives  # append them
        self._create_impl(new_task_primitives)

    def update(self) -> None:
        """Update the plotter for any updates in the task primitives"""
        self._update_impl(self._task_primitives)

    def _update_impl(self, task_list: List[BasePlotterTask]) -> None:
        raise NotImplementedError

    def _create_impl(self, task_list: List[BasePlotterTask]) -> None:
        raise NotImplementedError

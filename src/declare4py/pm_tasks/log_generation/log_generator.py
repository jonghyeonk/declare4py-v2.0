from __future__ import annotations

import collections
import logging
import typing
from abc import ABC

from src.declare4py.pm_tasks.log_generation.asp.asp_utils.distribution import Distributor
from src.declare4py.pm_tasks.pm_task import PMTask
from src.declare4py.process_models.process_model import ProcessModel

# from src.declare4py.process_models.ltl_model import LTLModel

"""

An abstract class for log generators.


Parameters
-------
log_length object of type int
PMTask inheriting from PMTask
"""


class LogGenerator(PMTask, ABC):

    def __init__(self, num_traces: int, min_event: int, max_event: int, p_model: ProcessModel):
        super().__init__(None, p_model)
        if min_event > max_event:
            raise ValueError(f"min_events({min_event}) > max_events({max_event}) not valid! Min events are greater than max events")
        self.__py_logger = logging.getLogger("Log generator")
        self.log_length: int = num_traces
        self.max_events: int = max_event
        self.min_events: int = min_event

        # Distributions Setting
        self.traces_length = {}
        self.distributor_type: typing.Literal["uniform", "gaussian", "custom"] = "uniform"
        self.custom_probabilities: None = None
        self.scale: float = None
        self.loc: float = None

        # Constraint violations
        """
        A trace is positive if it satisfies all three constraints that are defined in this model. Whereas it is
        negative if at least one of them is not satisfied. In the generated log you sent me, in all traces the 
        constraint " Response[Driving_Test, Resit] |A.Grade<=2 | " is not satisfied, i.e. it is violated!
        """
        self.violate_all_constraints: bool = False  # if false: clingo will decide itself the constraints to violate
        self.violatable_constraints: [str] = []  # constraint list which should be violated
        self.negative_traces = 0

        # constraint template conditions
        self.activation_conditions: dict = None

    def compute_distribution(self, total_traces: int | None = None):
        """
         The compute_distribution method computes the distribution of the number of events in a trace based on
         the distributor_type parameter. If the distributor_type is "gaussian", it uses the loc and scale parameters
         to compute a Gaussian distribution. Otherwise, it uses a uniform or custom distribution.
        """
        self.__py_logger.info("Computing distribution")
        d = Distributor()
        if total_traces is None:
            total_traces = self.log_length
        traces_len = {}
        if self.distributor_type == "gaussian":
            self.__py_logger.info(f"Computing gaussian distribution with mu={self.loc} and sigma={self.scale}")
            assert self.loc > 1  # Mu atleast should be 2
            assert self.scale >= 0  # standard deviation must be a positive value
            result: collections.Counter | None = d.distribution(
                self.loc, self.scale, total_traces, self.distributor_type, self.custom_probabilities)
            self.__py_logger.info(f"Gaussian distribution result {result}")
            if result is None or len(result) == 0:
                raise ValueError("Unable to found the number of traces with events to produce in log.")
            for k, v in result.items():
                if self.min_events <= k <= self.max_events:  # TODO: ask whether the boundaries should be included
                    traces_len[k] = v
            self.__py_logger.info(f"Gaussian distribution after refinement {traces_len}")
        else:
            traces_len: collections.Counter | None = d.distribution(self.min_events, self.max_events, total_traces,
                                                                    self.distributor_type, self.custom_probabilities)
        self.__py_logger.info(f"Distribution result {traces_len}")
        self.traces_length = traces_len
        return traces_len

    def set_distribution(self, distributor_type: typing.Literal["uniform", "gaussian", "custom"] = "uniform",
                         custom_probabilities: typing.Optional[typing.List[float]] = None,
                         loc: float = None, scale: float = None):
        self.distributor_type = distributor_type
        self.custom_probabilities = custom_probabilities
        self.scale = scale
        self.loc = loc
        return self

    def add_constraints_to_violate(self, constrains_to_violate: str | [str] = True):
        if isinstance(constrains_to_violate, str):
            self.violatable_constraints.append(constrains_to_violate)
        else:
            self.violatable_constraints = constrains_to_violate
        return self

    def set_activation_conditions(self, activations_list: dict[str, list[int]]):
        """
        the activation conditions are used TODO: add more info about it.
        TODO: this method should be in the asp generator rather than abstract class and also self.activation_conditions.

        Parameters
        ----------
        : param activations_list dict: accepts a dictionary with key as a string which represent a declare model
            constraint template, and value as an list with number values.
            i.e 'Response[A,B] | A.attribute is value1 | |': [3, 5].
            Here key represents a constraint template and the number list represents how many times activation key of
            that constraint template should be occurred. In this example we are saying, that it should at least 3 times
            and at most 5 times.
            the value must be a list of 2 integer which represents the bounding limits of activation. You can add math.inf
            as the 2 second element. First element should be greater or equal than 0.

        Returns
        -------

        """
        self.activation_conditions = activations_list
        return self

    def set_activation_conditions_by_template_index(self, activations_list: dict[int, list[int]]):
        """
        the activation conditions are used TODO: add more info about it.
        TODO: this method should be in the asp generator rather than abstract class and also self.activation_conditions.

        Parameters
        ----------
        : param activations_list dict: accepts a dictionary with key as a string which represent a declare model
            constraint template, and value as an list with number values.
            i.e 'Response[A,B] | A.attribute is value1 | |': [3, 5].
            Here key represents a constraint template and the number list represents how many times activation key of
            that constraint template should be occurred. In this example we are saying, that it should at least 3 times
            and at most 5 times.

        Returns
        -------

        """
        # indexes = activations_list.keys()  # indexes of constraint templates
        templates = self.process_model.parsed_model.templates
        n_dict = {}
        for m, n in activations_list.items():
            n_dict[templates[m].template_line] = n
        self.activation_conditions = n_dict
        return self


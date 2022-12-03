from __future__ import annotations

import re

from src.declare4py.log_utils.parsers.abstract.modelparser import ModelParser
from src.declare4py.log_utils.parsers.declare.decl_model import DeclModel, DeclareModelAttributeType, DeclareParsedModel
from src.declare4py.log_utils.parsers.declare.declare_parsers_utility import DeclareParserUtility
from src.declare4py.mp_constants import Template


class DeclareParseDetector:
    CONSTRAINTS_TEMPLATES_PATTERN = r"^(.*)\[(.*)\]\s*(.*)$"

    def __init__(self, lines: [str]):
        self.lines = lines

    @staticmethod
    def is_event_name_definition(line: str) -> bool:
        x = re.search(r"^\w+ [\w ]+$", line, re.MULTILINE)
        return x is not None

    @staticmethod
    def is_event_attributes_definition(line: str) -> bool:
        x = re.search("^bind (.*?)+$", line, re.MULTILINE)
        return x is not None

    @staticmethod
    def is_events_attrs_value_definition(line: str) -> bool:
        """
        categorical: c1, c2, c3
        categorical: group1:v1, group1:v2, group3:v1       <-------- Fails to parse this line
        integer: integer between 0 and 100
        org:resource: 10
        org:resource, org:vote: 10
        org:vote, grade: 9
        org:categorical: integer between 0 and 100
        categorical: integer between 0 and 100
        base, mark: integer between 0 and 100
        org:res, grade, concept:name: integer between 0 and 100
        :param line: declare line
        :return:
        """
        x = re.search(r"^(?!bind)([a-zA-Z_,0-9.?: ]+) *(: *[\w,.? ]+)$", line, re.MULTILINE)
        if x is None:
            return False
        groups_len = len(x.groups())
        return groups_len >= 2

    @staticmethod
    def is_constraint_template_definition(line: str) -> bool:
        x = re.search(DeclareParseDetector.CONSTRAINTS_TEMPLATES_PATTERN, line, re.MULTILINE)
        return x is not None

    @staticmethod
    def detect_declare_attr_value_type(value: str) -> DeclareModelAttributeType:
        """
        Detect the type of value assigned to an attribute assigned
        Parameters
        ----------
        value: assigned value
        Returns DeclareModelAttributeType
        -------
        """
        value = value.strip()
        v2 = value.replace("  ", "")
        if re.search(r"^[+-]?\d+$", value, re.MULTILINE):
            return DeclareModelAttributeType.INTEGER
        elif re.search(r"^[+-]?\d+(?:\.\d+)?$", value, re.MULTILINE):
            return DeclareModelAttributeType.FLOAT
        elif v2 and v2.lower().startswith("integer between"):
            # ^integer * between *[+-]?\d+(?:\.\d+)? *and [+-]?\d+(?:\.\d+)?$
            return DeclareModelAttributeType.INTEGER_RANGE
        elif v2 and v2.lower().startswith("float between"):
            # ^float * between *[+-]?\d+(?:\.\d+)? *and [+-]?\d+(?:\.\d+)?$
            return DeclareModelAttributeType.FLOAT_RANGE
        else:
            return DeclareModelAttributeType.ENUMERATION


class DeclareParser(ModelParser):

    def __init__(self):
        super().__init__()
        self.model: DeclModel | None = None
        self.dp_utilty = DeclareParserUtility()

    def parse_decl_model(self, model_path) -> None:
        """
        Parse the input DECLARE model.

        Parameters
        ----------
        model_path : str
            File path where the DECLARE model is stored.
        """
        self.model = self.parse_decl_from_file(model_path)

    def parse_data_cond(self, cond: str):
        return self.dp_utilty.parse_data_cond(cond)

    def parse_time_cond(self, condition: str):
        return self.dp_utilty.parse_data_cond(condition)

    def parse_decl_from_file(self, path: str) -> DeclModel:
        return self.parse_from_file(path)

    def parse_decl_from_string(self, decl_string: str) -> DeclModel:
        return self.parse_from_string(decl_string)

    def parse_from_file(self, filename: str) -> DeclModel:
        with open(filename, "r+") as file:
            self.lines = file.readlines()
        model: DeclModel = self.parse()
        return model

    def parse_from_string(self, content: str, new_line_ctrl: str = "\n") -> DeclModel:
        self.lines = content.split(new_line_ctrl)
        model: DeclModel = self.parse()
        return model

    def parse(self) -> DeclModel:
        return self.parse_decl(self.lines)

    def parse_decl(self, lines) -> DeclModel:
        decl_model = DeclModel()
        dpm = DeclareParsedModel()
        decl_model.parsed_model = dpm
        for line in lines:
            line = line.strip()
            if len(line) <= 1 or line.startswith("#"):  # line starting with # considered a comment line
                continue
            if DeclareParseDetector.is_event_name_definition(line):  # split[0].strip() == 'activity':
                split = line.split(maxsplit=1)
                decl_model.activities.append(split[1].strip())
                dpm.add_event(split[1], split[0])
            elif DeclareParseDetector.is_event_attributes_definition(line):
                split = line.split(": ", maxsplit=1)  # Assume complex "bind act3: categorical, integer, org:group"
                event_name = split[0].split(" ", maxsplit=1)[1].strip()
                attrs = split[1].strip().split(",",)
                for attr in attrs:
                    dpm.add_attribute(event_name, attr.strip())
            elif DeclareParseDetector.is_events_attrs_value_definition(line):
                """
                SOME OF Possible lines for assigning values to attribute
                
                categorical: c1, c2, c3
                categorical: group1:v1, group1:v2, group3:v1 
                cat1, cat2: group1:v1, group1:v2, group3:v1 
                price:art1, price:art2, cat2: group1:v1, group1:v2, group3:v1 
                integer: integer between 0 and 100
                org:resource: 10
                org:resource, org:vote: 10
                org:vote, grade: 9
                org:categorical: integer between 0 and 100
                categorical: integer between 0 and 100
                base, mark: integer between -30 and 100
                org:res, grade, concept:name: integer between 0 and 100
                """
                # consider this complex line: price:art1, price:art2, cat2: group1:v1, group1:v2, group3:v1
                split = line.split(": ", maxsplit=1)
                attributes_list = split[0]  # price:art1, price:art2, cat2
                attributes_list = attributes_list.strip().split(",")
                value = split[1].strip()
                typ = DeclareParseDetector.detect_declare_attr_value_type(value)
                for attr in attributes_list:
                    dpm.add_attribute_value(attr, typ, value)
            elif DeclareParseDetector.is_constraint_template_definition(line):
                split = line.split("[", 1)
                template_search = re.search(r'(^.+?)(\d*$)', split[0])
                if template_search is not None:
                    template_str, cardinality = template_search.groups()
                    template = Template.get_template_from_string(template_str)
                    if template is not None:
                        activities = split[1].split("]")[0]
                        tmp = {
                            "template": template,
                            "activities": activities,
                            "condition": re.split(r'\s+\|', line)[1:]
                        }
                        if template.supports_cardinality:
                            tmp['n'] = 1 if not cardinality else int(cardinality)
                            cardinality = tmp['n']
                        decl_model.constraints.append(tmp)
                        dpm.add_template(line.strip(), template, cardinality)
        decl_model.set_constraints()
        dpm.template_constraints = decl_model.constraints
        return decl_model


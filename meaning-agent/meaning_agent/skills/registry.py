"""Read-only registry for the six reusable skills."""

from .l1_load_reduction import SPEC as L1, run as run_l1
from .l2_experiential import SPEC as L2, run as run_l2
from .l3_meaning_generation import SPEC as L3, run as run_l3
from .l4_evidence import SPEC as L4, run as run_l4
from .l5_direction import SPEC as L5, run as run_l5
from .l6_recursive import SPEC as L6, run as run_l6

SKILLS = ((L1, run_l1), (L2, run_l2), (L3, run_l3), (L4, run_l4), (L5, run_l5), (L6, run_l6))


def registry_metadata():
    return [spec.as_dict() for spec, _ in SKILLS]


def get_skill(name_or_layer):
    for spec, runner in SKILLS:
        if name_or_layer in (spec.name, spec.layer):
            return spec, runner
    raise KeyError(name_or_layer)


def run_skill(name_or_layer, payload):
    return get_skill(name_or_layer)[1](payload)

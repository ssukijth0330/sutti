#!/usr/bin/env python3
import argparse
from collections import defaultdict
import jinja2
import os
from enum import Enum
from natsort import natsorted
from typing import Dict, List

from cereal import car
from openpilot.common.basedir import BASEDIR
from openpilot.selfdrive.car import gen_empty_fingerprint
from openpilot.selfdrive.car.docs_definitions import CarInfo, Column, CommonFootnote, DashcamReason, PartType
from openpilot.selfdrive.car.car_helpers import interfaces, get_interface_attr

CARS_MD_OUT = os.path.join(BASEDIR, "docs", "CARS.md")
CARS_MD_TEMPLATE = os.path.join(BASEDIR, "selfdrive", "car", "CARS_template.md")

PORTS_MD_OUT = os.path.join(BASEDIR, "docs", "PORTS.md")
PORTS_MD_TEMPLATE = os.path.join(BASEDIR, "selfdrive", "car", "PORTS_template.md")


def get_all_footnotes() -> Dict[Enum, int]:
  all_footnotes = list(CommonFootnote)
  for footnotes in get_interface_attr("Footnote", ignore_none=True).values():
    all_footnotes.extend(footnotes)
  return {fn: idx + 1 for idx, fn in enumerate(all_footnotes)}


def get_all_car_info(dashcam_only: bool = False) -> List[CarInfo]:
  all_car_info: List[CarInfo] = []
  footnotes = get_all_footnotes()
  for model, car_info in get_interface_attr("CAR_INFO", combine_brands=True).items():
    # If available, uses experimental longitudinal limits for the docs
    CP = interfaces[model][0].get_params(model, fingerprint=gen_empty_fingerprint(),
                                         car_fw=[car.CarParams.CarFw(ecu="unknown")], experimental_long=True, docs=True)

    if CP.dashcamOnly != dashcam_only or car_info is None:
      continue

    # A platform can include multiple car models
    if not isinstance(car_info, list):
      car_info = (car_info,)

    for _car_info in car_info:
      if not hasattr(_car_info, "row"):
        _car_info.init_make(CP)
        _car_info.init(CP, footnotes)
      all_car_info.append(_car_info)

  # Sort cars by make and model + year
  sorted_cars: List[CarInfo] = natsorted(all_car_info, key=lambda car: car.name.lower())
  return sorted_cars


def group_by_make(all_car_info: List[CarInfo]) -> Dict[str, List[CarInfo]]:
  sorted_car_info = defaultdict(list)
  for car_info in all_car_info:
    sorted_car_info[car_info.make].append(car_info)
  return dict(sorted_car_info)


def generate_cars_md(all_car_info: List[CarInfo], template_fn: str) -> str:
  with open(template_fn, "r") as f:
    template = jinja2.Template(f.read(), trim_blocks=True, lstrip_blocks=True)

  footnotes = [fn.value.text for fn in get_all_footnotes()]
  cars_md: str = template.render(all_car_info=all_car_info, PartType=PartType,
                                 group_by_make=group_by_make, footnotes=footnotes,
                                 Column=Column, DashcamReason=DashcamReason)
  return cars_md


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Auto generates supported cars documentation",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument("--template", nargs="+", help="Override default template filenames",
                      default=[CARS_MD_TEMPLATE, PORTS_MD_TEMPLATE])
  parser.add_argument("--out", nargs="+", help="Override default generated filenames",
                      default=[CARS_MD_OUT, PORTS_MD_OUT])
  parser.add_argument("--dashcam-only", nargs="+", help="List of template filenames to export dashcammed cars",
                      default=[PORTS_MD_TEMPLATE])
  args = parser.parse_args()

  for out, template in zip(args.out, args.template, strict=True):
    dashcam_only = any(t == template for t in args.dashcam_only)
    with open(out, 'w') as f:
      f.write(generate_cars_md(get_all_car_info(dashcam_only=dashcam_only), template))
    print(f"Generated and written to {out}")

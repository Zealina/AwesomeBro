#!/usr/bin/env python3

"""Test if JSON is valid and randomize the options"""

import json
import sys
import random
from collections import defaultdict
from typing import Dict


def randomize_options(data: Dict):
    """Randomize the options in the dictionary"""
    if data.get("options") is None:
        raise ValueError("No OPTIONS in data")
    if data.get("correct_option") is None:
        raise ValueError("Correct OPTION is not set")

    correct_option = data["options"][data["correct_option"]]
    random.shuffle(data["options"])
    data["correct_option"] = data["options"].index(correct_option)
    return data


if len(sys.argv) != 2:
    print("Usage: <python valid_json.py \"FILE NAME\"")
    sys.exit(-1)
filename = sys.argv[1]

DATA = []

try:
    with open(filename, 'r') as fs:
        DATA = json.load(fs)
        print(f"{filename} is a valid json!")

    new_data = []
    options_count = defaultdict(int)

    for entry in DATA:
        new_entry = randomize_options(entry)
        new_data.append(new_entry)
        options_count[chr(new_entry["correct_option"] + 65)] += 1

    random.shuffle(new_data)

    with open(filename, 'w') as fs:
        json.dump(new_data, fs, indent=2)

    print("\n---------------------summary---------------------")
    print("The options count are thus:")
    print(dict(sorted(options_count.items())))
    print("Successfully rewrote the file!")
except Exception as e:
    print(f"Invalid file: {e}")

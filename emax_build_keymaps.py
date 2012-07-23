#!/usr/bin/python
# Copyright (C) 2012
# See LICENSE.txt for details.
"""
Convert a template emacs JSON keymapping to one for each platform supported by
sublime: OS X, Linux, and Windows.
"""

# Every "move" key binding needs a copy which does the "extend" variant with a
# context that checks setting.transient_mode_on.

# Every binding in the whole file needs to have a context key that checks
# setting.emacs_on.

import os

__file__ = os.path.abspath(__file__)

import json
import copy

def here(path):
    return os.path.join(os.path.dirname(__file__), path)



def meta(platform):
    if platform == "OSX":
        return "super"
    else:
        return "alt"



def require_setting(mapping, setting):
    mapping.setdefault("context", []).append(
        dict(key=setting,
             operator="equal",
             operand=True))



def add_arg(mapping, name, value):
    mapping.setdefault("args", {})[name] = value



def new_map(kmap, platform, conditional):
    new = []
    for binding in kmap:
        new.append(binding)
        binding['keys'] = [
            k.replace(
                "meta+", meta(platform) + "+"
            ) for k in binding['keys']
        ]
        if conditional:
            require_setting(binding, "emax_enabled")
        if binding.get("command") in ["move", "move_to", "emax_move_sexp"]:
            clone = copy.deepcopy(binding)
            require_setting(clone, "setting.emax_region_active")
            add_arg(clone, "extend", True)
            new.append(clone)
    return new



def for_platform(platform):
    return here("Default ({0}).sublime-keymap".format(platform))



def all_maps(conditional=False):
    template = json.load(open(here("base-keymap.json")))
    for platform in "OSX", "Linux", "Windows":
        cloned = copy.deepcopy(template)
        doubleclone = new_map(cloned, platform, conditional)
        doubleclone.append({
            "keys": [
                meta(platform) + "+ctrl+shift+'",
            ],
            "command": "toggle_emax"
        })
        fn = for_platform(platform)
        tfn = fn + ".new" # atomic but not concurrent
        with open(tfn, "wb") as f:
            f.write(json.dumps(doubleclone, indent=2))
            f.write("\n")
        os.rename(tfn, fn)



if __name__ == '__main__':
    # Generating the keymaps from within the editor is more reliable, as that
    # will honor the globalness setting.
    all_maps()

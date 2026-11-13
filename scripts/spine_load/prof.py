"""Profile one run on a 1000-line document (about 40,000 characters)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flood
import cProfile
import pstats

t = flood.doc(1, 1000)
cProfile.run("flood.spine.run(t,'doc-1')", "/tmp/spine_load_profile.out")
pstats.Stats("/tmp/spine_load_profile.out").sort_stats("cumulative").print_stats(14)

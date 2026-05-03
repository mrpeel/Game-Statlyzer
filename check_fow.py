import re
from pathlib import Path
import json

base_dir = Path(".")
missing = []
with open("missing_data/missing_data.log", "r") as f:
    for line in f:
        m = re.search(r'\] (.*\.csv) \(', line)
        if m:
            missing.append(m.group(1))

for csv_name in missing:
    md_name = csv_name.replace(".csv", ".md")
    # need to find the correct MD name format, wait, verify_ball_by_ball has get_base_filename
    pass

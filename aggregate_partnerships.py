import csv
import re
from pathlib import Path
from collections import defaultdict

def aggregate_stats():
    milestones_dir = Path("game_milestones")
    out_dir = Path("team_season_milestones")
    out_dir.mkdir(exist_ok=True)
    
    def safe_int(val):
        if not val or val == "N/A":
            return 0
        try:
            return int(val)
        except ValueError:
            return 0
    
    # Structure: season_team_key -> { "partnerships": { wicket_num: [rows] }, "fow": { wicket_num: [rows] } }
    grouped_data = defaultdict(lambda: {"partnerships": defaultdict(list), "fow": defaultdict(list)})
    
    csv_files = list(milestones_dir.glob("*.csv"))
    print(f"Found {len(csv_files)} milestone files.")
    
    for csv_file in csv_files:
        stem = csv_file.stem
        match = re.match(r"^(Summer \d{4}-\d{2}) (.+? \d(?:st|nd|rd|th) XI) (\d{4}-\d{2}-\d{2}) (.*)$", stem)
        if not match:
            print(f"Skipping file due to name format: {stem}")
            continue
            
        season = match.group(1)
        team = match.group(2)
        key = f"{season} {team}"
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            
        # wicket_number: only increments on dismissal (used for both files)
        current_wicket_number = 1
        retired_batters_since_last_wicket = []
        current_innings = None
        
        for row in reader:
            name = row.get("Milestone Name", "")
            
            # Skip non-partnership milestones (team 50s, player 50s, etc.)
            if "dismissed" not in name and "retired not out" not in name and "Innings Complete" not in name:
                continue
            
            # Reset counters when the innings changes
            innings = row.get("Innings", "")
            if innings != current_innings:
                current_wicket_number = 1
                retired_batters_since_last_wicket = []
                current_innings = innings
            
            if "dismissed" in name:
                # --- Partnerships file: wicket number stays the same as current ---
                p_runs = safe_int(row.get("Partnership", 0))
                p_balls = safe_int(row.get("Partnership Balls", 0))
                b1 = row.get("Batter 1", "")
                b2 = row.get("Batter 2", "")
                
                grouped_data[key]["partnerships"][current_wicket_number].append({
                    "Wicket Number": current_wicket_number,
                    "Runs": p_runs,
                    "Balls": p_balls,
                    "Batter 1": b1,
                    "Batter 2": b2
                })
                
                # --- Fall of wicket file ---
                fow_runs = safe_int(row.get("Runs since last wicket", 0))
                fow_balls = safe_int(row.get("FOW Balls", 0))
                other_batters = " | ".join(retired_batters_since_last_wicket)
                grouped_data[key]["fow"][current_wicket_number].append({
                    "Wicket Number": current_wicket_number,
                    "Runs": fow_runs,
                    "Balls": fow_balls,
                    "Batter 1": b1,
                    "Batter 2": b2,
                    "Other Batters": other_batters
                })
                
                # Advance wicket number AFTER recording
                current_wicket_number += 1
                retired_batters_since_last_wicket = []
                
            elif "Innings Complete" in name:
                # Final unbroken partnership — record but don't increment
                p_runs = safe_int(row.get("Partnership", 0))
                p_balls = safe_int(row.get("Partnership Balls", 0))
                b1 = row.get("Batter 1", "")
                b2 = row.get("Batter 2", "")
                
                grouped_data[key]["partnerships"][current_wicket_number].append({
                    "Wicket Number": current_wicket_number,
                    "Runs": p_runs,
                    "Balls": p_balls,
                    "Batter 1": b1,
                    "Batter 2": b2
                })
                
                fow_runs = safe_int(row.get("Runs since last wicket", 0))
                fow_balls = safe_int(row.get("FOW Balls", 0))
                other_batters = " | ".join(retired_batters_since_last_wicket)
                grouped_data[key]["fow"][current_wicket_number].append({
                    "Wicket Number": current_wicket_number,
                    "Runs": fow_runs,
                    "Balls": fow_balls,
                    "Batter 1": b1,
                    "Batter 2": b2,
                    "Other Batters": other_batters
                })
                retired_batters_since_last_wicket = []
                
            elif "retired not out" in name:
                # Ends a partnership but stays on the SAME wicket number
                p_runs = int(row.get("Partnership", 0))
                p_balls = int(row.get("Partnership Balls", 0))
                b1 = row.get("Batter 1", "")
                b2 = row.get("Batter 2", "")
                
                grouped_data[key]["partnerships"][current_wicket_number].append({
                    "Wicket Number": current_wicket_number,
                    "Runs": p_runs,
                    "Balls": p_balls,
                    "Batter 1": b1,
                    "Batter 2": b2
                })
                
                # Record retired batter for FOW "Other Batters" column
                batter_name = name.split(" retired not out")[0].strip()
                batter_name_clean = batter_name.replace("*", "")
                if batter_name_clean in b1:
                    retired_batters_since_last_wicket.append(b1)
                elif batter_name_clean in b2:
                    retired_batters_since_last_wicket.append(b2)
                else:
                    retired_batters_since_last_wicket.append(f"{batter_name} (Stats unknown)")

    # Write out the max for each team/season
    for key, data in grouped_data.items():
        # 1. Partnerships.csv
        p_out_path = out_dir / f"{key} Partnerships.csv"
        with open(p_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Wicket Number", "Runs", "Balls", "Batter 1", "Batter 2"])
            writer.writeheader()
            
            for w in sorted(data["partnerships"].keys()):
                rows = data["partnerships"][w]
                if not rows: continue
                best_row = max(rows, key=lambda x: x["Runs"])
                writer.writerow(best_row)
                
        # 2. Fall of wicket.csv
        fow_out_path = out_dir / f"{key} Partnerships - Fall of wicket.csv"
        with open(fow_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Wicket Number", "Runs", "Balls", "Batter 1", "Batter 2", "Other Batters"])
            writer.writeheader()
            
            for w in sorted(data["fow"].keys()):
                rows = data["fow"][w]
                if not rows: continue
                best_row = max(rows, key=lambda x: x["Runs"])
                writer.writerow(best_row)
                
        print(f"Generated aggregations for {key}")

if __name__ == "__main__":
    aggregate_stats()

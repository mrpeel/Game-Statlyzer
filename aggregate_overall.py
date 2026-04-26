import csv
import re
from pathlib import Path
from collections import defaultdict

def aggregate_overall():
    season_dir = Path("team_season_milestones")
    out_dir = Path("overall_records")
    out_dir.mkdir(exist_ok=True)
    
    # Structure: team -> { "partnerships": { wicket_num: [rows] }, "fow": { wicket_num: [rows] } }
    team_data = defaultdict(lambda: {"partnerships": defaultdict(list), "fow": defaultdict(list)})
    
    for csv_file in season_dir.glob("*.csv"):
        stem = csv_file.stem
        
        # Parse: "Summer 2025-26 Laburnum - 5th XI Partnerships" or "Summer 2025-26 Laburnum - 5th XI Partnerships - Fall of wicket"
        match = re.match(r"^(Summer \d{4}-\d{2}) (.+? \d(?:st|nd|rd|th) XI) Partnerships(?: - Fall of wicket)?$", stem)
        if not match:
            print(f"Skipping file due to name format: {stem}")
            continue
            
        season = match.group(1)
        team = match.group(2)
        is_fow = "Fall of wicket" in stem
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        
        for row in reader:
            wicket = int(row.get("Wicket Number", 0))
            row["Season"] = season
            
            if is_fow:
                team_data[team]["fow"][wicket].append(row)
            else:
                team_data[team]["partnerships"][wicket].append(row)
    
    for team, data in team_data.items():
        # 1. Overall Partnerships
        p_out_path = out_dir / f"{team} Overall Partnerships.csv"
        with open(p_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Wicket Number", "Runs", "Balls", "Season", "Batter 1", "Batter 2"])
            writer.writeheader()
            
            for w in sorted(data["partnerships"].keys()):
                rows = data["partnerships"][w]
                if not rows:
                    continue
                best = max(rows, key=lambda x: int(x["Runs"]))
                writer.writerow({
                    "Wicket Number": best["Wicket Number"],
                    "Runs": best["Runs"],
                    "Balls": best["Balls"],
                    "Season": best["Season"],
                    "Batter 1": best["Batter 1"],
                    "Batter 2": best["Batter 2"]
                })
        
        # 2. Overall Fall of Wicket
        fow_out_path = out_dir / f"{team} Overall Partnerships - Fall of wicket.csv"
        with open(fow_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Wicket Number", "Runs", "Balls", "Season", "Batter 1", "Batter 2", "Other Batters"])
            writer.writeheader()
            
            for w in sorted(data["fow"].keys()):
                rows = data["fow"][w]
                if not rows:
                    continue
                best = max(rows, key=lambda x: int(x["Runs"]))
                writer.writerow({
                    "Wicket Number": best["Wicket Number"],
                    "Runs": best["Runs"],
                    "Balls": best["Balls"],
                    "Season": best["Season"],
                    "Batter 1": best["Batter 1"],
                    "Batter 2": best["Batter 2"],
                    "Other Batters": best.get("Other Batters", "")
                })
        
        print(f"Generated overall records for {team}")

if __name__ == "__main__":
    aggregate_overall()

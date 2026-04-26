import csv
import re
from pathlib import Path
from datetime import datetime
import glob

def parse_date_to_season(date_obj):
    year = date_obj.year
    month = date_obj.month
    if month >= 8: # Aug-Dec
        season_year_1 = year
        season_year_2 = year + 1
    else: # Jan-Jul
        season_year_1 = year - 1
        season_year_2 = year
    return f"Summer {season_year_1}/{str(season_year_2)[-2:]}"

def generate_milestones(csv_path):
    print(f"Processing: {csv_path.name}")
    stem = csv_path.stem
    try:
        parts = stem.split(" - ", 1)
        date_str_full = parts[0].strip()
        
        # Parse date
        date_part = date_str_full.split(", ")[1]
        date_obj = datetime.strptime(date_part, "%d %b %Y")
        date_formatted = date_obj.strftime("%Y-%m-%d")
        season = parse_date_to_season(date_obj)
        
        match_teams = parts[1]
        teams = match_teams.split(" v ")
        if "Laburnum" in teams[0]:
            team = teams[0].strip()
            opposition = teams[1].strip()
        else:
            team = teams[1].strip()
            opposition = teams[0].strip()
            
    except Exception as e:
        print(f"Error parsing filename {stem}: {e}")
        return

    # Replace slashes in season for filename
    safe_season = season.replace("/", "-")
    out_filename_base = f"{safe_season} {team} {date_formatted} {opposition}"
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        
    rows = list(reversed(reader))
    
    laburnum_rows = []
    for r in rows:
        if "Laburnum" in r.get("Innings", ""):
            laburnum_rows.append(r)
            
    if not laburnum_rows:
        print(f"No Laburnum innings found in {csv_path.name}")
        return
        
    team_runs = 0
    team_wickets = 0
    prev_team_runs = 0
    prev_team_wickets = 0
    runs_at_last_wicket = 0
    partnership_start_runs = 0
    batters = {}
    crease = []
    milestones = []
    team_50s_reached = 0
    
    def get_batter_stats_str(name):
        if name not in batters:
            return f"{name}(*), 0 (0), 4s: 0, 6s: 0, SR: 0.0"
        b = batters[name]
        star = "*" if not b["out"] else ""
        sr = (b["runs"] / b["balls"] * 100) if b["balls"] > 0 else 0.0
        return f"{name}{star}, {b['runs']} ({b['balls']}), 4s: {b['4s']}, 6s: {b['6s']}, SR: {sr:.1f}"

    def record_milestone(name, over_str, is_retirement=False):
        effective_runs = prev_team_runs if is_retirement else team_runs
        effective_wickets = prev_team_wickets if is_retirement else team_wickets
        
        score_str = f"{effective_wickets}/{effective_runs}"
        
        partnership = effective_runs - partnership_start_runs
        runs_since_last = effective_runs - runs_at_last_wicket
        
        b1_str = get_batter_stats_str(crease[0]) if len(crease) > 0 else ""
        b2_str = get_batter_stats_str(crease[1]) if len(crease) > 1 else ""
        milestones.append({
            "Milestone Name": name,
            "Score": score_str,
            "Overs": over_str,
            "Partnership": str(partnership),
            "Runs since last wicket": str(runs_since_last),
            "Batter 1": b1_str,
            "Batter 2": b2_str
        })
        
    for i, row in enumerate(laburnum_rows):
        ball_str = row.get("Ball", "")
        score_val = row.get("Score", "")
        outcome = row.get("Outcome", "")
        
        match = re.match(r"(\d+)--(\d+)", score_val)
        if match:
            team_wickets = int(match.group(1))
            team_runs = int(match.group(2))
            
        parts = outcome.split(" to ", 1)
        if len(parts) < 2: 
            prev_team_runs = team_runs
            prev_team_wickets = team_wickets
            continue
        
        subparts = parts[1].split(" : ", 1)
        if len(subparts) < 2: 
            prev_team_runs = team_runs
            prev_team_wickets = team_wickets
            continue
        
        batter = subparts[0].strip()
        event = subparts[1].strip()
        
        if batter not in batters:
            batters[batter] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "out": False, "50s_reached": 0}
            
        if batter not in crease:
            if len(crease) < 2:
                crease.append(batter)
            else:
                retired_batter = crease[0]
                for c in crease:
                    seen = False
                    for future_row in laburnum_rows[i:]:
                        future_outcome = future_row.get("Outcome", "")
                        if f" to {c} :" in future_outcome:
                            seen = True
                            break
                    if not seen:
                        retired_batter = c
                        break
                
                crease.remove(retired_batter)
                # Note: "retired not out" means they are not out, so we keep batters[retired_batter]["out"] = False
                record_milestone(f"{retired_batter} retired not out", ball_str, is_retirement=True)
                partnership_start_runs = prev_team_runs
                crease.append(batter)
                
        runs_scored = 0
        balls_faced = 1
        
        if "dismissed" in event:
            balls_faced = 1
            runs_scored = 0
            batters[batter]["out"] = True
        elif "wd" in event:
            balls_faced = 0
            runs_scored = 0
        elif "nb" in event or "b" in event or "lb" in event:
            balls_faced = 1
            runs_scored = 0
        elif "run" in event:
            match_runs = re.search(r"(\d+)\s*run", event)
            if match_runs:
                runs_scored = int(match_runs.group(1))
        elif "No Run" in event:
            runs_scored = 0
            
        batters[batter]["runs"] += runs_scored
        batters[batter]["balls"] += balls_faced
        if runs_scored == 4:
            batters[batter]["4s"] += 1
        elif runs_scored == 6:
            batters[batter]["6s"] += 1
            
        if "dismissed" in event:
            record_milestone(f"{batter} dismissed", ball_str)
            runs_at_last_wicket = team_runs
            partnership_start_runs = team_runs
            if batter in crease:
                crease.remove(batter)
                
        if team_runs // 50 > team_50s_reached:
            team_50s_reached = team_runs // 50
            record_milestone(f"Laburnum reaches {team_50s_reached * 50} runs", ball_str)
            
        if batters[batter]["runs"] // 50 > batters[batter]["50s_reached"]:
            batters[batter]["50s_reached"] = batters[batter]["runs"] // 50
            record_milestone(f"{batter} reaches {batters[batter]['50s_reached'] * 50} runs", ball_str)

        prev_team_runs = team_runs
        prev_team_wickets = team_wickets

    out_dir = Path("game_milestones")
    out_dir.mkdir(exist_ok=True)
    
    csv_out_path = out_dir / f"{out_filename_base}.csv"
    with open(csv_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Milestone Name", "Score", "Overs", "Partnership", "Runs since last wicket", "Batter 1", "Batter 2"])
        writer.writeheader()
        writer.writerows(milestones)
        
    print(f"Successfully generated milestones to:\n- {csv_out_path}")

if __name__ == "__main__":
    generate_milestones(Path("ball_by_ball_data/Sat, 21 Feb 2026 - Laburnum - 5th XI v Doncaster - 5th XI.csv"))

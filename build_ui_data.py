import json
import os
import re
from pathlib import Path
from datetime import datetime

def parse_date_to_season(date_obj):
    year = date_obj.year
    month = date_obj.month
    if month >= 8:
        return f"Summer {year}/{str(year + 1)[-2:]}"
    else:
        return f"Summer {year - 1}/{str(year)[-2:]}"

def build_data_map():
    base_dir = Path(__file__).parent
    bbb_dir = base_dir / "ball_by_ball_data"
    milestones_dir = base_dir / "game_milestones"
    results_dir = base_dir / "game_results"
    
    games = []
    
    for bbb_file in bbb_dir.glob("*.csv"):
        stem = bbb_file.stem
        try:
            parts = stem.split(" - ", 1)
            date_str_full = parts[0].strip()
            date_part = date_str_full.split(", ")[1] if ", " in date_str_full else date_str_full
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
                
            safe_season = season.replace("/", "-")
            out_filename_base = f"{safe_season} {team} {date_formatted} {opposition}"
            
            milestone_path = milestones_dir / f"{out_filename_base}.csv"
            scorecard_path = results_dir / f"{out_filename_base}.md"
            
            games.append({
                "name": f"{date_formatted} - {team} vs {opposition}",
                "season": season,
                "team": team,
                "ball_by_ball": f"ball_by_ball_data/{bbb_file.name}",
                "milestones": f"game_milestones/{milestone_path.name}" if milestone_path.exists() else None,
                "scorecard": f"game_results/{scorecard_path.name}" if scorecard_path.exists() else None
            })
            
        except Exception as e:
            print(f"Error parsing {stem}: {e}")
            
    # Sort games by date descending
    games.sort(key=lambda x: x["name"], reverse=True)
    
    ui_dir = base_dir / "ui"
    ui_dir.mkdir(exist_ok=True)
    
    with open(ui_dir / "data_map.json", "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2)
        
    print(f"Generated data_map.json with {len(games)} games.")

if __name__ == "__main__":
    build_data_map()

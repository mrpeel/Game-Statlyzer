import csv
import re
import os
from pathlib import Path
from datetime import datetime

def parse_date_to_season(date_obj):
    year = date_obj.year
    month = date_obj.month
    if month >= 8:
        return f"Summer {year}/{str(year + 1)[-2:]}"
    else:
        return f"Summer {year - 1}/{str(year)[-2:]}"

def get_base_filename(csv_path):
    stem = csv_path.stem
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
        return f"{safe_season} {team} {date_formatted} {opposition}", season, team, date_formatted
    except Exception as e:
        return None, None, None, None

def get_scorecard_details(md_path):
    if not md_path.exists():
        return None, [], 0
        
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    blocks = re.split(r'\n## ', content)
    for block in blocks:
        if ('LAB' in block or 'Laburnum' in block) and '### Batting' in block:
            # 1. Total Overs
            expected_overs = None
            match = re.search(r'\*\*Total:\*\* TOTAL\s+\|\s+([\d\.]+)\s+Overs', block)
            if match:
                expected_overs = float(match.group(1))
            
            # 2. Batting scores
            scores = []
            batting_match = re.search(r'### Batting\n\| Batting \|.*?\|\n\| --- \|.*?\|\n((?:\|.*?\|\n)+)', block)
            if batting_match:
                rows = batting_match.group(1).strip().split('\n')
                for row in rows:
                    cols = [c.strip() for c in row.split('|') if c.strip()]
                    if len(cols) >= 4:
                        wicket_info = cols[1]
                        if 'did not bat' in wicket_info.lower():
                            continue
                        runs_str = cols[2].replace('*', '').strip()
                        runs = int(runs_str) if runs_str.isdigit() else 0
                        
                        balls_str = cols[3].strip()
                        if balls_str.isdigit():
                            balls = int(balls_str)
                        else:
                            balls = runs * 2 if runs > 0 else 5
                            
                        scores.append({'runs': runs, 'balls': balls})
            
            # 3. Extras
            extras = 0
            extras_match = re.search(r'\*\*Extras:\*\* Extras\s+.*?\s+\|\s+(\d+)', block)
            if extras_match:
                extras = int(extras_match.group(1))
                
            return expected_overs, scores, extras
            
    return None, [], 0

def get_season_records(season, team):
    base_dir = Path(__file__).parent
    records_dir = base_dir / "team_season_milestones"
    safe_season = season.replace("/", "-")
    file_path = records_dir / f"{safe_season} {team} Partnerships.csv"
    
    records = {}
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                w = int(row.get("Wicket Number", 0))
                r = int(row.get("Runs", 0))
                if w > 0:
                    records[w] = r
    return records

def check_potential_records(scores, extras, expected_overs, season_records):
    potential_records = []
    
    if len(scores) < 2:
        return []
        
    for s in scores:
        s['balls_remaining'] = s['balls']
        
    active_batters = [scores[0], scores[1]]
    next_batter_idx = 2
    
    total_innings_balls = 0
    if expected_overs is not None:
        completed_overs = int(expected_overs)
        decimal_part = expected_overs - completed_overs
        total_innings_balls = (completed_overs * 6) + int(decimal_part * 10)
    else:
        total_innings_balls = sum(s['balls'] for s in scores) + extras
        
    if total_innings_balls <= 0:
        total_innings_balls = 1
    
    for wicket_num in range(1, 11):
        if len(active_batters) < 2:
            break
            
        b1 = active_batters[0]
        b2 = active_batters[1]
        
        partnership_balls_per_batter = min(b1['balls_remaining'], b2['balls_remaining'])
        combined_balls = partnership_balls_per_batter * 2
        
        runs1 = (partnership_balls_per_batter / b1['balls']) * b1['runs'] if b1['balls'] > 0 else 0
        runs2 = (partnership_balls_per_batter / b2['balls']) * b2['runs'] if b2['balls'] > 0 else 0
        
        partnership_extras = (combined_balls / total_innings_balls) * extras
        
        total_estimate = runs1 + runs2 + partnership_extras
        upper_bound = total_estimate * 1.10
        
        record_runs = season_records.get(wicket_num, 0)
        
        if upper_bound >= record_runs and upper_bound > 0:
            potential_records.append({
                "wicket": wicket_num,
                "potential": int(round(upper_bound)),
                "record": record_runs
            })
            
        b1['balls_remaining'] -= partnership_balls_per_batter
        b2['balls_remaining'] -= partnership_balls_per_batter
        
        if b1['balls_remaining'] <= 0 and b2['balls_remaining'] <= 0:
            active_batters.remove(b1)
        elif b1['balls_remaining'] <= 0:
            active_batters.remove(b1)
        else:
            active_batters.remove(b2)
            
        if next_batter_idx < len(scores):
            active_batters.append(scores[next_batter_idx])
            next_batter_idx += 1
            
    return potential_records

def verify_data():
    base_dir = Path(__file__).parent
    bbb_dir = base_dir / "ball_by_ball_data"
    results_dir = base_dir / "game_results"
    
    missing_data = []
    
    for csv_path in bbb_dir.glob("*.csv"):
        base_name, season, team, date_formatted = get_base_filename(csv_path)
        if not base_name:
            continue
            
        md_path = results_dir / f"{base_name}.md"
        expected_overs, scores, extras = get_scorecard_details(md_path)
        
        if expected_overs is None:
            continue
            
        max_ball = 0.0
        has_data = False
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                innings = row.get("Innings", "")
                if "Laburnum" in innings:
                    has_data = True
                    ball_str = row.get("Ball", "0")
                    try:
                        b = float(ball_str)
                        if b > max_ball:
                            max_ball = b
                    except ValueError:
                        pass
                        
        is_missing = False
        discrepancy_type = ""
        actual_overs = 0.0
        
        if not has_data:
            is_missing = True
            discrepancy_type = "NO DATA"
        else:
            completed_overs = int(max_ball)
            decimal_part = max_ball - completed_overs
            actual_overs = completed_overs + decimal_part
            
            if (expected_overs - actual_overs) > 2.0:
                is_missing = True
                discrepancy_type = "TRUNCATED"
                
        if is_missing:
            season_records = get_season_records(season, team)
            potentials = check_potential_records(scores, extras, expected_overs, season_records)
            
            missing_data.append({
                "type": discrepancy_type,
                "file": csv_path.name,
                "season": season,
                "team": team,
                "date": date_formatted,
                "expected": expected_overs,
                "actual": actual_overs,
                "potentials": potentials
            })
            
    # Sort logically
    missing_data.sort(key=lambda x: (x["season"], x["team"], x["date"]), reverse=True)
    
    missing_dir = base_dir / "missing_data"
    missing_dir.mkdir(exist_ok=True)
    
    # Write LOG
    with open(missing_dir / "missing_data.log", "w", encoding="utf-8") as f:
        f.write(f"Found {len(missing_data)} games with missing or truncated Laburnum batting data:\n\n")
        for item in missing_data:
            pot_str = " [POTENTIAL RECORD]" if item['potentials'] else ""
            f.write(f"[{item['type']}]{pot_str} {item['file']} (Expected: {item['expected']} overs, Actual: {item['actual']:.1f} overs)\n")
            
    # Write MD
    md_content = "# Incomplete Ball-by-Ball Data Report\n\n"
    md_content += f"Found **{len(missing_data)} games** with missing or truncated Laburnum batting data.\n"
    md_content += "A game is flagged as `TRUNCATED` if the last recorded ball in the CSV is more than 2 overs short of the official scorecard total.\n\n"
    md_content += "Games tagged with `POTENTIAL RECORD` indicate that a pro-rata estimation (based on balls faced and extras) theoretically could have produced a partnership that beats or ties the current season record for that wicket.\n\n"
    
    current_season = ""
    for item in missing_data:
        if item['season'] != current_season:
            current_season = item['season']
            md_content += f"## {current_season}\n\n"
            
        pot_tag = " 🚨 **POTENTIAL RECORD**" if item['potentials'] else ""
        
        md_content += f"### {item['team']} ({item['date']}){pot_tag}\n"
        md_content += f"- **Status**: `{item['type']}`\n"
        md_content += f"- **Expected Overs**: {item['expected']}\n"
        md_content += f"- **Recorded Overs**: {item['actual']:.1f}\n"
        md_content += f"- **File**: `{item['file']}`\n"
        
        if item['potentials']:
            md_content += "- **Potential Records Found**:\n"
            for p in item['potentials']:
                md_content += f"  - Wicket {p['wicket']}: Estimated Upper Bound **{p['potential']}** (vs Record {p['record']})\n"
                
        md_content += "\n"
        
    with open(missing_dir / "missing_data.md", "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"Generated missing_data.log and missing_data.md with {len(missing_data)} discrepancies.")

if __name__ == "__main__":
    verify_data()

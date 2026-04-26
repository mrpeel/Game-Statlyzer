import csv
import re
from pathlib import Path
from datetime import datetime
import glob
import os

def parse_scorecard(filepath):
    """Parse a Markdown scorecard for Laburnum innings, batting, and FOW data."""
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, 'r', encoding="utf-8") as f:
        content = f.read()
    
    # Split by innings (##)
    innings_blocks = re.split(r'\n## ', content)
    laburnum_innings = []
    
    # Also extract the game metadata from the top
    match_title = ""
    title_match = re.search(r'^# (.*)', content)
    if title_match:
        match_title = title_match.group(1).strip()
        
    for block in innings_blocks:
        # Check if it's a Laburnum innings
        if 'LAB' in block or 'Laburnum' in block:
            header = block.split('\n')[0].strip()
            
            # Find Batting table
            batting_match = re.search(r'### Batting\n\| Batting \|.*?\|\n\| --- \|.*?\|\n((?:\|.*?\|\n)+)', block)
            batting_data = []
            if batting_match:
                rows = batting_match.group(1).strip().split('\n')
                for row in rows:
                    cols = [c.strip() for c in row.split('|') if c.strip()]
                    if len(cols) >= 3:
                        name = cols[0]
                        wicket_info = cols[1]
                        if 'did not bat' in wicket_info.lower():
                            continue
                        
                        runs_str = cols[2].replace('*', '').strip()
                        runs = int(runs_str) if runs_str.isdigit() else 0
                        
                        balls = 0
                        if len(cols) > 3:
                            balls_str = cols[3].strip()
                            balls = int(balls_str) if balls_str.isdigit() else 0
                            
                        fours = 0
                        if len(cols) > 4:
                            fours_str = cols[4].strip()
                            fours = int(fours_str) if fours_str.isdigit() else 0
                            
                        sixes = 0
                        if len(cols) > 5:
                            sixes_str = cols[5].strip()
                            sixes = int(sixes_str) if sixes_str.isdigit() else 0
                            
                        batting_data.append({
                            'name': name,
                            'runs': runs,
                            'balls': balls,
                            '4s': fours,
                            '6s': sixes,
                            'out': 'not out' not in wicket_info.lower() and 'retired' not in wicket_info.lower()
                        })
            
            # Find Fall of Wickets
            fow_match = re.search(r'### Fall of Wickets\n((?:- .*?\n)+)', block)
            fow_data = []
            if fow_match:
                rows = fow_match.group(1).strip().split('\n')
                for row in rows:
                    # Pattern: - 1-10 - Jason Hugo (c: ******** b: H Mills)
                    m = re.match(r'- (\d+)-(\d+) - (.*?) \(', row)
                    if m:
                        fow_data.append({
                            'wicket': int(m.group(1)),
                            'score': int(m.group(2)),
                            'player': m.group(3).strip()
                        })
            
            # Extract Total Score
            total_score = 0
            total_match = re.search(r'\*\*Total:\*\* TOTAL\s+.*\|\s+(\d+)\s*$', block)
            if total_match:
                total_score = int(total_match.group(1))
            elif batting_data:
                extras_match = re.search(r'\*\*Extras:\*\* Extras\s+.*?\s+\|\s+(\d+)', block)
                extras = int(extras_match.group(1)) if extras_match else 0
                total_score = sum(b['runs'] for b in batting_data) + extras

            if batting_data or fow_data:
                laburnum_innings.append({
                    'name': header,
                    'batting': batting_data,
                    'fow': fow_data,
                    'total_score': total_score
                })
    
    return laburnum_innings

def get_scorecard_path(csv_path):
    """Find the corresponding Markdown scorecard for a given ball-by-ball CSV."""
    stem = csv_path.stem
    try:
        parts = stem.split(" - ", 1)
        if len(parts) < 2: return None
        
        date_str_full = parts[0].strip()
        # Handle formats like "Sat, 11 Jan 2025"
        if ", " in date_str_full:
            date_part = date_str_full.split(", ")[1]
        else:
            date_part = date_str_full
            
        date_obj = datetime.strptime(date_part, "%d %b %Y")
        date_formatted = date_obj.strftime("%Y-%m-%d")
        
        match_teams = parts[1]
        teams = match_teams.split(" v ")
        if len(teams) < 2: return None
        
        if "Laburnum" in teams[0]:
            team = teams[0].strip()
            opposition = teams[1].strip()
        else:
            team = teams[1].strip()
            opposition = teams[0].strip()
            
        # Clean team names for matching (remove "CC" or other suffix if needed)
        # But our scraper uses full names, so let's try exact first.
        
        results_dir = Path("game_results")
        if not results_dir.exists(): return None
        
        # Pattern matching: date and team name
        # We use wildcards because the season is at the start and team names might vary slightly
        pattern = f"*{date_formatted}*{opposition}*.md"
        matches = list(results_dir.glob(pattern))
        if not matches:
            pattern = f"*{date_formatted}*.md"
            matches = list(results_dir.glob(pattern))
            
        if matches:
            # Pick the best match (one containing Laburnum team name)
            for m in matches:
                if team in m.name:
                    return m
            return matches[0]
            
    except Exception as e:
        # print(f"Lookup error for {csv_path.name}: {e}")
        pass
    return None

def generate_milestones_from_scorecard(scorecard_path, csv_path):
    """Reconstruct milestones from a Markdown scorecard when ball-by-ball is missing."""
    print(f"Fallback: Using scorecard {scorecard_path.name} for {csv_path.name}")
    
    innings_data = parse_scorecard(scorecard_path)
    if not innings_data:
        print(f"  No Laburnum data found in scorecard {scorecard_path.name}")
        return False
        
    # Get metadata for output filename
    stem = csv_path.stem
    try:
        parts = stem.split(" - ", 1)
        date_part = parts[0].split(", ")[1]
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
    except Exception:
        # Fallback metadata from filename
        date_formatted = "unknown"
        season = "unknown"
        team = "Laburnum"
        opposition = "Opposition"
    
    safe_season = season.replace("/", "-")
    out_filename_base = f"{safe_season} {team} {date_formatted} {opposition}"
    
    all_milestones = []
    
    # Read content once for regex searches
    with open(scorecard_path, 'r', encoding="utf-8") as f:
        content = f.read()

    for inn in innings_data:
        batting = inn['batting']
        fow_list = inn['fow']
        total_score = inn['total_score']
        innings_name = inn['name']
        
        if not batting: continue
        
        # Try to find overs for this specific innings block
        innings_overs = "N/A"
        block_match = re.search(rf'## {re.escape(innings_name)}.*?\|\s+([\d\.]+)\s+Overs', content, re.DOTALL)
        if block_match:
            innings_overs = block_match.group(1)

        milestones = []
        crease = []
        if len(batting) >= 1:
            crease.append(batting[0]['name'])
        if len(batting) >= 2:
            crease.append(batting[1]['name'])
            
        partnership_start_score = 0
        next_batter_idx = 2
        
        def get_batter_stats(name):
            for b in batting:
                if b['name'] == name:
                    star = "*" if not b['out'] else ""
                    return f"{b['name']}{star}, {b['runs']} ({b['balls']}), 4s: {b['4s']}, 6s: {b['6s']}, SR: 0.0"
            return f"{name}, 0 (0), 4s: 0, 6s: 0, SR: 0.0"

        for fow in fow_list:
            out_player = fow['player'].strip()
            
            # Handle retirements
            while out_player not in crease and next_batter_idx < len(batting):
                # print(f"    Retirement: {crease[0] if crease else 'None'} replaced by {batting[next_batter_idx]['name']}")
                if len(crease) > 0:
                    crease.pop(0)
                crease.append(batting[next_batter_idx]['name'])
                next_batter_idx += 1
            
            score = fow['score']
            p_total = score - partnership_start_score
            
            b1_str = get_batter_stats(crease[0]) if len(crease) > 0 else ""
            b2_str = get_batter_stats(crease[1]) if len(crease) > 1 else ""
            
            milestones.append({
                "Innings": innings_name,
                "Milestone Name": f"{out_player} dismissed",
                "Score": f"{fow['wicket']}/{score}",
                "Overs": "N/A",
                "Partnership": str(p_total),
                "Partnership Balls": "N/A",
                "Runs since last wicket": str(p_total),
                "FOW Balls": "N/A",
                "Batter 1": b1_str,
                "Batter 2": b2_str
            })
            
            partnership_start_score = score
            
            if out_player in crease:
                crease.remove(out_player)
            
            if next_batter_idx < len(batting):
                crease.append(batting[next_batter_idx]['name'])
                next_batter_idx += 1
        
        # Final partnership
        p_total = total_score - partnership_start_score
        b1_str = get_batter_stats(crease[0]) if len(crease) > 0 else ""
        b2_str = get_batter_stats(crease[1]) if len(crease) > 1 else ""
        final_wickets = len(fow_list)
        
        milestones.append({
            "Innings": innings_name,
            "Milestone Name": "Innings Complete",
            "Score": f"{final_wickets}/{total_score}",
            "Overs": innings_overs,
            "Partnership": str(p_total),
            "Partnership Balls": "N/A",
            "Runs since last wicket": str(p_total),
            "FOW Balls": "N/A",
            "Batter 1": b1_str,
            "Batter 2": b2_str
        })
            
        all_milestones.extend(milestones)
        
    if not all_milestones:
        return False
        
    out_dir = Path("game_milestones")
    out_dir.mkdir(exist_ok=True)
    csv_out_path = out_dir / f"{out_filename_base}.csv"
    
    with open(csv_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Innings", "Milestone Name", "Score", "Overs", "Partnership", "Partnership Balls", "Runs since last wicket", "FOW Balls", "Batter 1", "Batter 2"])
        writer.writeheader()
        writer.writerows(all_milestones)
        
    print(f"  Successfully generated milestones from scorecard to:\n  - {csv_out_path}")
    return True

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
    
    # Find all distinct Laburnum innings (e.g., "1st Innings - Laburnum - 5th XI", "2nd Innings - ...")
    laburnum_innings_names = []
    for r in rows:
        inn = r.get("Innings", "")
        if "Laburnum" in inn and inn not in laburnum_innings_names:
            laburnum_innings_names.append(inn)
            
    if not laburnum_innings_names:
        print(f"No Laburnum innings found in {csv_path.name}")
        # Try fallback
        scorecard_path = get_scorecard_path(csv_path)
        if scorecard_path:
            return generate_milestones_from_scorecard(scorecard_path, csv_path)
        return False
    
    # Collect all milestones across all innings
    all_milestones = []
    
    for innings_name in laburnum_innings_names:
        laburnum_rows = [r for r in rows if r.get("Innings", "") == innings_name]
        
        team_runs = 0
        team_wickets = 0
        prev_team_runs = 0
        prev_team_wickets = 0
        runs_at_last_wicket = 0
        partnership_start_runs = 0
        partnership_balls = 0
        fow_balls = 0
        batters = {}
        crease = []
        milestones = []
        team_50s_reached = 0
        ball_str = ""
        partnership_start_stats = {}  # snapshot of each batter's stats at partnership start
        
        def snapshot_partnership_stats():
            """Snapshot current stats for all batters on the crease."""
            for name in crease:
                if name in batters:
                    b = batters[name]
                    partnership_start_stats[name] = {"runs": b["runs"], "balls": b["balls"], "4s": b["4s"], "6s": b["6s"]}
                else:
                    partnership_start_stats[name] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0}
        
        def get_batter_stats_str(name):
            """Get batter's total innings stats string."""
            if name not in batters:
                return f"{name}(*), 0 (0), 4s: 0, 6s: 0, SR: 0.0"
            b = batters[name]
            star = "*" if not b["out"] else ""
            sr = (b["runs"] / b["balls"] * 100) if b["balls"] > 0 else 0.0
            return f"{name}{star}, {b['runs']} ({b['balls']}), 4s: {b['4s']}, 6s: {b['6s']}, SR: {sr:.1f}"

        def get_partnership_batter_stats_str(name):
            """Get batter's stats for the current partnership only (delta from snapshot)."""
            if name not in batters:
                return f"{name}(*), 0 (0), 4s: 0, 6s: 0, SR: 0.0"
            b = batters[name]
            start = partnership_start_stats.get(name, {"runs": 0, "balls": 0, "4s": 0, "6s": 0})
            p_runs = b["runs"] - start["runs"]
            p_balls = b["balls"] - start["balls"]
            p_4s = b["4s"] - start["4s"]
            p_6s = b["6s"] - start["6s"]
            star = "*" if not b["out"] else ""
            sr = (p_runs / p_balls * 100) if p_balls > 0 else 0.0
            return f"{name}{star}, {p_runs} ({p_balls}), 4s: {p_4s}, 6s: {p_6s}, SR: {sr:.1f}"

        def record_milestone(name, over_str, is_retirement=False):
            nonlocal partnership_balls, fow_balls
            effective_runs = prev_team_runs if is_retirement else team_runs
            effective_wickets = prev_team_wickets if is_retirement else team_wickets
            
            score_str = f"{effective_wickets}/{effective_runs}"
            
            partnership = effective_runs - partnership_start_runs
            runs_since_last = effective_runs - runs_at_last_wicket
            
            b1_str = get_partnership_batter_stats_str(crease[0]) if len(crease) > 0 else ""
            b2_str = get_partnership_batter_stats_str(crease[1]) if len(crease) > 1 else ""
            milestones.append({
                "Innings": innings_name,
                "Milestone Name": name,
                "Score": score_str,
                "Overs": over_str,
                "Partnership": str(partnership),
                "Partnership Balls": str(partnership_balls),
                "Runs since last wicket": str(runs_since_last),
                "FOW Balls": str(fow_balls),
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
                    if len(crease) == 2:
                        snapshot_partnership_stats()
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
                    
                    # Record milestone before removing the batter so their stats are captured in the milestone row
                    record_milestone(f"{retired_batter} retired not out", ball_str, is_retirement=True)
                    partnership_start_runs = prev_team_runs
                    partnership_balls = 0
                    
                    crease.remove(retired_batter)
                    crease.append(batter)
                    snapshot_partnership_stats()
                    
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
            
            # Track partnership and FOW balls (legal deliveries only, wides don't count)
            if balls_faced > 0:
                partnership_balls += 1
                fow_balls += 1
                
            if "dismissed" in event:
                record_milestone(f"{batter} dismissed", ball_str)
                runs_at_last_wicket = team_runs
                partnership_start_runs = team_runs
                partnership_balls = 0
                fow_balls = 0
                if batter in crease:
                    crease.remove(batter)
                snapshot_partnership_stats()
                    
            if team_runs // 50 > team_50s_reached:
                team_50s_reached = team_runs // 50
                record_milestone(f"Laburnum reaches {team_50s_reached * 50} runs", ball_str)
                
            if batters[batter]["runs"] // 50 > batters[batter]["50s_reached"]:
                batters[batter]["50s_reached"] = batters[batter]["runs"] // 50
                record_milestone(f"{batter} reaches {batters[batter]['50s_reached'] * 50} runs", ball_str)

            prev_team_runs = team_runs
            prev_team_wickets = team_wickets

        # Record the final unbroken partnership if the innings ended with batters still at the crease
        # Don't record if the last milestone was a dismissal on the same ball (i.e., all out)
        last_was_dismissal = milestones and "dismissed" in milestones[-1].get("Milestone Name", "")
        if len(crease) > 0 and not last_was_dismissal:
            record_milestone("Innings Complete", ball_str)
        
        all_milestones.extend(milestones)

    out_dir = Path("game_milestones")
    out_dir.mkdir(exist_ok=True)
    
    csv_out_path = out_dir / f"{out_filename_base}.csv"
    with open(csv_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Innings", "Milestone Name", "Score", "Overs", "Partnership", "Partnership Balls", "Runs since last wicket", "FOW Balls", "Batter 1", "Batter 2"])
        writer.writeheader()
        writer.writerows(all_milestones)
        
    print(f"Successfully generated milestones to:\n- {csv_out_path}")
    return True

if __name__ == "__main__":
    data_dir = Path("ball_by_ball_data")
    csv_files = list(data_dir.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files in {data_dir.name}/")
    
    missing_data = []
    
    for csv_file in csv_files:
        try:
            success = generate_milestones(csv_file)
            if not success:
                # If no Laburnum data in CSV, try fallback directly
                scorecard_path = get_scorecard_path(csv_file)
                if scorecard_path:
                    generate_milestones_from_scorecard(scorecard_path, csv_file)
        except Exception as e:
            print(f"Failed processing {csv_file.name}: {e}")
    
    # Log games with missing Laburnum data
    for csv_file in csv_files:
        with open(csv_file, "r", encoding="utf-8") as f:
            content = f.read()
        if "Laburnum" not in content:
            missing_data.append(f"NO DATA: {csv_file.name}")
        elif "Innings" in content:
            import re as _re
            innings = set(_re.findall(r"Innings.*Laburnum[^\r\n]*", content))
            if not innings:
                missing_data.append(f"NO LABURNUM INNINGS: {csv_file.name}")
    
    log_path = Path("missing_data.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Games with missing Laburnum batting data ({len(missing_data)} total):\n\n")
        for entry in sorted(missing_data):
            f.write(f"  {entry}\n")
    
    print(f"\n{len(missing_data)} games with missing data logged to {log_path}")

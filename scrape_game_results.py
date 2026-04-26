"""
Scrape game results (scorecards) from play.cricket.com.au/competitions.

Navigation flow:
  1. /competitions → search "Laburnum Cricket Club"
  2. Select season from custom dropdown (fieldset radio buttons)
  3. Click team link → /grade page with matches
  4. Click each match link → /match page with scorecard
  5. Toggle innings via radio buttons, extract tables + FOW
  6. Browser back to return to matches list
"""
import time
import re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

SEASONS = [
    "Summer 2025/26",
    "Summer 2024/25",
    "Summer 2023/24"
]

TEAMS = [
    "Laburnum - 1st XI",
    "Laburnum - 2nd XI",
    "Laburnum - 3rd XI",
    "Laburnum - 4th XI",
    "Laburnum - 5th XI"
]

OUTPUT_DIR = Path("game_results")


def safe_filename(s):
    """Replace characters that are invalid in filenames."""
    return s.replace("/", "-").replace(":", "").replace("?", "").replace('"', "")


def parse_date_from_text(text):
    """Parse date from text like 'Saturday, 4 October 2025 at 12:30 pm'."""
    try:
        match = re.search(r'(\d+\s+\w+\s+\d{4})', text)
        if match:
            return datetime.strptime(match.group(1), "%d %B %Y")
    except (ValueError, AttributeError):
        pass
    return None


def format_table(headers, rows):
    """Format headers and rows into a markdown table."""
    if not headers and not rows:
        return ""
    if not headers and rows:
        headers = [f"Col{i+1}" for i in range(len(rows[0]))]
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        # Escape pipe characters in cell values
        escaped = [c.replace("|", "\\|") for c in padded[:len(headers)]]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def scrape_innings_data(page):
    """Scrape batting, bowling, fielding, FOW from the current innings view.
    
    DOM structure (from play.cricket.com.au):
      - 3 tables: Batting, Bowling, Fielding
        - Table class: w-play-match-centre-scorecard__table
        - Batting headers: Player, (how out), R, B, 4s, 6s, SR
        - Bowling headers: Bowler, O, M, R, W, Econ, Wd, NB  
        - Fielding headers: Fielder, C, RO, ST
        - Extras in tbody, Total in tfoot
      - Fall of Wickets: div.w-play-match-centre-scorecard__wickets
        - ul > li with score and batter info
    """
    innings_data = {
        "batting": {"headers": [], "rows": [], "extras": "", "total": ""},
        "bowling": {"headers": [], "rows": []},
        "fielding": {"headers": [], "rows": []},
        "fall_of_wickets": []
    }

    # Get all visible tables
    tables = page.locator("table.w-play-match-centre-scorecard__table").all()
    visible_tables = [t for t in tables if t.is_visible()]
    
    for table in visible_tables:
        try:
            # Get headers (short form - the text inside spans, cleaned up)
            header_els = table.locator("thead th").all()
            headers = []
            for h in header_els:
                # Headers have format "Full Name\nAbbr" - take the abbreviated version
                full_text = h.inner_text().strip()
                # Use the last line (abbreviation) if multi-line, or the full text
                parts = full_text.split("\n")
                headers.append(parts[-1].strip() if len(parts) > 1 else full_text)

            # Get body rows
            rows = []
            body_rows = table.locator("tbody tr").all()
            for row in body_rows:
                cells = row.locator("td").all()
                if cells:
                    row_data = [c.inner_text().strip().replace("\n", " ") for c in cells]
                    rows.append(row_data)

            # Get tfoot for total
            total_text = ""
            tfoot_rows = table.locator("tfoot tr").all()
            for trow in tfoot_rows:
                total_text = trow.inner_text().strip().replace("\n", " | ")

            # Classify table by headers
            header_lower = " ".join(headers).lower()

            if "batting" in header_lower or ("r" in headers and "b" in headers and "sr" in headers):
                innings_data["batting"]["headers"] = headers
                for row_data in rows:
                    joined = " ".join(row_data).lower()
                    if "extras" in joined:
                        innings_data["batting"]["extras"] = " | ".join(row_data)
                    else:
                        innings_data["batting"]["rows"].append(row_data)
                if total_text:
                    innings_data["batting"]["total"] = total_text

            elif "bowling" in header_lower or ("o" in headers and "w" in headers):
                innings_data["bowling"]["headers"] = headers
                innings_data["bowling"]["rows"] = rows

            elif "fielding" in header_lower or ("c" in headers):
                innings_data["fielding"]["headers"] = headers
                innings_data["fielding"]["rows"] = rows

        except Exception as e:
            print(f"      Warning: table extraction error: {e}")

    # Extract Fall of Wickets (not in a table - it's a list)
    try:
        fow_items = page.locator("li.w-play-match-centre-scorecard__wicket").all()
        visible_fow = [f for f in fow_items if f.is_visible()]
        for item in visible_fow:
            text = item.inner_text().strip().replace("\n", " - ")
            innings_data["fall_of_wickets"].append(text)
    except Exception:
        pass

    return innings_data


def write_match_markdown(filepath, match_info, innings_list):
    """Write match data to a markdown file."""
    lines = []

    lines.append(f"# {match_info.get('title', 'Match')}")
    if match_info.get("date"):
        lines.append(f"**Date:** {match_info['date']}")
    if match_info.get("venue"):
        lines.append(f"**Venue:** {match_info['venue']}")
    if match_info.get("result"):
        lines.append(f"**Result:** {match_info['result']}")
    if match_info.get("format"):
        lines.append(f"**Format:** {match_info['format']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for innings in innings_list:
        innings_name = innings.get("name", "Innings")
        lines.append(f"## {innings_name}")
        lines.append("")

        data = innings.get("data", {})

        # Batting
        if data.get("batting", {}).get("rows"):
            lines.append("### Batting")
            batting = data["batting"]
            table = format_table(batting["headers"], batting["rows"])
            if table:
                lines.append(table)
            if batting.get("extras"):
                lines.append(f"\n**Extras:** {batting['extras']}")
            if batting.get("total"):
                lines.append(f"\n**Total:** {batting['total']}")
            lines.append("")

        # Bowling
        if data.get("bowling", {}).get("rows"):
            lines.append("### Bowling")
            bowling = data["bowling"]
            table = format_table(bowling["headers"], bowling["rows"])
            if table:
                lines.append(table)
            lines.append("")

        # Fielding
        if data.get("fielding", {}).get("rows"):
            lines.append("### Fielding")
            fielding = data["fielding"]
            table = format_table(fielding["headers"], fielding["rows"])
            if table:
                lines.append(table)
            lines.append("")

        # Fall of Wickets
        if data.get("fall_of_wickets"):
            lines.append("### Fall of Wickets")
            for fow in data["fall_of_wickets"]:
                lines.append(f"- {fow}")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def navigate_to_club(page):
    """Navigate to competitions page and select Laburnum Cricket Club."""
    print("Navigating to competitions page...")
    page.goto("https://play.cricket.com.au/competitions", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Use the competition search input (NOT the nav bar search)
    # The correct input has name="competitionSearch"
    print("Searching for Laburnum Cricket Club...")
    search_input = page.locator('input[name="competitionSearch"]')
    search_input.fill("Laburnum")
    page.wait_for_timeout(2000)

    page.get_by_text("Laburnum Cricket Club", exact=True).click()
    page.wait_for_timeout(4000)
    print("Selected Laburnum Cricket Club.")


def select_season(page, season):
    """Select a season from the custom dropdown on the club page.
    
    The dropdown is: button#season[role="listbox"] which opens a list
    of o-dropdown__options-item elements.
    """
    try:
        # Click the season dropdown trigger button
        season_btn = page.locator("button#season")
        season_btn.click()
        page.wait_for_timeout(1000)

        # Click the season option
        # Options are in li.o-dropdown__options-item > button.o-dropdown__item-trigger
        option = page.locator(f"button.o-dropdown__item-trigger:has-text('{season}')")
        option.click()
        page.wait_for_timeout(3000)
        print(f"  Selected season: {season}")
        return True

    except Exception as e:
        print(f"  Failed to select season '{season}': {e}")
        # Try escape to close any open dropdown
        page.keyboard.press("Escape")
        return False


def run(playwright):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    OUTPUT_DIR.mkdir(exist_ok=True)

    navigate_to_club(page)

    for season in SEASONS:
        print(f"\n{'='*60}")
        print(f"SEASON: {season}")
        print(f"{'='*60}")

        if not select_season(page, season):
            print(f"  Skipping season {season}")
            continue

        # Collect team links on the current club page
        team_links_data = []
        for team in TEAMS:
            try:
                # Team entries are <a> links with the team name
                team_el = page.get_by_text(team, exact=True).first
                if team_el.is_visible(timeout=2000):
                    # Get the parent <a> tag's href
                    parent_a = team_el.locator("xpath=ancestor::a[1]")
                    href = parent_a.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            href = "https://play.cricket.com.au" + href
                        team_links_data.append({"team": team, "url": href})
            except Exception:
                pass

        print(f"  Found {len(team_links_data)} teams with links")

        for team_data in team_links_data:
            team = team_data["team"]
            team_url = team_data["url"]
            print(f"\n  --- Team: {team} ---")

            # Navigate directly to the grade page
            page.goto(team_url, wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Collect match data from the grade page
            # Each match card (a.o-play-match-card__link) contains:
            #   - href with match URL
            #   - date in span.o-play-match-card__fixture-date--day
            #   - result in span.o-play-match-card__result-text
            #   - format/venue in div.o-play-match-card__fixture-info
            #   - team names in div.o-play-match-card__team-name
            match_cards_data = []
            try:
                match_card_links = page.locator('a.o-play-match-card__link').all()
                
                for card in match_card_links:
                    try:
                        href = card.get_attribute("href")
                        if not href or "/match/" not in href:
                            continue
                        if not href.startswith("http"):
                            href = "https://play.cricket.com.au" + href

                        # Extract match ID to deduplicate (Stream Replay links share same match ID)
                        match_id_match = re.search(r'/match/([a-f0-9-]+)/', href)
                        match_id = match_id_match.group(1) if match_id_match else href

                        # Get date from within this card
                        date_str = ""
                        date_obj_card = None
                        try:
                            date_el = card.locator("span.o-play-match-card__fixture-date--day").first
                            if date_el.is_visible(timeout=1000):
                                date_str = date_el.inner_text().strip()
                                date_obj_card = parse_date_from_text(date_str)
                        except Exception:
                            pass

                        # Get result
                        result = ""
                        try:
                            result_el = card.locator("span.o-play-match-card__result-text").first
                            if result_el.is_visible(timeout=1000):
                                result = result_el.inner_text().strip()
                        except Exception:
                            pass

                        # Get format/venue info
                        format_info = ""
                        try:
                            info_el = card.locator("div.o-play-match-card__fixture-info").first
                            if info_el.is_visible(timeout=1000):
                                format_info = info_el.inner_text().strip()
                        except Exception:
                            pass

                        # Get team names
                        team_names = []
                        try:
                            name_els = card.locator("div.o-play-match-card__team-name").all()
                            team_names = [n.inner_text().strip() for n in name_els]
                        except Exception:
                            pass

                        match_cards_data.append({
                            "url": href,
                            "match_id": match_id,
                            "date_str": date_str,
                            "date_obj": date_obj_card,
                            "result": result,
                            "format_info": format_info,
                            "team_names": team_names
                        })
                    except Exception:
                        continue

                # Deduplicate by match_id (filters out Stream Replay duplicate links)
                seen_ids = set()
                unique_cards = []
                for mc in match_cards_data:
                    if mc["match_id"] not in seen_ids:
                        seen_ids.add(mc["match_id"])
                        unique_cards.append(mc)
                match_cards_data = unique_cards

            except Exception as e:
                print(f"  Error finding match cards: {e}")

            print(f"  Found {len(match_cards_data)} matches")

            for match_idx, mc in enumerate(match_cards_data):
                match_url = mc["url"]
                date_obj = mc["date_obj"]
                
                # Determine opposition from team names
                opposition = "Unknown"
                title = ""
                if len(mc["team_names"]) >= 2:
                    t1, t2 = mc["team_names"][0], mc["team_names"][1]
                    title = f"{t1} vs {t2}"
                    if "laburnum" in t1.lower():
                        opposition = t2
                    elif "laburnum" in t2.lower():
                        opposition = t1

                # Parse format and venue from format_info (e.g., "2 Day +West Oval")
                match_format = ""
                venue = ""
                fi = mc.get("format_info", "")
                fmt_match = re.match(r'(2 Day\s*\+?|One Day|T20)\s*(.*)', fi, re.IGNORECASE)
                if fmt_match:
                    match_format = fmt_match.group(1).strip()
                    venue = fmt_match.group(2).strip()

                # Build filename
                safe_season = season.replace("/", "-")
                date_str_file = date_obj.strftime("%Y-%m-%d") if date_obj else "unknown-date"
                opposition_clean = safe_filename(opposition).strip()

                out_filename = f"{safe_season} {team} {date_str_file} {opposition_clean}.md"
                out_path = OUTPUT_DIR / out_filename

                preview = f"{opposition} ({date_str_file})"
                print(f"\n    [{match_idx+1}/{len(match_cards_data)}] {preview}")

                if out_path.exists():
                    print(f"    Skipped (exists): {out_filename}")
                    continue

                match_info = {
                    "title": title or opposition,
                    "date": mc.get("date_str", ""),
                    "venue": venue,
                    "result": mc.get("result", ""),
                    "format": match_format
                }

                print(f"    Processing: {out_filename}")

                # Navigate to the match page
                page.goto(match_url, wait_until="networkidle")
                page.wait_for_timeout(3000)

                # ---- Find and iterate innings via radio toggle ----
                innings_list = []

                try:
                    # Innings toggle: fieldset[name="innings"] with radio inputs + labels
                    innings_labels = page.locator('fieldset[name="innings"] label').all()

                    if innings_labels:
                        label_texts = [l.inner_text().strip().replace("\n", " ") for l in innings_labels]
                        print(f"    Found {len(innings_labels)} innings: {label_texts}")

                        for idx, label in enumerate(innings_labels):
                            label_text = label_texts[idx]
                            print(f"      Extracting: {label_text}")

                            # Click the label to switch innings
                            label.click()
                            page.wait_for_timeout(2000)

                            data = scrape_innings_data(page)
                            innings_list.append({"name": label_text, "data": data})
                    else:
                        # No innings toggle - single innings or no data
                        print(f"    No innings toggle, trying direct extraction...")
                        data = scrape_innings_data(page)
                        if data["batting"]["rows"]:
                            innings_list.append({"name": "Innings", "data": data})

                except Exception as e:
                    print(f"    Error processing innings: {e}")

                # Write markdown file
                if innings_list:
                    write_match_markdown(out_path, match_info, innings_list)
                    print(f"    Saved: {out_filename}")
                else:
                    print(f"    No data found, skipping")

            # After all matches for this team, navigate back to club page
            navigate_to_club(page)
            select_season(page, season)

    context.close()
    browser.close()
    print("\n\nDone! All match results scraped.")


if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)

import os
import time
from pathlib import Path
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

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    output_dir = Path("ball_by_ball_data")
    output_dir.mkdir(exist_ok=True)
    
    print("Navigating to stats page...")
    page.goto("https://play.cricket.com.au/stats", wait_until="networkidle")

    # 1. Category -> Ball by Ball
    print("Selecting category...")
    page.locator("#stats-category-dropdown").click()
    page.get_by_role("option", name="Ball by Ball").click()

    # 2. Organisation -> Laburnum Cricket Club
    print("Selecting Organisation...")
    page.locator("#stats-org-search").fill("Laburnum")
    # Wait for results to appear and click the club
    page.get_by_role("option", name="Laburnum Cricket Club").click()

    # Wait for the next dropdowns to load
    page.wait_for_timeout(2000)

    for season in SEASONS:
        print(f"\n==============================")
        print(f"PROCESSING SEASON: {season}")
        print(f"==============================")
        
        # 3. Season
        try:
            page.locator("#stats-season-id-dropdown").click()
            page.get_by_role("option", name=season).click()
        except Exception as e:
            print(f"Failed to select season '{season}'. Skipping.")
            page.keyboard.press("Escape")
            continue
            
        page.wait_for_timeout(2000)

        for team in TEAMS:
            print(f"\n--- Processing Team: {team} ---")
            
            # 4. Team
            try:
                page.locator("#stats-team-id-dropdown").click()
                page.wait_for_timeout(500)
                page.get_by_role("option", name=team).click()
            except Exception as e:
                print(f"Team '{team}' not found in dropdown for season {season}. Skipping.")
                page.keyboard.press("Escape")
                continue
                
            page.wait_for_timeout(2000)

            # 5. Get all matches
            print("Fetching all matches...")
            try:
                page.locator("#stats-grade-id-dropdown").click()
                page.wait_for_timeout(1000)
                
                # Get all options in the dropdown. Skip "Select Match".
                match_options = page.get_by_role("option").all_inner_texts()
                matches = [m.strip() for m in match_options if m.strip() and m.strip() != "Select Match"]
            except Exception as e:
                print(f"No matches dropdown found for {team} in {season}. Skipping.")
                page.keyboard.press("Escape")
                continue
                
            print(f"Found {len(matches)} matches to process for {team}.")
            
            # Close the dropdown so we can open it freshly in the loop
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            
            for match_name in matches:
                print(f"  -> Match: {match_name}")
                page.locator("#stats-grade-id-dropdown").click()
                page.wait_for_timeout(500)
                
                # Using exact match in case some match names are prefixes of others
                try:
                    page.get_by_role("option", name=match_name, exact=True).click()
                except Exception as e:
                    print(f"     Failed to click match option. Skipping.")
                    page.keyboard.press("Escape")
                    continue

                # 6. Generate Report
                # print("     Generating Report...")
                page.get_by_role("button", name="Generate report").click()

                # Wait for report to generate
                page.wait_for_timeout(4000)
                
                # Check if there are no rows
                if page.locator("text='No rows'").is_visible():
                    print(f"     Skipped: No rows data.")
                    continue

                # 7. Download CSV
                # print("     Downloading CSV...")
                try:
                    page.get_by_role("button", name="Export").click(timeout=3000)
                    with page.expect_download(timeout=5000) as download_info:
                        page.get_by_role("menuitem", name="Comma-Separated Values (CSV)").click()
                    
                    download = download_info.value
                    
                    # 8. Save CSV
                    safe_match_name = match_name.replace("/", "-").replace(":", "")
                    file_path = output_dir / f"{safe_match_name}.csv"
                    
                    # Prevent redownloading if file already exists (optional but good for large scrapes)
                    if not file_path.exists():
                        download.save_as(file_path)
                        print(f"     Saved: {file_path}")
                    else:
                        print(f"     Skipped: File already exists.")
                        
                except Exception as e:
                    print(f"     Failed to download {match_name}: {e}")

    # Close browser
    context.close()
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)

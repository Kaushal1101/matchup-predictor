import requests
from bs4 import BeautifulSoup
import time

def scrape_cricket_player(player_name):
    # Initialize tracking metrics
    start_time = time.time()
    pages_visited = 0
    
    # Format name for Wikipedia URL (e.g., "Virat Kohli" -> "Virat_Kohli")
    formatted_name = player_name.replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{formatted_name}"
    
    headers = {
        'User-Agent': 'CricketScraperBot/1.0 (contact: your@email.com)'
    }

    result = {
        "Batting": "Not found",
        "Bowling": "Not found",
        "Pages Visited": 0,
        "Time Taken": 0
    }

    try:
        response = requests.get(url, headers=headers)
        pages_visited += 1
        
        if response.status_code != 200:
            return f"Error: Could not find page for '{player_name}'. (Status: {response.status_code})"

        soup = BeautifulSoup(response.text, 'html.parser')
        infobox = soup.find("table", {"class": "infobox"})

        if not infobox:
            return "Error: Could not find infobox on the page."

        # Search for Batting and Bowling rows
        for row in infobox.find_all("tr"):
            header = row.find("th")
            value = row.find("td")
            
            if header and value:
                header_text = header.get_text(strip=True).lower()
                # Check for batting style
                if "batting" in header_text:
                    result["Batting"] = value.get_text(strip=True)
                # Check for bowling style
                if "bowling" in header_text:
                    result["Bowling"] = value.get_text(strip=True)

    except Exception as e:
        return f"An error occurred: {e}"

    # Finalize metrics
    result["Time Taken"] = round(time.time() - start_time, 4)
    result["Pages Visited"] = pages_visited
    
    return result

# --- Execution ---
name = input("Enter Cricket Player Name: ")
data = scrape_cricket_player(name)

if isinstance(data, dict):
    print(f"\nResults for {name}:")
    print(f"  - Batting Style: {data['Batting']}")
    print(f"  - Bowling Style: {data['Bowling']}")
    print("-" * 30)
    print(f"  - Pages Visited: {data['Pages Visited']}")
    print(f"  - Time Taken:    {data['Time Taken']} seconds")
else:
    print(data)
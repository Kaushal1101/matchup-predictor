import json
import os
import pandas as pd
from datetime import datetime


def get_phase(over):
    if over < 6:
        return "powerplay"
    elif over < 15:
        return "middle"
    else:
        return "death"


# 🌍 GLOBAL CAREER STATS (persist across matches)
global_batter_stats = {}
global_bowler_stats = {}


def extract_match_date(match_json, filename="<unknown>"):
    info = match_json.get("info")
    if not isinstance(info, dict):
        raise ValueError(f"{filename}: missing or invalid 'info' field")

    dates = info.get("dates")
    if not isinstance(dates, list) or len(dates) == 0:
        raise ValueError(f"{filename}: missing or empty 'info.dates'")

    parsed_dates = []
    for i, date_str in enumerate(dates):
        if not isinstance(date_str, str):
            raise ValueError(f"{filename}: info.dates[{i}] is not a string: {date_str}")

        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(
                f"{filename}: invalid date format in info.dates[{i}] = '{date_str}', "
                "expected YYYY-MM-DD"
            ) from e

        parsed_dates.append(parsed_date)

    # Use the earliest listed date to guarantee chronological ordering
    return min(parsed_dates)


def parse_match(match_json, match_date):
    rows = []

    info = match_json["info"]
    teams = info["teams"]
    innings_list = match_json["innings"]

    for innings_idx, innings in enumerate(innings_list):
        batting_team = innings["team"]
        bowling_team = [t for t in teams if t != batting_team][0]

        target = innings.get("target", {}).get("runs", 0)
        is_chasing = 1 if innings_idx == 1 else 0

        # MATCH-LEVEL stats
        batter_stats = {}
        bowler_stats = {}

        team_runs = 0
        team_wickets = 0
        balls_bowled = 0

        for over_data in innings["overs"]:
            over_num = over_data["over"]

            for ball_idx, delivery in enumerate(over_data["deliveries"], start=1):
                batter = delivery["batter"]
                bowler = delivery["bowler"]
                non_striker = delivery["non_striker"]

                if batter not in batter_stats:
                    batter_stats[batter] = {"runs": 0, "balls": 0}

                if non_striker not in batter_stats:
                    batter_stats[non_striker] = {"runs": 0, "balls": 0}

                if bowler not in bowler_stats:
                    bowler_stats[bowler] = {"runs": 0, "balls": 0, "wickets": 0}

                if batter not in global_batter_stats:
                    global_batter_stats[batter] = {"runs": 0, "balls": 0}

                if non_striker not in global_batter_stats:
                    global_batter_stats[non_striker] = {"runs": 0, "balls": 0}

                if bowler not in global_bowler_stats:
                    global_bowler_stats[bowler] = {"runs": 0, "balls": 0, "wickets": 0}

                batter_sr = (
                    batter_stats[batter]["runs"] / max(1, batter_stats[batter]["balls"]) * 100
                )

                nonstriker_sr = (
                    batter_stats[non_striker]["runs"] / max(1, batter_stats[non_striker]["balls"]) * 100
                )

                bowler_economy = (
                    bowler_stats[bowler]["runs"] / max(1, bowler_stats[bowler]["balls"]) * 6
                )

                career_sr = (
                    global_batter_stats[batter]["runs"] /
                    max(1, global_batter_stats[batter]["balls"]) * 100
                )

                career_bowler_economy = (
                    global_bowler_stats[bowler]["runs"] /
                    max(1, global_bowler_stats[bowler]["balls"]) * 6
                )

                overs_float = balls_bowled / 6 if balls_bowled > 0 else 0
                net_run_rate = team_runs / overs_float if overs_float > 0 else 0

                balls_remaining = max(0, 120 - balls_bowled)
                runs_remaining = max(0, target - team_runs) if is_chasing else 0

                required_run_rate = (
                    runs_remaining / (balls_remaining / 6)
                    if is_chasing and balls_remaining > 0
                    else 0
                )

                row = {
                    "match_date": match_date.strftime("%d/%m/%Y"),
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "over": over_num,
                    "ball": ball_idx,
                    "phase": get_phase(over_num),

                    "batter": batter,
                    "bowler": bowler,
                    "nonstriker": non_striker,

                    "batter_runs": batter_stats[batter]["runs"],
                    "batter_balls": batter_stats[batter]["balls"],
                    "batter_strike_rate": batter_sr,

                    "nonstriker_strike_rate": nonstriker_sr,

                    "bowler_runs_conceded": bowler_stats[bowler]["runs"],
                    "bowler_wickets": bowler_stats[bowler]["wickets"],
                    "bowler_economy": bowler_economy,

                    "career_strike_rate": career_sr,
                    "career_bowler_economy": career_bowler_economy,

                    "team_runs": team_runs,
                    "team_wickets": team_wickets,
                    "net_run_rate": net_run_rate,
                    "required_run_rate": required_run_rate,
                    "is_chasing": is_chasing,
                    "target": target,
                    "runs_remaining": runs_remaining,
                    "balls_remaining": balls_remaining,

                    "runs_scored": delivery["runs"]["total"],
                    "wicket": 1 if "wickets" in delivery else 0,
                }

                rows.append(row)

                runs = delivery["runs"]["batter"]
                total_runs = delivery["runs"]["total"]

                team_runs += total_runs
                balls_bowled += 1

                if "wickets" in delivery:
                    team_wickets += 1
                    bowler_stats[bowler]["wickets"] += 1
                    global_bowler_stats[bowler]["wickets"] += 1

                batter_stats[batter]["runs"] += runs
                batter_stats[batter]["balls"] += 1

                bowler_stats[bowler]["runs"] += total_runs
                bowler_stats[bowler]["balls"] += 1

                global_batter_stats[batter]["runs"] += runs
                global_batter_stats[batter]["balls"] += 1

                global_bowler_stats[bowler]["runs"] += total_runs
                global_bowler_stats[bowler]["balls"] += 1


    return rows


folder_path = "../data/raw/t20s_json"

matches = []

for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        path = os.path.join(folder_path, filename)
        with open(path, "r") as f:
            match_json = json.load(f)

        match_date = extract_match_date(match_json, filename)
        matches.append((match_date, match_json, filename))

# Sort by actual parsed earliest match date, then filename for deterministic tie-break
matches.sort(key=lambda x: (x[0], x[2]))

all_rows = []

for match_date, match_json, filename in matches:
    rows = parse_match(match_json, match_date)
    all_rows.extend(rows)
    print(f"Processed {filename} ({match_date.strftime('%d/%m/%Y')}) → {len(rows)} rows")

os.makedirs("../data/processed", exist_ok=True)

with open("../data/processed/all_matches_dataset.json", "w") as f:
    json.dump(all_rows, f, indent=2)

df = pd.DataFrame(all_rows)
df.to_csv("../data/processed/all_matches_dataset.csv", index=False)

print(f"\nTotal rows: {len(all_rows)}")
print("Saved CSV successfully")
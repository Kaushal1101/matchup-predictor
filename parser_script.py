import json


def get_phase(over):
    if over < 6:
        return "powerplay"
    elif over < 15:
        return "middle"
    else:
        return "death"


def parse_match(match_json):
    rows = []

    info = match_json["info"]
    teams = info["teams"]
    innings_list = match_json["innings"]

    for innings_idx, innings in enumerate(innings_list):
        batting_team = innings["team"]
        bowling_team = [t for t in teams if t != batting_team][0]

        target = innings.get("target", {}).get("runs", 0)
        is_chasing = 1 if innings_idx == 1 else 0

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
                    bowler_stats[bowler] = {"runs": 0, "wickets": 0}

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
                    "bowler_runs_conceded": bowler_stats[bowler]["runs"],
                    "bowler_wickets": bowler_stats[bowler]["wickets"],
                    "nonstriker_runs": batter_stats[non_striker]["runs"],
                    "nonstriker_balls": batter_stats[non_striker]["balls"],
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

                # update state after ball
                team_runs += delivery["runs"]["total"]
                balls_bowled += 1

                if "wickets" in delivery:
                    team_wickets += 1
                    bowler_stats[bowler]["wickets"] += 1

                batter_stats[batter]["runs"] += delivery["runs"]["batter"]
                batter_stats[batter]["balls"] += 1
                bowler_stats[bowler]["runs"] += delivery["runs"]["total"]

    return rows


with open("test_data.json", "r") as f:
    match_json = json.load(f)

rows = parse_match(match_json)

print(f"Parsed {len(rows)} ball events")
print(rows[0])

with open("parsed_test_data.json", "w") as f:
    json.dump(rows, f, indent=2)
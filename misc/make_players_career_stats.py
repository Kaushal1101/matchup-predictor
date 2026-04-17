#!/usr/bin/env python3

from __future__ import annotations

import pandas as pd
from pathlib import Path

# =========================
# File paths
# =========================
PLAYERS_PATH = Path("data/processed/players.csv")
MATCHES_PATH = Path("data/processed/all_matches_dataset.csv")
OUTPUT_PATH = Path("data/processed/player_career_stats.csv")

# =========================
# players.csv columns
# =========================
PLAYER_ID_COL = "identifier"
PLAYER_NAME_COL = "unique_name"
ALT_NAME_COLS = ["unique_name", "name_x", "name_y"]

# =========================
# all_matches_dataset.csv columns
# =========================
DATE_COL = "match_date"
BATTING_TEAM_COL = "batting_team"
BOWLING_TEAM_COL = "bowling_team"
BATTER_COL = "batter"
NONSTRIKER_COL = "nonstriker"
BOWLER_COL = "bowler"

BATTER_RUNS_COL = "batter_runs"                 # cumulative in innings
BATTER_BALLS_COL = "batter_balls"               # cumulative in innings
BOWLER_RUNS_COL = "bowler_runs_conceded"        # cumulative in innings
BOWLER_WICKETS_COL = "bowler_wickets"           # cumulative in innings
BOWLER_ECON_COL = "bowler_economy"              # cumulative/final economy
RUNS_SCORED_COL = "runs_scored"
WICKET_COL = "wicket"


def safe_div(n: float, d: float) -> float:
    if d == 0:
        return 0.0
    return n / d


def build_name_to_id_map(players_df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}

    for _, row in players_df.iterrows():
        pid = row[PLAYER_ID_COL]
        for col in ALT_NAME_COLS:
            if col in players_df.columns:
                val = row.get(col)
                if pd.notna(val):
                    name = str(val).strip()
                    if name:
                        mapping[name] = pid

    return mapping


def make_match_key(df: pd.DataFrame) -> pd.Series:
    team_a = df[[BATTING_TEAM_COL, BOWLING_TEAM_COL]].min(axis=1)
    team_b = df[[BATTING_TEAM_COL, BOWLING_TEAM_COL]].max(axis=1)
    return (
        df[DATE_COL].astype(str).str.strip()
        + "||"
        + team_a.astype(str).str.strip()
        + "||"
        + team_b.astype(str).str.strip()
    )


def make_innings_key(df: pd.DataFrame) -> pd.Series:
    return df["match_key"] + "||" + df[BATTING_TEAM_COL].astype(str).str.strip()


def main() -> None:
    print("Loading files...")
    players_df = pd.read_csv(PLAYERS_PATH)
    df = pd.read_csv(MATCHES_PATH)

    # Standardize string columns
    for col in [
        DATE_COL,
        BATTING_TEAM_COL,
        BOWLING_TEAM_COL,
        BATTER_COL,
        NONSTRIKER_COL,
        BOWLER_COL,
    ]:
        df[col] = df[col].astype(str).str.strip()

    # Build keys
    df["match_key"] = make_match_key(df)
    df["innings_key"] = make_innings_key(df)

    # Map names to player ids
    print("Mapping player names to identifiers...")
    name_to_id = build_name_to_id_map(players_df)
    df["batter_id"] = df[BATTER_COL].map(name_to_id)
    df["nonstriker_id"] = df[NONSTRIKER_COL].map(name_to_id)
    df["bowler_id"] = df[BOWLER_COL].map(name_to_id)

    # ==========================================================
    # Batting innings table
    # One row per player per innings using MAX cumulative values
    # ==========================================================
    print("Building batting innings stats...")
    batting_innings = (
        df.dropna(subset=["batter_id"])
          .groupby(["innings_key", "match_key", BATTING_TEAM_COL, "batter_id"], as_index=False)
          .agg(
              innings_runs=(BATTER_RUNS_COL, "max"),
              innings_balls=(BATTER_BALLS_COL, "max"),
          )
          .rename(columns={"batter_id": PLAYER_ID_COL})
    )

    batting_career = (
        batting_innings.groupby(PLAYER_ID_COL, as_index=False)
        .agg(
            innings_batted=("innings_key", "nunique"),
            runs_scored=("innings_runs", "sum"),
            balls_faced=("innings_balls", "sum"),
            highest_score=("innings_runs", "max"),
        )
    )

    # Proxy batting average: runs / innings_batted
    batting_career["batting_career_average"] = batting_career.apply(
        lambda row: safe_div(row["runs_scored"], row["innings_batted"]),
        axis=1,
    )
    batting_career["batting_career_sr"] = batting_career.apply(
        lambda row: safe_div(row["runs_scored"] * 100, row["balls_faced"]),
        axis=1,
    )

    milestones = (
        batting_innings.groupby(PLAYER_ID_COL, as_index=False)
        .agg(
            thirties=("innings_runs", lambda s: ((s >= 30) & (s < 50)).sum()),
            fifties=("innings_runs", lambda s: ((s >= 50) & (s < 100)).sum()),
            hundreds=("innings_runs", lambda s: (s >= 100).sum()),
        )
    )

    # ==========================================================
    # Bowling innings table
    # One row per bowler per innings using MAX cumulative values
    # ==========================================================
    print("Building bowling innings stats...")
    bowling_innings = (
        df.dropna(subset=["bowler_id"])
          .groupby(["innings_key", "match_key", BOWLING_TEAM_COL, "bowler_id"], as_index=False)
          .agg(
              innings_runs_conceded=(BOWLER_RUNS_COL, "max"),
              innings_wickets=(BOWLER_WICKETS_COL, "max"),
              final_economy=(BOWLER_ECON_COL, "last"),
          )
          .rename(columns={"bowler_id": PLAYER_ID_COL})
    )

    def estimate_balls(row) -> float:
        econ = row["final_economy"]
        runs = row["innings_runs_conceded"]
        if pd.isna(econ) or econ <= 0:
            return 0.0
        overs = runs / econ
        return overs * 6.0

    bowling_innings["estimated_balls_bowled"] = bowling_innings.apply(estimate_balls, axis=1)

    bowling_career = (
        bowling_innings.groupby(PLAYER_ID_COL, as_index=False)
        .agg(
            innings_bowled=("innings_key", "nunique"),
            runs_conceded=("innings_runs_conceded", "sum"),
            wickets_taken=("innings_wickets", "sum"),
            estimated_balls_bowled=("estimated_balls_bowled", "sum"),
            highest_wickets_in_innings=("innings_wickets", "max"),
        )
    )

    bowling_career["bowling_career_average"] = bowling_career.apply(
        lambda row: safe_div(row["runs_conceded"], row["wickets_taken"]),
        axis=1,
    )
    bowling_career["bowling_career_sr"] = bowling_career.apply(
        lambda row: safe_div(row["estimated_balls_bowled"], row["wickets_taken"]),
        axis=1,
    )

    bowling_career["bowling_career_economy"] = bowling_career.apply(
        lambda row: safe_div(row["runs_conceded"] * 6, row["estimated_balls_bowled"]),
        axis=1,
    )

    # ==========================================================
    # Matches played
    # ==========================================================
    print("Computing matches played...")
    batter_matches = (
        df.dropna(subset=["batter_id"])[["match_key", "batter_id"]]
          .drop_duplicates()
          .rename(columns={"batter_id": PLAYER_ID_COL})
    )
    nonstriker_matches = (
        df.dropna(subset=["nonstriker_id"])[["match_key", "nonstriker_id"]]
          .drop_duplicates()
          .rename(columns={"nonstriker_id": PLAYER_ID_COL})
    )
    bowler_matches = (
        df.dropna(subset=["bowler_id"])[["match_key", "bowler_id"]]
          .drop_duplicates()
          .rename(columns={"bowler_id": PLAYER_ID_COL})
    )

    all_matches = pd.concat(
        [batter_matches, nonstriker_matches, bowler_matches],
        ignore_index=True,
    ).drop_duplicates()

    matches_played = (
        all_matches.groupby(PLAYER_ID_COL, as_index=False)
        .agg(matches_played=("match_key", "nunique"))
    )

    # ==========================================================
    # Final merge
    # ==========================================================
    print("Merging final career stats table...")
    final_df = players_df[[PLAYER_ID_COL, PLAYER_NAME_COL]].copy()

    final_df = final_df.merge(
        batting_career[
            [
                PLAYER_ID_COL,
                "innings_batted",
                "batting_career_average",
                "batting_career_sr",
                "runs_scored",
                "balls_faced",
                "highest_score",
            ]
        ],
        on=PLAYER_ID_COL,
        how="left",
    )

    final_df = final_df.merge(
        bowling_career[
            [
                PLAYER_ID_COL,
                "innings_bowled",
                "runs_conceded",
                "wickets_taken",
                "estimated_balls_bowled",
                "highest_wickets_in_innings",
                "bowling_career_average",
                "bowling_career_sr",
                "bowling_career_economy",
            ]
        ],
        on=PLAYER_ID_COL,
        how="left",
    )

    final_df = final_df.merge(matches_played, on=PLAYER_ID_COL, how="left")
    final_df = final_df.merge(milestones, on=PLAYER_ID_COL, how="left")

    # Fill missing numeric values
    numeric_cols = [
        "innings_batted",
        "innings_bowled",
        "batting_career_average",
        "batting_career_sr",
        "bowling_career_average",
        "bowling_career_sr",
        "bowling_career_economy",
        "matches_played",
        "runs_scored",
        "balls_faced",
        "runs_conceded",
        "wickets_taken",
        "estimated_balls_bowled",
        "highest_score",
        "highest_wickets_in_innings",
        "thirties",
        "fifties",
        "hundreds",
    ]
    for col in numeric_cols:
        final_df[col] = final_df[col].fillna(0)

    # Round rate/average columns
    for col in [
        "batting_career_average",
        "batting_career_sr",
        "bowling_career_average",
        "bowling_career_sr",
        "bowling_career_economy",
        "estimated_balls_bowled",
    ]:
        final_df[col] = final_df[col].round(2)

    final_df = final_df.rename(
        columns={
            "thirties": "30s",
            "fifties": "50s",
            "hundreds": "100s",
        }
    )

    final_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved: {OUTPUT_PATH}")
    print(final_df.head())
    print()
    print("Note: batting_career_average is a proxy (runs / innings_batted),")
    print("because this dataset does not contain dismissal/not-out attribution.")


if __name__ == "__main__":
    main()
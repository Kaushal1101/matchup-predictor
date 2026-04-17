import pandas as pd

df = pd.read_csv("data/processed/player_career_stats.csv")

print("\nTop 10 batters by runs scored:")
print(
    df[["unique_name", "runs_scored"]]
    .sort_values("runs_scored", ascending=False)
    .head(10)
    .to_string(index=False)
)

# Change this if your wickets column has a different name
wickets_col = "wickets_taken"

print("\nTop 10 bowlers by wickets:")
print(
    df[["unique_name", wickets_col]]
    .sort_values(wickets_col, ascending=False)
    .head(10)
    .to_string(index=False)
)
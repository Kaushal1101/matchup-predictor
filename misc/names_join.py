import pandas as pd

# --- file names ---
players_file = "data/raw/people.csv"
alt_names_file = "data/raw/names.csv"
output_file = "data/processed/players_with_alt_names.csv"

# --- column names ---
# Change these if your CSV headers are different
id_col = "identifier"
name_col = "name"
unique_name_col = "unique_name"
alt_name_col = "name"

# Read both CSVs
players_df = pd.read_csv(players_file)
alt_names_df = pd.read_csv(alt_names_file)

# Keep only needed columns from alternate names file
alt_names_df = alt_names_df[[id_col, alt_name_col]]

# Left join so every player in players.csv is kept
merged_df = players_df.merge(alt_names_df, on=id_col, how="left")

# Save result
merged_df.to_csv(output_file, index=False)

print(f"Done. Saved merged file to {output_file}")
print(merged_df.head())
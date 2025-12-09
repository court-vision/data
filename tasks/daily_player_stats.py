from datetime import timedelta
from datetime import datetime
import json
import requests
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv3
import pandas as pd
from db.models.season2.daily_player_stats import DailyPlayerStats

def get_game_ids(date: str) -> list[str]:
	scoreboard = scoreboardv2.ScoreboardV2(game_date=date)
	games = scoreboard.get_dict()['resultSets'][0]['rowSet']
	game_ids = [game[2] for game in games]
	return game_ids

def get_espn_rostered_data(year: int, league_id: int) -> dict:
	params = {
			'view': 'kona_player_info',
			'scoringPeriodId': 0,
	}
	endpoint = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{}/segments/0/leagues/{}'.format(year, league_id)
	filters = {"players":{"filterSlotIds":{"value":[]},"limit": 750, "sortPercOwned":{"sortPriority":1,"sortAsc":False},"sortDraftRanks":{"sortPriority":2,"sortAsc":True,"value":"STANDARD"}}}
	headers = {'x-fantasy-filter': json.dumps(filters)}

	data = requests.get(endpoint, params=params, headers=headers).json()
	data = data['players']
	data = [x.get('player', x) for x in data]

	cleaned_data = {player['fullName']: player['ownership']['percentOwned'] for player in data if player}

	return cleaned_data

# Helper function to convert minutes from MM:SS format to integer minutes
def minutes_to_int(min_str: str) -> int:
	if isinstance(min_str, (int, float)):
		return int(min_str)
	if ':' in str(min_str):
		parts = str(min_str).split(':')
		return int(parts[0])
	return int(min_str)

year = 2026
league_id = 993431466

rostered_data = get_espn_rostered_data(year, league_id)

def get_rostered_pct(player_name):
	# Try exact match first
	if player_name in rostered_data:
		return float(rostered_data[player_name])
	# Try case-insensitive match
	for espn_name, pct in rostered_data.items():
		if player_name.lower() == espn_name.lower():
			return float(pct)
	return None

def calculate_fantasy_points(stats: pd.DataFrame) -> float:
	points_score = stats['points']
	rebounds_score = stats['reboundsTotal']
	assists_score = stats['assists'] * 2
	stocks_score = (stats['steals'] + stats['blocks']) * 4
	turnovers_score = stats['turnovers'] * -2
	three_pointers_score = stats['threePointersMade']
	fg_eff_score = (stats['fieldGoalsMade'] * 2) - stats['fieldGoalsAttempted']
	ft_eff_score = stats['freeThrowsMade'] - stats['freeThrowsAttempted']

	return points_score + rebounds_score + assists_score + stocks_score + turnovers_score + three_pointers_score + fg_eff_score + ft_eff_score


def main():
	yesterday = datetime.now() - timedelta(days=1)
	game_ids = get_game_ids(yesterday)

	for game_id in game_ids:
			boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
			stats = boxscore.get_data_frames()[0]
			stats = stats.dropna()
			stats.loc[:, "fantasyScore"] = stats.apply(calculate_fantasy_points, axis=1)
			game_date = yesterday.date()

			for _, row in stats.iterrows():
				# Skip players who didn't play (indicated by blank/null/empty minutes)
				minutes_value = row['minutes']
				
				# Check for null, NaN, empty string, or None
				if pd.isna(minutes_value) or minutes_value == '' or minutes_value is None:
					continue
				
				# Convert to integer and skip if it's 0 (player didn't play)
				minutes_int = minutes_to_int(minutes_value)
				if minutes_int == 0:
					continue
				
				player_name = row['firstName'] + " " + row['familyName']
				rost_pct = get_rostered_pct(player_name)
				
				DailyPlayerStats.create(
					id=int(row['personId']),
					name=player_name,
					team=row['teamTricode'],
					date=game_date,
					fpts=int(round(row['fantasyScore'])),
					pts=int(row['points']),
					reb=int(row['reboundsTotal']),
					ast=int(row['assists']),
					stl=int(row['steals']),
					blk=int(row['blocks']),
					tov=int(row['turnovers']),
					fgm=int(row['fieldGoalsMade']),
					fga=int(row['fieldGoalsAttempted']),
					fg3m=int(row['threePointersMade']),
					fg3a=int(row['threePointersAttempted']),
					ftm=int(row['freeThrowsMade']),
					fta=int(row['freeThrowsAttempted']),
					min=minutes_int,
					rost_pct=rost_pct
				)

if __name__ == "__main__":
	main()
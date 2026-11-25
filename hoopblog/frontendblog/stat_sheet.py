import csv
import io
import re


COLUMNS = {
    'player': ('player_name', 'player', 'name'),
    'team': ('team',),
    'points': ('points', 'pts'),
    'assists': ('assists', 'ast', 'as'),
    'turnovers': ('turnovers', 'tov', 'to'),
    'two_made': ('two point made', '2pm'),
    'two_attempted': ('two point attempted', '2pa'),
    'three_made': ('three point made', '3pm'),
    'three_attempted': ('three point attempted', '3pa'),
}
COUNTING_STATS = ('points', 'assists', 'turnovers')


def count(value, line, column):
    if value.casefold() in ('', '-', '—', 'n/a', 'na'):
        return None
    if not re.fullmatch(r'[0-9]{1,5}(?:\.0+)?', value):
        raise ValueError(f'Row {line} has an invalid value for {column}. Use a whole number or leave it blank.')
    return int(value.split('.', 1)[0])


def read_csv(upload):
    try:
        return upload.read().decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('Save the stat sheet as a UTF-8 CSV and upload it again.') from error


def analyze_rows(raw, *, allow_team_rows=False):
    reader = csv.DictReader(io.StringIO(raw, newline=''), strict=True)
    try:
        headers = reader.fieldnames or []
        normalized = {header.strip().casefold(): header for header in headers}
        if len(normalized) != len(headers):
            raise ValueError('Use a different column name for each statistic.')
        columns = {
            key: next(normalized[alias] for alias in aliases if alias in normalized)
            for key, aliases in COLUMNS.items() if any(alias in normalized for alias in aliases)
        }
        row_name = columns.get('player')
        if not row_name and allow_team_rows:
            row_name = columns.get('team')
        if not row_name:
            raise ValueError('Include a Player or Team column.' if allow_team_rows else 'Include a Player or player_name column.')
        if not set(columns) - {'player', 'team'}:
            raise ValueError('Include points, assists, turnovers, or a pair of shooting columns.')
        players = []
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f'Row {reader.line_num} does not have the same number of cells as the header.')
            player = row[row_name].strip()
            if not player or player.casefold() in ('total', 'totals', 'team total', 'team totals'):
                continue
            stats = {
                key: count(row[header].strip(), reader.line_num, header)
                for key, header in columns.items() if key not in ('player', 'team')
            }
            result = {
                'player': player,
                'team': row.get(columns.get('team'), '').strip() if 'player' in columns else '',
                **{key: stats.get(key) for key in COUNTING_STATS},
                'effective_fg': None,
            }
            shot_keys = ('two_made', 'two_attempted', 'three_made', 'three_attempted')
            if all(stats.get(key) is not None for key in shot_keys):
                twos, two_attempts, threes, three_attempts = (stats[key] for key in shot_keys)
                if twos > two_attempts or threes > three_attempts:
                    raise ValueError(f'Row {reader.line_num} has more made shots than attempts.')
                attempts = two_attempts + three_attempts
                if attempts:
                    result['effective_fg'] = 100 * (twos + 1.5 * threes) / attempts
            if any(result[key] is not None for key in (*COUNTING_STATS, 'effective_fg')):
                players.append(result)
    except csv.Error as error:
        raise ValueError('The CSV could not be read. Check its formatting and upload it again.') from error
    if not players:
        raise ValueError('Include at least one player with a recorded stat or complete shooting line.')
    return players

def stat_highlights(players):
    highlights = []
    for key, label in (('points', 'Points'), ('assists', 'Assists')):
        recorded = [line for line in players if line[key] is not None]
        if recorded:
            highest = max(line[key] for line in recorded)
            leaders = [
                f"{line['player']} ({line['team']})" if line['team'] else line['player']
                for line in recorded if line[key] == highest
            ]
            highlights.append({'label': label, 'value': highest, 'leaders': leaders})
    return highlights

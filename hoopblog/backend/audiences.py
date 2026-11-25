import re


def audience_slugs(data):
    classification = data.get('classification')
    if not isinstance(classification, dict):
        classification = {}
    matching = set()
    for source in (data, classification):
        for key in ('audience', 'audiences', 'primary_audience', 'secondary_audience', 'secondary_audiences'):
            values = source.get(key)
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str):
                        matching.update(re.findall(r'\b(player|coach|parent)(?:s|es)?\b', value.lower()))
    return matching

import json
import os

def load_accounts(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('accounts', [])
    except:
        return []

def get_enabled_accounts(accounts):
    return [acc for acc in accounts if acc.get('enabled', True)]

def find_accounts_by_query(accounts, query_text):
    query_lower = query_text.lower()
    results = []
    for acc in accounts:
        if query_lower in acc.get('name', '').lower():
            results.append(acc)
            continue
        aliases = acc.get('aliases', [])
        if any(query_lower in alias.lower() for alias in aliases):
            results.append(acc)
            continue
        tags = acc.get('tags', [])
        if any(query_lower in tag.lower() for tag in tags):
            results.append(acc)
    return results

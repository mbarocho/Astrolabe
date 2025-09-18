import json
from event import Event

def save_to_json(catalog):
    catalog_json = [event.__dict__ for event in catalog]
    with open("event_catalog.json", "w") as file:
        json.dump(catalog_json, file, indent=4)

def load_from_json(catalog):
    with open("event_catalog.json", "r") as file:
        data = json.load(file)
        for event in data:
            catalog.append(Event(**event))
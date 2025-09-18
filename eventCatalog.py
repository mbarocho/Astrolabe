import json
from event import *
from convert import *

global catalog
catalog = []

def add_to_catalog():
    item = ""
    title = input("Title: ")
    date = input("Date: ")
    location = input("Location: ")
    description = input("Description: ")
    item = Content(title, date, location, description)
    catalog.append(item)
    save_to_json(catalog)

def remove_from_catalog():
    query = input("Enter the title of the event you want to remove: ")
    for event in catalog:
        if event.title == query:
            catalog.remove(event)
            save_to_json(catalog)
            print(f"{event.title} has been removed from the catalog.")
            return

def search_catalog():
    search_by_name(catalog)


def show_catalog():
    if catalog == []:
        print("Catalog is empty. Please add content to be displayed.")
    else:
        for event in catalog:
            print(f"{event.title} ({event.date})")
            print(f"Location: {event.location}")
            print(f"Description: {event.description}")
            print("")

def open_catalog():
    load_from_json(catalog)
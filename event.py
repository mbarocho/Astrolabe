class Event:
    def __init__(self, title, date, location, description):
        self.title = title
        self.date = date
        self.location = location
        self.description = description


    def __repr__(self):
        return f"{self.title}\n{self.description}\n{self.location}\n"
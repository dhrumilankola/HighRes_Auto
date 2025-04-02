import json

def load_resume_data(path: str = "./resume_data/resume_data.json") -> dict:
    with open(path, "r") as file:
        return json.load(file)
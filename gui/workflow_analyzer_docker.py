import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
DB_URL = "http://localhost:8003"

def get_recent_observations(limit=3):
    res = requests.get(f"{DB_URL}/get_observations?limit={limit}")
    return res.json() if res.status_code == 200 else []

def analyze_patterns(observations):
    obs_text = "\n".join([json.dumps(obs["json_data"]) for obs in observations])
    prompt = f"""From these observations, detect repetitive workflows.

Observations:
{obs_text}

JSON output format:
{{
  "patterns": [
    {{
      "name": "Edit Docker",
      "steps": [
        {{"type": "click", "element": "docker-compose.yml"}},
        {{"type": "type", "value": "env update"}}
      ]
    }}
  ]
}}"""

    payload = {
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=60)
    if res.status_code == 200:
        return json.loads(res.json()["response"])
    return {"patterns": []}

def store_workflow(pattern):
    res = requests.post(f"{DB_URL}/store_workflow", json=pattern)
    return res.json() if res.status_code == 201 else None

if __name__ == "__main__":
    obs = get_recent_observations()
    patterns = analyze_patterns(obs)
    for p in patterns["patterns"]:
        store_workflow(p)
    print("Patterns stored!")
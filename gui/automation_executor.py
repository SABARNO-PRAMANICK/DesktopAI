import pyautogui
import time
import json

def execute_workflow(steps):
    for step in steps:
        if step["step"] == "click":
            x, y = step.get("position", (100, 100))
            pyautogui.click(x, y)
        elif step["step"] == "type":
            pyautogui.typewrite(step["value"])
        time.sleep(0.5)
    return "Workflow executed"

if __name__ == "__main__":
    with open("temp_workflow.json", "r") as f:
        wf = json.load(f)
    print(execute_workflow(wf["steps_json"]))
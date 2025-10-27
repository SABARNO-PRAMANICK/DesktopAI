import customtkinter as ctk
import requests
from tkinter import messagebox, filedialog
from datetime import datetime
import json
from threading import Thread
import time
import mss
import pyautogui
import sounddevice as sd
import soundfile as sf
import numpy as np
import base64
from io import BytesIO
from PIL import Image
import io
from logging import Logger

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AGIAssistant(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AGI Assistant")
        self.geometry("1200x800")
        self.resizable(True, True)

        # API Endpoints
        self.OCR_URL = "http://localhost:8001/process_image"
        self.STT_URL = "http://localhost:8002/transcribe"
        self.DB_URL = "http://localhost:8003"
        self.OLLAMA_URL = "http://localhost:11434/api/generate"

        # State
        self.is_recording_screen = False
        self.is_recording_audio = False
        self.is_real_time = False
        self.observations = []
        self.workflows = []
        self.selected_workflow = None  # FIXED: Initialized
        self.real_time_events = []  # For continuous logging

        # UI
        self.setup_ui()

    def setup_ui(self):
        # Tab View
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Tabs
        self.observe_tab = self.tabview.add("Observe")
        self.understand_tab = self.tabview.add("Understand")
        self.automate_tab = self.tabview.add("Automate")
        self.data_tab = self.tabview.add("Data")

        self.setup_observe_tab()
        self.setup_understand_tab()
        self.setup_automate_tab()
        self.setup_data_tab()

    def setup_observe_tab(self):
        ctk.CTkLabel(self.observe_tab, text="Capture Screen/Audio", font=ctk.CTkFont(size=20)).pack(pady=10)

        self.screen_btn = ctk.CTkButton(self.observe_tab, text="Capture Screenshot", command=self.capture_screenshot)
        self.screen_btn.pack(pady=5)

        self.audio_btn = ctk.CTkButton(self.observe_tab, text="Record Audio (5s)", command=self.record_audio)
        self.audio_btn.pack(pady=5)

        # Real-time toggle
        self.real_time_btn = ctk.CTkButton(self.observe_tab, text="Start Real-Time Recording", command=self.toggle_real_time)
        self.real_time_btn.pack(pady=5)

        self.observe_result = ctk.CTkTextbox(self.observe_tab, height=300)
        self.observe_result.pack(fill="both", expand=True, pady=10)

    def setup_understand_tab(self):
        ctk.CTkLabel(self.understand_tab, text="Analyze Observations", font=ctk.CTkFont(size=20)).pack(pady=10)

        self.analyze_btn = ctk.CTkButton(self.understand_tab, text="Analyze for Patterns (Qwen)", command=self.analyze_patterns)
        self.analyze_btn.pack(pady=5)

        self.understand_result = ctk.CTkTextbox(self.understand_tab, height=300)
        self.understand_result.pack(fill="both", expand=True, pady=10)

    def setup_automate_tab(self):
        ctk.CTkLabel(self.automate_tab, text="Execute Workflow", font=ctk.CTkFont(size=20)).pack(pady=10)

        self.workflow_select = ctk.CTkComboBox(self.automate_tab, values=[], command=self.select_workflow)
        self.workflow_select.pack(pady=5)

        self.execute_btn = ctk.CTkButton(self.automate_tab, text="Execute Selected Workflow", command=self.execute_workflow)
        self.execute_btn.pack(pady=5)

        self.automate_result = ctk.CTkTextbox(self.automate_tab, height=300)
        self.automate_result.pack(fill="both", expand=True, pady=10)

    def setup_data_tab(self):
        ctk.CTkLabel(self.data_tab, text="Manage Data", font=ctk.CTkFont(size=20)).pack(pady=10)

        self.refresh_btn = ctk.CTkButton(self.data_tab, text="Refresh Data", command=self.refresh_data)
        self.refresh_btn.pack(pady=5)

        self.purge_btn = ctk.CTkButton(self.data_tab, text="Purge Old Data", command=self.purge_data)
        self.purge_btn.pack(pady=5)

        self.data_result = ctk.CTkTextbox(self.data_tab, height=300)
        self.data_result.pack(fill="both", expand=True, pady=10)

    # Observe Methods
    def capture_screenshot(self):
        Thread(target=self._capture_screenshot_thread).start()

    def _capture_screenshot_thread(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save("temp_screenshot.png")

        # OCR
        try:
            with open("temp_screenshot.png", "rb") as f:
                files = {"file": ("temp.png", f, "image/png")}
                res = requests.post(self.OCR_URL, files=files, timeout=120)
                if res.status_code == 200:
                    ocr_data = res.json()
                    obs = {"type": "screen", "data": ocr_data, "timestamp": datetime.now().isoformat()}
                    self.observations.append(obs)
                    self.observe_result.insert("end", f"Screenshot OCR:\n{json.dumps(ocr_data, indent=2)}\n\n")
                    self.observe_result.see("end")
                else:
                    messagebox.showerror("OCR Error", res.text)
        except Exception as e:
            messagebox.showerror("Capture Error", str(e))

    def record_audio(self):
        Thread(target=self._record_audio_thread).start()

    def _record_audio_thread(self):
        fs = 16000
        duration = 5
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
        audio = recording.flatten().astype(np.float32)

        # Save temp WAV
        sf.write("temp_audio.wav", audio, fs)

        # STT
        try:
            with open("temp_audio.wav", "rb") as f:
                files = {"file": ("temp.wav", f, "audio/wav")}
                res = requests.post(self.STT_URL, files=files, timeout=30)
                if res.status_code == 200:
                    stt_data = res.json()
                    obs = {"type": "audio", "data": stt_data, "timestamp": datetime.now().isoformat()}
                    self.observations.append(obs)
                    self.observe_result.insert("end", f"Audio STT:\n{json.dumps(stt_data, indent=2)}\n\n")
                    self.observe_result.see("end")
                else:
                    messagebox.showerror("STT Error", res.text)
        except Exception as e:
            messagebox.showerror("Record Error", str(e))

    def toggle_real_time(self):
        self.is_real_time = not self.is_real_time
        self.real_time_btn.configure(text="Stop Real-Time" if self.is_real_time else "Start Real-Time")
        if self.is_real_time:
            Thread(target=self._real_time_loop).start()

    def _real_time_loop(self):
        event_log = []
        start_time = time.time()
        while self.is_real_time:
            # Screenshot every 1s
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                img.save(f"rt_frame_{int(time.time())}.png")

            # Log mouse position/click
            mouse_pos = pyautogui.position()
            event = {"timestamp": datetime.now().isoformat(), "type": "mouse", "position": [mouse_pos.x, mouse_pos.y]}
            event_log.append(event)

            # OCR every 5 frames (every 5s)
            if len(event_log) % 5 == 0:
                try:
                    with open(f"rt_frame_{int(time.time())}.png", "rb") as f:
                        files = {"file": ("rt.png", f, "image/png")}
                        res = requests.post(self.OCR_URL, files=files, timeout=120)
                        if res.status_code == 200:
                            ocr_data = res.json()
                            event["ocr"] = ocr_data
                except Exception as e:
                    Logger.error(f"Real-time OCR error: {e}")

            time.sleep(1)

        # Save sequence on stop
        self.observations.append({"type": "real_time_sequence", "data": event_log, "duration": time.time() - start_time})
        self.observe_result.insert("end", f"Real-time sequence saved: {len(event_log)} events\n")
        self.observe_result.see("end")

    # Understand Methods
    def analyze_patterns(self):
        Thread(target=self._analyze_patterns_thread).start()

    def _analyze_patterns_thread(self):
        if not self.observations:
            messagebox.showwarning("No Data", "Record some observations first")
            return

        # Get recent observations
        recent_obs = self.observations[-3:]  # Last 3
        obs_text = "\n".join([json.dumps(obs.get("data", {}), indent=2) for obs in recent_obs])  # FIXED: .get("data", {}) safe

        prompt = f"""Analyze these recent observations for repetitive workflows or patterns. Suggest automatable steps.

Observations:
{obs_text}

Output JSON:
{{
  "detected_patterns": [
    {{
      "pattern_name": "e.g., Edit Docker File",
      "description": "Click docker-compose.yml and type env",
      "confidence": 0.8,
      "steps": [
        {{"step": "click", "element": "docker-compose.yml"}},
        {{"step": "type", "value": "env: OLLAMA_HOST=0.0.0.0"}}
      ]
    }}
  ]
}}"""

        payload = {
            "model": "qwen2.5:latest",  # FIXED: :latest
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }

        try:
            res = requests.post(self.OLLAMA_URL, json=payload, timeout=60)
            if res.status_code == 200:
                analysis = res.json()["response"]
                try:
                    parsed = json.loads(analysis)
                    self.understand_result.insert("end", f"Qwen Analysis:\n{json.dumps(parsed, indent=2)}\n\n")
                    self.understand_result.see("end")
                except:
                    self.understand_result.insert("end", f"Raw Analysis: {analysis[:1000]}\n\n")
                    self.understand_result.see("end")
            else:
                messagebox.showerror("Analysis Error", res.text)
        except Exception as e:
            messagebox.showerror("Analysis Error", str(e))

    # Automate Methods
    def select_workflow(self, selection):
        self.selected_workflow = selection

    def execute_workflow(self):
        if self.selected_workflow is None:  # FIXED: Explicit None check
            messagebox.showwarning("No Workflow", "Select a workflow first")
            return

        Thread(target=self._execute_workflow_thread).start()

    def _execute_workflow_thread(self):
        # Get workflow from DB
        try:
            res = requests.get(f"{self.DB_URL}/get_workflows?limit=10")
            workflows = res.json()
            wf = next((w for w in workflows if w["pattern_text"] == self.selected_workflow), None)
            if not wf:
                messagebox.showerror("Workflow Not Found", "Selected workflow not in DB")
                return

            steps = wf["steps_json"]
            self.automate_result.insert("end", f"Executing: {wf['pattern_text']}\n\n")
            self.automate_result.see("end")

            for i, step in enumerate(steps):
                self.automate_result.insert("end", f"Step {i+1}: {step['step']} on {step['element']}\n")
                self.automate_result.update()

                if step["step"] == "click":
                    x, y = step.get("position", [100, 100])
                    pyautogui.click(x, y)
                elif step["step"] == "type":
                    pyautogui.typewrite(step.get("value", ""))
                time.sleep(0.5)  # Pause between steps

            # Increment run count
            requests.post(f"{self.DB_URL}/increment_workflow_run/{wf['id']}")
            self.automate_result.insert("end", "Execution complete!\n")
            self.automate_result.see("end")

            # Refresh workflows
            self.refresh_workflows()
        except Exception as e:
            messagebox.showerror("Execution Error", str(e))

    # Data Methods
    def refresh_data(self):
        Thread(target=self._refresh_data_thread).start()

    def _refresh_data_thread(self):
        try:
            # Get observations
            res_obs = requests.get(f"{self.DB_URL}/get_observations?limit=10")
            self.observations = res_obs.json()

            # Get workflows
            res_wf = requests.get(f"{self.DB_URL}/get_workflows?limit=10")
            self.workflows = res_wf.json()
            self.workflow_select.configure(values=[w["pattern_text"] for w in self.workflows])

            data_text = f"Observations: {len(self.observations)}\nWorkflows: {len(self.workflows)}\n\n"
            data_text += "Recent Observations:\n"
            for obs in self.observations[-3:]:
                data_text += f"- {obs['type']} at {obs['timestamp'][:19]}\n"
            data_text += "\nRecent Workflows:\n"
            for wf in self.workflows[-3:]:
                data_text += f"- {wf['pattern_text']} (runs: {wf['run_count']})\n"

            self.data_result.delete("1.0", "end")
            self.data_result.insert("1.0", data_text)
        except Exception as e:
            messagebox.showerror("Data Refresh Error", str(e))

    def purge_data(self):
        if messagebox.askyesno("Confirm Purge", "Delete old data?"):
            try:
                res = requests.post(f"{self.DB_URL}/purge_old", json={"days_old": 7})
                if res.status_code == 200:
                    messagebox.showinfo("Purge Complete", res.json()["message"])
                    self.refresh_data()
                else:
                    messagebox.showerror("Purge Error", res.text)
            except Exception as e:
                messagebox.showerror("Purge Error", str(e))

    def refresh_workflows(self):
        try:
            res = requests.get(f"{self.DB_URL}/get_workflows?limit=10")
            self.workflows = res.json()
            self.workflow_select.configure(values=[w["pattern_text"] for w in self.workflows])
        except Exception as e:
            messagebox.showerror("Refresh Error", str(e))

if __name__ == "__main__":
    app = AGIAssistant()
    app.mainloop()
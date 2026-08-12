"""ShiftScout: a standard-library-only job hunting portal."""

from __future__ import annotations

import html
import json
import re
import sqlite3
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


DB_PATH = Path(__file__).with_name("shiftscout.db")

KNOWN_SKILLS = {
    "python", "java", "javascript", "typescript", "sql", "excel", "aws",
    "azure", "docker", "kubernetes", "react", "django", "flask", "fastapi",
    "git", "linux", "power bi", "tableau", "machine learning", "data analysis",
    "project management", "customer service", "sales", "marketing", "finance",
}

DEMO_JOBS = [
    {"title": "Junior Python Developer", "company_name": "Northstar Labs", "location": "Remote", "remote": True,
     "description": "Build Python services using Flask, SQL, Git and Docker. Work with a supportive product team.", "url": "https://example.com/jobs/python"},
    {"title": "Data Analyst", "company_name": "Bright Metrics", "location": "Berlin", "remote": False,
     "description": "Analyse business data with SQL, Excel, Python, Power BI and clear stakeholder communication.", "url": "https://example.com/jobs/analyst"},
    {"title": "Customer Success Specialist", "company_name": "Cloud Desk", "location": "Remote", "remote": True,
     "description": "Help customers, manage accounts and collaborate with sales. Customer service and communication required.", "url": "https://example.com/jobs/success"},
    {"title": "Frontend Developer", "company_name": "Pixel Works", "location": "Munich", "remote": False,
     "description": "Create accessible web applications with JavaScript, TypeScript, React and Git.", "url": "https://example.com/jobs/frontend"},
]


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", value).strip()


@dataclass
class Profile:
    name: str
    email: str
    location: str
    desired_role: str
    skills: str
    cv_text: str
    remote_only: bool


class Store:
    def __init__(self, path: Path = DB_PATH):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id=1), name TEXT, email TEXT, location TEXT, desired_role TEXT, skills TEXT, cv_text TEXT, remote_only INTEGER)")
        self.db.execute("CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, title TEXT, company TEXT, url TEXT, status TEXT, created_at TEXT)")
        self.db.commit()

    def save_profile(self, p: Profile) -> None:
        self.db.execute("INSERT OR REPLACE INTO profile VALUES (1,?,?,?,?,?,?,?)", (p.name, p.email, p.location, p.desired_role, p.skills, p.cv_text, int(p.remote_only)))
        self.db.commit()

    def load_profile(self) -> Profile | None:
        row = self.db.execute("SELECT name,email,location,desired_role,skills,cv_text,remote_only FROM profile WHERE id=1").fetchone()
        return Profile(*row[:-1], bool(row[-1])) if row else None

    def track(self, job: dict) -> None:
        self.db.execute("INSERT INTO applications(title,company,url,status,created_at) VALUES(?,?,?,?,?)", (job["title"], job["company_name"], job.get("url", ""), "Interested", datetime.now().isoformat(timespec="minutes")))
        self.db.commit()

    def applications(self):
        return self.db.execute("SELECT title,company,status,created_at FROM applications ORDER BY id DESC").fetchall()


class JobAgent:
    """A transparent agent loop: understand, plan, retrieve, rank, explain."""

    def infer_skills(self, profile: Profile) -> list[str]:
        text = f"{profile.skills} {profile.cv_text}".lower()
        found = {skill for skill in KNOWN_SKILLS if re.search(rf"\b{re.escape(skill)}\b", text)}
        found.update(x.strip().lower() for x in profile.skills.split(",") if x.strip())
        return sorted(found)

    def plan(self, profile: Profile) -> str:
        skills = self.infer_skills(profile)
        focus = profile.desired_role or (skills[0] if skills else "general")
        place = "remote" if profile.remote_only else (profile.location or "any location")
        return f"Goal: find {focus} roles in {place}.\nSignals: {', '.join(skills[:10]) or 'role and CV terms'}.\nActions: retrieve jobs → score relevance → explain top matches → let user review and track."

    def fetch(self, live: bool) -> tuple[list[dict], str]:
        if not live:
            return DEMO_JOBS, "Offline demo catalogue"
        try:
            req = urllib.request.Request("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": "ShiftScout/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.load(response).get("data", [])
            jobs = [{"title": j.get("title", "Untitled"), "company_name": j.get("company_name", "Unknown"),
                     "location": j.get("location", ""), "remote": bool(j.get("remote")),
                     "description": clean_text(j.get("description", "")), "url": j.get("url", "")} for j in data]
            return jobs, f"Live feed ({len(jobs)} jobs)"
        except Exception as exc:
            return DEMO_JOBS, f"Live feed unavailable; using demos ({type(exc).__name__})"

    def rank(self, profile: Profile, jobs: list[dict]) -> list[dict]:
        skills = self.infer_skills(profile)
        role_terms = set(re.findall(r"[a-z+#.]{2,}", profile.desired_role.lower()))
        results = []
        for job in jobs:
            haystack = f"{job['title']} {job['description']}".lower()
            matched_skills = [s for s in skills if s in haystack]
            matched_role = [t for t in role_terms if t in haystack]
            score = min(100, 15 * len(matched_skills) + 18 * len(matched_role))
            if profile.remote_only:
                score += 15 if job.get("remote") else -40
            if profile.location and profile.location.lower() in job.get("location", "").lower():
                score += 10
            job = dict(job)
            job["score"] = max(0, min(100, score))
            reasons = []
            if matched_role: reasons.append("role alignment: " + ", ".join(matched_role))
            if matched_skills: reasons.append("skill matches: " + ", ".join(matched_skills[:6]))
            if job.get("remote") and profile.remote_only: reasons.append("remote preference")
            job["reason"] = "; ".join(reasons) or "limited direct keyword overlap—review manually"
            results.append(job)
        return sorted(results, key=lambda j: j["score"], reverse=True)

    def application_note(self, p: Profile, job: dict) -> str:
        skills = [s for s in self.infer_skills(p) if s in job["description"].lower()][:4]
        evidence = ", ".join(skills) or "my relevant experience and transferable skills"
        return (f"Hello {job['company_name']} hiring team,\n\nI am interested in the {job['title']} role. "
                f"My background includes {evidence}, which aligns with the position. I would welcome the opportunity "
                f"to discuss how I could contribute to your team.\n\nKind regards,\n{p.name}\n{p.email}")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ShiftScout — Job Hunting Agent")
        self.geometry("1050x720")
        self.minsize(850, 600)
        self.store, self.agent, self.jobs = Store(), JobAgent(), []
        self.vars = {k: tk.StringVar() for k in ("name", "email", "location", "role", "skills")}
        self.remote, self.live, self.status = tk.BooleanVar(), tk.BooleanVar(value=True), tk.StringVar(value="Ready")
        self._build()
        self._load()

    def _build(self):
        tabs = ttk.Notebook(self); tabs.pack(fill="both", expand=True, padx=10, pady=10)
        profile = ttk.Frame(tabs, padding=14); results = ttk.Frame(tabs, padding=14); tracker = ttk.Frame(tabs, padding=14)
        tabs.add(profile, text="1. My profile"); tabs.add(results, text="2. Find jobs"); tabs.add(tracker, text="3. Tracker")
        fields = [("Full name", "name"), ("Email", "email"), ("Location", "location"), ("Desired role", "role"), ("Skills (comma separated)", "skills")]
        for row, (label, key) in enumerate(fields):
            ttk.Label(profile, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(profile, textvariable=self.vars[key], width=70).grid(row=row, column=1, sticky="ew", pady=5)
        ttk.Label(profile, text="CV text").grid(row=5, column=0, sticky="nw", pady=5)
        self.cv = tk.Text(profile, height=16, wrap="word"); self.cv.grid(row=5, column=1, sticky="nsew", pady=5)
        buttons = ttk.Frame(profile); buttons.grid(row=6, column=1, sticky="w")
        ttk.Button(buttons, text="Import text CV", command=self.import_cv).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save profile", command=self.save).pack(side="left")
        ttk.Checkbutton(profile, text="Remote jobs only", variable=self.remote).grid(row=7, column=1, sticky="w", pady=8)
        profile.columnconfigure(1, weight=1); profile.rowconfigure(5, weight=1)

        top = ttk.Frame(results); top.pack(fill="x")
        ttk.Checkbutton(top, text="Use live jobs", variable=self.live).pack(side="left")
        ttk.Button(top, text="Run job agent", command=self.search).pack(side="left", padx=10)
        ttk.Label(top, textvariable=self.status).pack(side="left")
        self.plan_box = tk.Text(results, height=4, wrap="word", background="#f3f4f6"); self.plan_box.pack(fill="x", pady=10)
        self.tree = ttk.Treeview(results, columns=("score", "title", "company", "location"), show="headings", height=12)
        for col, width in (("score", 65), ("title", 300), ("company", 210), ("location", 180)):
            self.tree.heading(col, text=col.title()); self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True); self.tree.bind("<<TreeviewSelect>>", self.show_job)
        self.detail = tk.Text(results, height=9, wrap="word"); self.detail.pack(fill="x", pady=8)
        actions = ttk.Frame(results); actions.pack(fill="x")
        ttk.Button(actions, text="Track selected", command=self.track).pack(side="left")
        ttk.Button(actions, text="Generate application note", command=self.note).pack(side="left", padx=8)

        self.app_tree = ttk.Treeview(tracker, columns=("title", "company", "status", "date"), show="headings")
        for col in ("title", "company", "status", "date"): self.app_tree.heading(col, text=col.title())
        self.app_tree.pack(fill="both", expand=True)
        ttk.Button(tracker, text="Refresh", command=self.refresh_tracker).pack(anchor="w", pady=8)

    def profile(self):
        return Profile(self.vars["name"].get().strip(), self.vars["email"].get().strip(), self.vars["location"].get().strip(), self.vars["role"].get().strip(), self.vars["skills"].get().strip(), self.cv.get("1.0", "end").strip(), self.remote.get())

    def save(self, quiet=False):
        p = self.profile()
        if not p.name or not p.email: messagebox.showwarning("Missing details", "Please enter your name and email."); return False
        if "@" not in p.email: messagebox.showwarning("Invalid email", "Please enter a valid email address."); return False
        self.store.save_profile(p)
        if not quiet: messagebox.showinfo("Saved", "Your profile was saved locally.")
        return True

    def _load(self):
        p = self.store.load_profile()
        if p:
            for k, v in (("name", p.name), ("email", p.email), ("location", p.location), ("role", p.desired_role), ("skills", p.skills)): self.vars[k].set(v)
            self.cv.insert("1.0", p.cv_text); self.remote.set(p.remote_only)
        self.refresh_tracker()

    def import_cv(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            try: self.cv.delete("1.0", "end"); self.cv.insert("1.0", Path(path).read_text(encoding="utf-8", errors="replace"))
            except OSError as exc: messagebox.showerror("Could not read CV", str(exc))

    def search(self):
        if not self.save(quiet=True): return
        p = self.profile(); self.plan_box.delete("1.0", "end"); self.plan_box.insert("1.0", self.agent.plan(p))
        self.status.set("Agent is searching…")
        threading.Thread(target=self._search_worker, args=(p,), daemon=True).start()

    def _search_worker(self, p):
        jobs, source = self.agent.fetch(self.live.get()); ranked = self.agent.rank(p, jobs)
        self.after(0, lambda: self._show_results(ranked, source))

    def _show_results(self, jobs, source):
        self.jobs = jobs
        for item in self.tree.get_children(): self.tree.delete(item)
        for i, job in enumerate(jobs[:100]): self.tree.insert("", "end", iid=str(i), values=(job["score"], job["title"], job["company_name"], job["location"]))
        self.status.set(source)

    def selected(self):
        selection = self.tree.selection()
        return self.jobs[int(selection[0])] if selection else None

    def show_job(self, _event=None):
        job = self.selected()
        if job:
            text = f"{job['title']} — {job['company_name']}\nMatch: {job['score']}% ({job['reason']})\nURL: {job['url']}\n\n{job['description'][:900]}"
            self.detail.delete("1.0", "end"); self.detail.insert("1.0", text)

    def track(self):
        job = self.selected()
        if not job: messagebox.showinfo("Select a job", "Select a job first."); return
        self.store.track(job); self.refresh_tracker(); messagebox.showinfo("Tracked", "Job added to your tracker.")

    def note(self):
        job = self.selected()
        if not job: messagebox.showinfo("Select a job", "Select a job first."); return
        note = self.agent.application_note(self.profile(), job)
        win = tk.Toplevel(self); win.title("Application note"); box = tk.Text(win, width=80, height=20, wrap="word"); box.pack(padx=12, pady=12); box.insert("1.0", note)

    def refresh_tracker(self):
        for item in self.app_tree.get_children(): self.app_tree.delete(item)
        for row in self.store.applications(): self.app_tree.insert("", "end", values=row)


if __name__ == "__main__":
    App().mainloop()

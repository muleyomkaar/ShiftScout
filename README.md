# ShiftScout

ShiftScout is a small, Python-only job hunting portal. It collects a candidate
profile and CV text, creates a simple search plan, fetches jobs, ranks them, and
tracks applications.

## Features

- Local profile storage with SQLite
- Paste CV text or import a `.txt` CV
- Rule-based "agent" extracts skills and builds search queries
- Optional live jobs from the public Arbeitnow feed
- Offline demo jobs when the network is unavailable
- Match scores and human-readable reasons
- Tailored application-note generation
- Application tracking

No API key and no third-party Python packages are required.

## Run

```powershell
python app.py
```

Data is stored locally in `shiftscout.db`. Live job retrieval requires internet
access; uncheck **Use live jobs** to work entirely offline.

## Notes

This is an educational MVP. Job matches should be reviewed by the user before
applying. The app never submits applications automatically.


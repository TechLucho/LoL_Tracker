# 🎮 LoL Performance Tracker

**LoL Performance Tracker** is a personal "High Performance" dashboard designed to foster discipline in Ranked games.

Unlike traditional stat sites, this tool focuses on the **human factor**: managing tilt, enforcing a strict Champion Pool, and analyzing optimal biological playtimes.

> **Note:** The application user interface is currently in Spanish for personal use, but the codebase and logic are documented here in English.

## ✨ Key Features

### 📊 Tab 1: Journal & Analysis
- **LP Tracker:** Visualizes cumulative LP gains/losses (Net) over the last 20 games.
- **Activity Heatmap:** Analyzes performance by "Day of Week vs. Hour" to identify biological patterns (e.g., "Do I play worse on Friday late nights?").
- **The Constitution:** A "Stop-Loss" rule system that alerts the user to stop playing after consecutive losses to prevent tilt.

### 🔎 Tab 2: Smart Scout
- **Nemesis Detector:** Automatically identifies enemy **Champions** (not players) against whom the user has the lowest historical Winrate.
- **Matchup History:** A searchable database to review personal notes from previous lane matchups (e.g., "Jax vs Renekton strategy").

### 🏆 Tab 3: Champion Pool
- **Main Control:** Strict performance monitoring (KDA, CS/min, WR) focused solely on the user's defined "Main" champions to encourage consistency.

---

## 🚀 Installation & Usage

### 1. Prerequisites
- Python 3.10 or higher.
- A Riot Games Developer Account (to obtain an API Key).

### 2. Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/TechLucho/LoL_Tracker.git
cd LoL_Tracker
pip install -r requirements.txt
```

---

## ⚖️ Legal Disclaimer

LoL Performance Tracker isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
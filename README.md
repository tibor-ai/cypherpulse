# CypherPulse

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Open-source X/Twitter analytics dashboard that tracks your tweet performance over time.**

CypherPulse automatically collects engagement metrics at 24h, 72h, and 7-day intervals after posting, giving you deep insights into what content resonates with your audience.

## ✨ Features

- 📊 **Automated Metrics Collection** — Snapshots at 24h, 72h, and 7 days after posting
- 📈 **Performance Analytics** — Track engagement by post type (tweets, replies, retweets)
- ⏰ **Timing Insights** — Discover your best hours and days to post
- 🎯 **Top Posts Tracking** — See which content performs best
- 🌐 **Beautiful Dashboard** — Dark-themed, responsive web interface
- 🔧 **Simple CLI** — Scan, collect, and report from the command line

## 🚀 Quick Start

### ⚡ Quick Install

**Ubuntu / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/tibor-ai/cypherpulse/main/install.sh | bash
```

**Windows (PowerShell as Administrator):**
```powershell
irm https://raw.githubusercontent.com/tibor-ai/cypherpulse/main/install.ps1 | iex
```

**Tested on:** Ubuntu 22.04+, macOS 13+, Windows 11

---

### 📦 Manual Installation

<details>
<summary>Click to expand manual installation steps</summary>

```bash
# Clone the repository
git clone https://github.com/tibor-ai/cypherpulse.git
cd cypherpulse

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

</details>

### Configuration

Create a `.env` file in the project root:

```bash
TWITTER_API_KEY=your_twitterapi_io_key_here
TWITTER_USERNAME=your_twitter_username
PORT=8080
```

**API Key**: Get your free API key from [twitterapi.io](https://twitterapi.io/)

### Usage

```bash
# Scan for new tweets
cypherpulse scan

# Collect metric snapshots (run daily)
cypherpulse collect

# View analytics report in terminal
cypherpulse report

# Start web dashboard
cypherpulse serve
```

Then open your browser to `http://localhost:8080`

## 📸 Screenshots

*Dashboard screenshots coming soon*

## 💡 Why CypherPulse?

- **Time-series tracking** — Most analytics tools only show current stats. CypherPulse tracks how engagement evolves over days.
- **Post type analysis** — Understand whether tweets, replies, or retweets perform better for your account.
- **Timing optimization** — Data-driven insights on when your audience is most engaged.

## 📋 How It Works

1. **Scan** — CypherPulse fetches your recent tweets via the Twitter API
2. **Track** — It registers each tweet and schedules metric collection at 24h, 72h, and 7d
3. **Analyze** — Visualize trends, compare post types, and optimize your content strategy

All data is stored locally in a SQLite database (`~/.cypherpulse/analytics.db`)

## 🛠️ Tech Stack

- **Python 3.8+** — Core application
- **FastAPI** — REST API and dashboard backend
- **SQLite** — Local data storage
- **Vanilla JS** — No heavy frontend frameworks, just clean, fast code

## 📦 Project Structure

```
cypherpulse/
├── cypherpulse/
│   ├── __init__.py
│   ├── collector.py    # Tweet scanning and metrics collection
│   ├── db.py           # Database operations
│   ├── api.py          # FastAPI backend
│   └── cli.py          # Command-line interface
├── web/
│   └── index.html      # Dashboard UI
├── requirements.txt
├── setup.py
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

Built with love for the Twitter developer community. Data provided by [twitterapi.io](https://twitterapi.io/).

---

**Made with ⚡ by the open-source community**

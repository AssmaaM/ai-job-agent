# 🤖 AutoJob AI Agent

Intelligent job search, AI-powered relevance scoring, and personalized application generation — all in one place.

## Features

- **Smart Job Search**: Multi-source job scraping from 6 real APIs (no mock data)
  - RemoteOK, Remotive, Arbeitnow, Jobicy, LinkedIn, Indeed
- **AI-Powered Scoring**: Uses OpenAI GPT-4o-mini to match your CV against job descriptions
- **Strict Filtering**: Only returns truly relevant jobs (not sales/marketing/unrelated roles)
- **Location Matching**: Accurate city/region matching with Remote support
- **Application Generation**: Auto-generates cover letters and LinkedIn messages
- **Memory Persistence**: Tracks search history and saved jobs
- **Web Interface**: Beautiful Streamlit dashboard

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ai-job-agent.git
cd ai-job-agent
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/Scripts/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your OpenAI API key
# OPENAI_API_KEY=sk-your-api-key-here
```

Get your OpenAI API key from: https://platform.openai.com/api-keys

### 5. Run the App
```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## Usage

1. **Enter Job Criteria**
   - Job title/keywords (e.g., "AI Engineer", "Python Developer")
   - Location (e.g., "Paris", "Remote", "New York")
   - Your CV/resume

2. **Configure Options** (Sidebar)
   - Top jobs to process (1-10)
   - Minimum relevance score filter
   - Toggle application generation

3. **Run Agent**
   - Click "🚀 Run Agent"
   - Monitor real-time reasoning logs
   - View results with relevance scores

4. **Download Applications**
   - Download cover letters
   - Download LinkedIn connection messages

## Project Structure

```
ai-job-agent/
├── app.py                    # Streamlit web interface
├── requirements.txt          # Python dependencies
├── agents/
│   └── job_agent.py         # Main orchestration logic
├── tools/
│   ├── job_search.py        # Multi-source job scraper
│   ├── job_matcher.py       # CV relevance scoring
│   └── application_generator.py  # Cover letter & LinkedIn message generation
├── utils/
│   └── memory.py            # Persistent search/job history
└── data/
    └── mock_jobs.json       # (Optional) Mock data reference
```

## Configuration

Edit sidebar settings:
- **Top jobs to process**: How many jobs to generate applications for
- **Minimum relevance score**: Filter out low-scoring jobs (0-80)
- **Generate Applications**: Uncheck to only score jobs (faster, saves API calls)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key for GPT-4o-mini |

Store in `.env` file (never commit this)

## Filtering Logic

The agent uses **strict semantic filtering** to return only relevant results:

- For "AI Engineer" searches:
  - ✅ Requires BOTH AI keywords (ai, ml, machine learning, nlp, llm) AND role keywords (engineer, developer, scientist)
  - ❌ Hard-rejects sales, marketing, HR, finance, support roles
  - ❌ Rejects "Computer Aided X" patterns (like CAD)
  - ✅ Matches location precisely (Paris matches "Paris, France")

- For multi-word queries: Requires at least 50% keyword match

## API Sources

All data comes from **real, live public APIs** (no mock fallback):

1. **RemoteOK** - Remote tech jobs
2. **Remotive** - Remote jobs across categories
3. **Arbeitnow** - Pan-European remote + location jobs
4. **Jobicy** - Remote tech-specific jobs
5. **LinkedIn** - Guest API (broad professional jobs)
6. **Indeed** - HTML scraping (location-specific jobs)

Results are merged, deduplicated, and limited to 8 total jobs per search.

## Memory & History

The app persists:
- **Search history** - Recent searches with result counts
- **Job runs** - Agent execution summaries
- **Saved jobs** - Bookmarked positions with scores

Data stored in `data/memory.json` (also git-ignored for privacy)

## Troubleshooting

### "No API key set. AI features will fail."
- Add your OpenAI API key to `.env`
- Restart the Streamlit app

### "No matching jobs found"
- Try broader keywords
- Try different locations
- Check internet connection

### Jobs found but not relevant
- Use more specific job titles
- Add location to narrow results

## Development

### Adding New Job Sources
Edit `tools/job_search.py` and add a `_scrape_newsource()` function

### Customizing Scoring
Edit `tools/job_matcher.py` → `score_job()` function

### Adjusting Filtering
Edit `tools/job_search.py` → `_query_hits()` function (lines ~71-140)

## License

MIT License - feel free to use and modify

## Support

Issues or suggestions? Create a GitHub issue or reach out!

---

Built with ❤️ using Streamlit + OpenAI GPT-4o-mini

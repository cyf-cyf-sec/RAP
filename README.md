# RAP

The implementation tool for the research work presented in the paper RealAICode. It aims to reproduce the data construction and experimental training workflows of RealAICode, and also supports crawling agent code from authentic repositories as well as model training and prediction.

## Architecture

```
RAP/
├── app/
│   ├── core/               # Core utilities
│   ├── routes/             # Flask route handlers
│   ├── services/           # Business logic layer
│   ├── utils/              # Helper utilities
│   ├── static/             # Frontend assets
│   ├── templates/          # Jinja2 HTML templates
│   └── __init__.py         # Flask app factory
├── .env                    # Environment variables file
├── config.py               # Application configuration
├── run.py                  # Entry point
└── requirements.txt        # Python dependencies
```

## Pipeline

The Tool processes a GitHub repository and crawls real source codethrough 6 steps :

| Step | Component          | Description                                                    |
|------|--------------------|----------------------------------------------------------------|
| 1    | PR Crawler         | Crawl all pull requests from a GitHub repository               |
| 2    | PR Filter          | Filter PRs by date range and merged status                     |
| 3    | PR Detail Crawler  | Fetch detailed commit information for each PR                  |
| 4    | File Analyzer      | Download code files modified in each PR                        |
| 5    | Function Extractor | Extract individual functions from code files using tree-sitter |
| 5.5  | Code Generator     | Generate equivalent functions via LLM                          |
| 6    | Deduplication      | Remove duplicate functions by content hash                     |

After the pipeline, you can train classifiers to distinguish human vs AI-generated code.


### Model Training
#### Deep Learning
- **ModernBERT**
- **GPTSniffer** 

## Installation

### Prerequisites

- Python 3.9+

### Setup

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd RAP
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:

| Variable                     | Description                                                  |
|------------------------------|--------------------------------------------------------------|
| `GITHUB_TOKEN` (mandatory)   | GitHub personal access token for API requests                |
| `SECRET_KEY`                 | Flask secret key for session management                      |
| `DEBUG`                      | Enable debug mode (`True`/`False`)                           |

5. Start the server

   ```bash
   python run.py
   ```
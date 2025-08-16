# Coventry University Research Publications Crawler

A specialized web crawler for extracting research publications from Coventry University's School of Economics, Finance and Accounting portal.

## Features

- Crawls all publication pages from the Pure Portal
- Extracts publication details: title, year, authors, and links
- Sends data to API endpoint after each page crawl
- Polite crawling with configurable delays to avoid 403 errors
- Comprehensive logging system
- Selenium-based crawling for dynamic content
- API integration with retry mechanism

## Project Structure

```
crawler/
├── src/
│   ├── __init__.py
│   ├── crawler.py          # Main crawler implementation
│   ├── parser.py           # HTML parsing utilities
│   └── utils.py            # Utility functions
├── logs/                   # Log files directory
├── data/                   # Output data directory
├── config/
│   └── settings.py         # Configuration settings
├── .github/workflows/
│   └── weekly-crawler.yml  # GitHub Actions workflow
├── requirements.txt        # Python dependencies
├── main.py                 # Entry point
├── test_setup.py           # Setup verification
├── test_api_local.py       # Local API testing with mock server
├── test_api_simple.py      # Simple API testing
└── README.md              # This file
```

## Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd crawler
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables** (for local development only):

   ```bash
   # Copy the example environment file
   cp env.example .env

   # Edit the .env file with your API endpoint for local testing
   # API_ENDPOINT=https://your-api.com/api/publications
   ```

5. **Create necessary directories**

   ```bash
   mkdir -p logs
   ```

6. **Test the setup**

   ```bash
   python test_setup.py
   ```

7. **Test API functionality (optional)**

   ```bash
   python test_api_simple.py
   ```

## Usage

Run the crawler:

```bash
python main.py
```

The crawler will:

- Start from the seed URL
- Crawl all available pages
- Extract publication information
- Send data to API endpoint after each page
- Log all activities to `logs/crawler.log`

## Configuration

Edit `config/settings.py` to modify:

- Crawling delays
- User agent strings
- Output file paths
- Logging levels

## API Integration

The crawler sends data to the API endpoint after each page crawl. The payload structure is:

```json
{
  "publications": [
    {
      "title": "Publication Title",
      "year": 2024,
      "authors": "Author Name",
      "publication_link": "https://example.com/publication",
      "author_links": "https://example.com/author",
      "page_number": 0
    }
  ]
}
```

### API Configuration

- **Endpoint**: Retrieved from GitHub secrets (required)
- **Method**: POST
- **Content-Type**: application/json
- **Retry Mechanism**: 3 attempts with 5-second delays (configurable)
- **Timeout**: 30 seconds (configurable)
- **GitHub Secrets**:
  - `API_ENDPOINT`: The API endpoint URL (required)
  - `API_TIMEOUT`: Request timeout in seconds (optional, default: 30)
  - `API_RETRIES`: Number of retry attempts (optional, default: 3)

## Logging

All crawling activities are logged to `logs/crawler.log` with timestamps and detailed information about:

- Page visits
- Extracted publications
- Errors and warnings
- Crawling statistics

## Robots.txt Compliance

The crawler respects robots.txt rules and implements polite crawling practices:

- Configurable delays between requests
- User agent identification
- Rate limiting

## Troubleshooting

### ChromeDriver Issues

If you encounter ChromeDriver errors:

1. **Manual installation via Homebrew**:

   ```bash
   brew install chromedriver
   ```

2. **Check Chrome version compatibility**:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version
   ```

### Common Issues

- **403 errors**: Increase delays in `config/settings.py`
- **Timeout errors**: Check network connectivity and increase timeout values
- **No publications found**: Verify website structure hasn't changed

## GitHub Actions

The crawler automatically runs via GitHub Actions in two scenarios:

1. **On Push to Master**: Triggers when code is pushed to the master/main branch
2. **Weekly Schedule**: Runs every Sunday at 2:00 AM UTC

### GitHub Secrets Setup

**Required**: The crawler uses GitHub secrets to retrieve the API endpoint URL. You must set up the following secrets in your repository:

1. Go to your repository → Settings → Secrets and variables → Actions
2. Add the following secrets:
   - `API_ENDPOINT`: Your API endpoint URL (e.g., `https://your-api.com/api/publications`) - **REQUIRED**
   - `API_TIMEOUT`: Request timeout in seconds (optional, default: 30)
   - `API_RETRIES`: Number of retry attempts (optional, default: 3)

Example:

```
API_ENDPOINT=https://your-production-api.com/api/publications
API_TIMEOUT=60
API_RETRIES=5
```

**Note**: You can test your secrets configuration by running the "Test GitHub Secrets" workflow manually from the Actions tab.

The workflow will:

- Install all dependencies
- Run the crawler
- Commit the results to the repository
- Provide detailed execution summaries

## Future Enhancements

- Database storage for historical data
- Web interface for querying results
- Advanced filtering and search capabilities

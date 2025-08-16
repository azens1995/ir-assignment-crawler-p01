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
   # Set environment variables for local testing
   export API_ENDPOINT=https://your-api.com/api/publications
   export API_TIMEOUT=30
   export API_RETRIES=3
   ```

5. **Create necessary directories**

   ```bash
   mkdir -p logs
   ```

6. **Run the crawler**

   ```bash
   python main.py
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
2. Click "New repository secret"
3. Add the following secrets:

   - **Name**: `API_ENDPOINT`
   - **Value**: Your API endpoint URL (e.g., `https://your-api.com/api/publications`)
   - **Required**: ✅ Yes

   - **Name**: `API_TIMEOUT`
   - **Value**: Request timeout in seconds (e.g., `30`)
   - **Required**: ❌ No (default: 30)

   - **Name**: `API_RETRIES`
   - **Value**: Number of retry attempts (e.g., `3`)
   - **Required**: ❌ No (default: 3)

Example:

```
API_ENDPOINT=https://your-production-api.com/api/publications
API_TIMEOUT=60
API_RETRIES=5
```

**Note**: Make sure to set up your GitHub secrets before running the workflow.

### Troubleshooting

#### **API_ENDPOINT shows as empty:**

- ✅ **Check**: Go to repository → Settings → Secrets and variables → Actions
- ✅ **Verify**: `API_ENDPOINT` secret exists and has a value
- ✅ **Format**: Ensure the URL is complete (e.g., `https://your-api.com/api/publications`)

#### **Workflow fails with "API_ENDPOINT secret is not set":**

- ✅ **Solution**: Add the `API_ENDPOINT` secret in repository settings
- ✅ **Value**: Use your complete API endpoint URL

The workflow will:

- Install all dependencies
- Run the crawler
- Commit the results to the repository
- Provide detailed execution summaries

## Future Enhancements

- Database storage for historical data
- Web interface for querying results
- Advanced filtering and search capabilities

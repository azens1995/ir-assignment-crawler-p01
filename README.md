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

4. **Create necessary directories**

   ```bash
   mkdir -p logs
   ```

5. **Run the crawler**

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

- **Endpoint**: `https://api.irapi.workers.dev/api/publications`
- **Method**: POST
- **Content-Type**: application/json
- **Retry Mechanism**: 3 attempts with 5-second delays
- **Timeout**: 30 seconds

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

### Troubleshooting

#### **API Connection Issues:**

- ✅ **Check**: Verify the API endpoint is accessible
- ✅ **Test**: The endpoint should return a valid JSON response
- ✅ **Format**: Ensure proper network connectivity

The workflow will:

- Install all dependencies
- Run the crawler
- Commit the results to the repository
- Provide detailed execution summaries

## Future Enhancements

- Database storage for historical data
- Web interface for querying results
- Advanced filtering and search capabilities

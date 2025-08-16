#!/usr/bin/env python3
"""
Test script for local API testing with mock server.
"""

import sys
import time
import json
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils import send_to_api, setup_logging
from config.settings import API_ENDPOINT

# Override API endpoint for testing
API_ENDPOINT = "http://localhost:8788/api/publications"


class MockAPIHandler(BaseHTTPRequestHandler):
    """Mock API server handler."""
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/publications':
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Parse JSON
                data = json.loads(post_data.decode('utf-8'))
                publications = data.get('publications', [])
                
                print(f"📥 Received {len(publications)} publications:")
                for i, pub in enumerate(publications[:3]):  # Show first 3
                    print(f"  {i+1}. {pub.get('title', 'No title')[:50]}...")
                if len(publications) > 3:
                    print(f"  ... and {len(publications) - 3} more")
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"status": "success", "received": len(publications)}
                self.wfile.write(json.dumps(response).encode())
                
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"status": "error", "message": "Invalid JSON"}
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def start_mock_server(port=8788):
    """Start mock API server."""
    server = HTTPServer(('localhost', port), MockAPIHandler)
    print(f"🚀 Starting mock API server on http://localhost:{port}")
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return server


def test_api_functionality():
    """Test API functionality with mock data."""
    print("🧪 Testing API Functionality")
    print("=" * 50)
    
    # Start mock server
    server = start_mock_server()
    time.sleep(1)  # Give server time to start
    
    try:
        # Setup logging
        setup_logging()
        
        # Test data
        test_publications = [
            {
                "title": "Test Publication 1",
                "year": "2024",
                "authors": "John Doe, Jane Smith",
                "publication_link": "https://example.com/pub1",
                "author_links": "https://example.com/author1, https://example.com/author2",
                "page_number": 0
            },
            {
                "title": "Test Publication 2",
                "year": "2025",
                "authors": "Alice Johnson",
                "publication_link": "https://example.com/pub2",
                "author_links": "https://example.com/author3",
                "page_number": 0
            }
        ]
        
        print(f"\n📤 Sending test data to {API_ENDPOINT}")
        
        # Test API call
        success = send_to_api(test_publications)
        
        if success:
            print("✅ API test successful!")
        else:
            print("❌ API test failed!")
        
        # Test with invalid data
        print(f"\n📤 Testing with empty data...")
        success = send_to_api([])
        if not success:
            print("✅ Correctly handled empty data")
        
        # Test with malformed data
        print(f"\n📤 Testing with malformed data...")
        malformed_data = [{"title": "Test", "invalid_field": "value"}]
        success = send_to_api(malformed_data)
        if success:
            print("✅ API accepted malformed data (flexible)")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
    
    finally:
        # Stop server
        print("\n🛑 Stopping mock server...")
        server.shutdown()
        server.server_close()


def test_crawler_with_api():
    """Test the crawler with API integration."""
    print("\n🕷️ Testing Crawler with API Integration")
    print("=" * 50)
    
    # Start mock server
    server = start_mock_server()
    time.sleep(1)
    
    try:
        from src.crawler import CoventryPublicationsCrawler
        
        print("Starting crawler test...")
        crawler = CoventryPublicationsCrawler()
        
        # Run crawler for just 1 page to test API integration
        crawler.setup_driver()
        
        # Navigate to first page
        success = crawler.navigate_to_page("https://pureportal.coventry.ac.uk/en/organisations/fbl-school-of-economics-finance-and-accounting/publications/?page=0")
        
        if success:
            print("✅ Successfully navigated to page")
            
            # Extract publications
            publications = crawler.extract_publications_from_page("https://pureportal.coventry.ac.uk/en/organisations/fbl-school-of-economics-finance-and-accounting/publications/?page=0")
            
            if publications:
                print(f"✅ Extracted {len(publications)} publications")
                
                # Test API call
                api_success = send_to_api(publications)
                if api_success:
                    print("✅ Successfully sent publications to API")
                else:
                    print("❌ Failed to send publications to API")
            else:
                print("❌ No publications extracted")
        else:
            print("❌ Failed to navigate to page")
        
        crawler.close_driver()
        
    except Exception as e:
        print(f"❌ Crawler test failed: {e}")
    
    finally:
        # Stop server
        print("\n🛑 Stopping mock server...")
        server.shutdown()
        server.server_close()


def main():
    """Main test function."""
    print("Coventry University Publications Crawler - API Test")
    print("=" * 60)
    
    # Test 1: Basic API functionality
    test_api_functionality()
    
    # Test 2: Crawler with API integration
    test_crawler_with_api()
    
    print("\n" + "=" * 60)
    print("✅ API testing completed!")
    print("\nTo run the full crawler with API:")
    print("  python main.py")


if __name__ == "__main__":
    main()

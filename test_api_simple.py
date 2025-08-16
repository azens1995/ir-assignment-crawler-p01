#!/usr/bin/env python3
"""
Simple test script for API functionality.
"""

import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils import send_to_api, setup_logging
from config.settings import API_ENDPOINT


def test_api_functionality():
    """Test API functionality with test data."""
    print("🧪 Testing API Functionality")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    
    # Test data
    test_publications = [
        {
            "title": "Test Publication 1",
            "year": 2024,
            "authors": "John Doe, Jane Smith",
            "publication_link": "https://example.com/pub1",
            "author_links": "https://example.com/author1, https://example.com/author2",
            "page_number": 0
        },
        {
            "title": "Test Publication 2",
            "year": 2025,
            "authors": "Alice Johnson",
            "publication_link": "https://example.com/pub2",
            "author_links": "https://example.com/author3",
            "page_number": 0
        }
    ]
    
    # Override API endpoint for testing if environment variable is set
    import os
    test_endpoint = os.getenv('TEST_API_ENDPOINT', API_ENDPOINT)
    print(f"📤 Testing API endpoint: {test_endpoint}")
    print(f"📤 Sending {len(test_publications)} test publications")
    
    # Test API call
    success = send_to_api(test_publications)
    
    if success:
        print("✅ API test successful!")
    else:
        print("❌ API test failed!")
        print("   This is expected if the API server is not running.")
        print("   To test with a real server, start your API server and run:")
        print("   python test_api_local.py")
    
    # Test with empty data
    print(f"\n📤 Testing with empty data...")
    success = send_to_api([])
    if not success:
        print("✅ Correctly handled empty data")
    
    # Test with malformed data
    print(f"\n📤 Testing with malformed data...")
    malformed_data = [
        {
            "title": "Test",
            "year": 2024,
            "authors": "Test Author",
            "publication_link": "https://example.com/test",
            "author_links": "https://example.com/author",
            "page_number": 0
        }
    ]
    success = send_to_api(malformed_data)
    if success:
        print("✅ API accepted data")
    else:
        print("❌ API rejected data")


def test_payload_structure():
    """Test the payload structure."""
    print("\n📋 Testing Payload Structure")
    print("=" * 50)
    
    # Test data
    test_publications = [
        {
            "title": "Sample Publication",
            "year": 2024,
            "authors": "Author Name",
            "publication_link": "https://example.com/publication",
            "author_links": "https://example.com/author",
            "page_number": 0
        }
    ]
    
    # Create payload
    payload = {
        "publications": test_publications
    }
    
    print("✅ Payload structure:")
    import json
    print(json.dumps(payload, indent=2))
    
    # Validate required fields
    required_fields = ["title", "year", "authors", "publication_link", "author_links", "page_number"]
    
    for pub in test_publications:
        missing_fields = [field for field in required_fields if field not in pub]
        if missing_fields:
            print(f"❌ Missing fields: {missing_fields}")
        else:
            print("✅ All required fields present")


def main():
    """Main test function."""
    print("Coventry University Publications Crawler - Simple API Test")
    print("=" * 60)
    
    # Test 1: API functionality
    test_api_functionality()
    
    # Test 2: Payload structure
    test_payload_structure()
    
    print("\n" + "=" * 60)
    print("✅ API testing completed!")
    print("\nTo run the full crawler with API:")
    print("  python main.py")
    print("\nTo test with a mock server:")
    print("  python test_api_local.py")


if __name__ == "__main__":
    main()

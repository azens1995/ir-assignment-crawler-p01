#!/usr/bin/env python3
"""
Test script to verify the crawler setup and dependencies.
"""

import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import selenium
        print("✅ Selenium imported successfully")
    except ImportError as e:
        print(f"❌ Selenium import failed: {e}")
        return False
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        print("✅ WebDriver Manager imported successfully")
    except ImportError as e:
        print(f"❌ WebDriver Manager import failed: {e}")
        return False
    
    try:
        from bs4 import BeautifulSoup
        print("✅ BeautifulSoup imported successfully")
    except ImportError as e:
        print(f"❌ BeautifulSoup import failed: {e}")
        return False
    
    try:
        from loguru import logger
        print("✅ Loguru imported successfully")
    except ImportError as e:
        print(f"❌ Loguru import failed: {e}")
        return False
    
    try:
        import pandas as pd
        print("✅ Pandas imported successfully")
    except ImportError as e:
        print(f"❌ Pandas import failed: {e}")
        return False
    
    return True

def test_config():
    """Test if configuration can be loaded."""
    print("\nTesting configuration...")
    
    try:
        from config.settings import SEED_URL, BASE_URL, DELAY_BETWEEN_PAGES
        print("✅ Configuration loaded successfully")
        print(f"   Seed URL: {SEED_URL}")
        print(f"   Base URL: {BASE_URL}")
        print(f"   Delay between pages: {DELAY_BETWEEN_PAGES}s")
        return True
    except ImportError as e:
        print(f"❌ Configuration import failed: {e}")
        return False

def test_crawler_initialization():
    """Test if crawler can be initialized."""
    print("\nTesting crawler initialization...")
    
    try:
        from src.crawler import CoventryPublicationsCrawler
        crawler = CoventryPublicationsCrawler()
        print("✅ Crawler initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Crawler initialization failed: {e}")
        return False


def test_chromedriver():
    """Test if ChromeDriver is working properly."""
    print("\nTesting ChromeDriver...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Try to create a driver
        driver = webdriver.Chrome(options=options)
        driver.quit()
        
        print("✅ ChromeDriver working correctly")
        return True
        
    except Exception as e:
        print(f"❌ ChromeDriver test failed: {e}")
        print("   This is common on macOS ARM64 systems.")
        print("   Run: python3 install_chromedriver.py")
        return False

def test_directories():
    """Test if required directories exist."""
    print("\nTesting directories...")
    
    required_dirs = ["logs", "data", "src", "config"]
    all_exist = True
    
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✅ Directory '{dir_name}' exists")
        else:
            print(f"❌ Directory '{dir_name}' missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests."""
    print("Coventry University Publications Crawler - Setup Test")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_crawler_initialization,
        test_chromedriver,
        test_directories
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The crawler is ready to use.")
        print("\nTo run the crawler:")
        print("  python main.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nTo install dependencies:")
        print("  pip install -r requirements.txt")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

import sys

def ensure_playwright_firefox():
    """Check if Playwright Firefox is installed, install if not."""
    try:
        # Try importing playwright
        from playwright.sync_api import sync_playwright

        # Test if Firefox is installed
        with sync_playwright() as p:
            try:
                # Just try to launch and immediately close
                browser = p.firefox.launch()
                browser.close()
                return True  # Firefox is installed and working
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    print("Playwright Firefox browser is not installed.")
                    print("Installing Playwright Firefox browser...")

                    # Use subprocess to run the installation command
                    import subprocess
                    result = subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "firefox"],
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0:
                        print("Playwright Firefox installed successfully!")
                        return True
                    else:
                        print(f"Failed to install Playwright Firefox: {result.stderr}")
                        return False
                else:
                    print(f"Error launching Firefox: {e}")
                    return False
    except ImportError:
        print("Playwright package is not installed.")
        return False
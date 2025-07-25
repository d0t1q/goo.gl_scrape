# goo.gl URL Scanner

A modern Python script to scan and archive goo.gl shortened URLs before Google's service shutdown on **August 25th, 2025**. This tool efficiently handles Google's warning pages, extracts real destination URLs, and provides comprehensive scanning capabilities.

## 🚨 Urgent Notice

**goo.gl will stop working on August 25th, 2025!** This scanner helps preserve URL mappings before the service is permanently shut down.

## ✨ Features

- **Smart Warning Page Bypass** - Automatically handles Google's shutdown warning pages
- **Auto-Resume Capability** - Continues scanning from where it left off
- **Flexible URL Length** - Scan 4, 5, 6+ character combinations  
- **404 Filtering** - Option to skip recording non-existent URLs
- **Progress Tracking** - Real-time logging and CSV output
- **Rate Limiting** - Configurable delays to be respectful to servers
- **Debug Mode** - Detailed logging for troubleshooting
- **Modern Python** - Type hints, proper error handling, and logging

## 📋 Requirements

- **Python 3.8+**
- **requests** library
- **types-requests** (for type hints)

## 🚀 Quick Start

1. **Clone or download this repository**
   ```bash
   git clone https://github.com/yourusername/goo.gl-scanner.git
   cd goo.gl-scanner
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start scanning** (auto-resumes from previous runs)
   ```bash
   python goo.gl.py --length 4 --no-404 --delay 1.0
   ```

## 📖 Usage

### Basic Commands

```bash
# Scan 4-character URLs, skip 404s, 1 second delay
python goo.gl.py --length 4 --no-404 --delay 1.0

# Test a specific URL
python goo.gl.py --test-url "https://goo.gl/test"

# Resume from specific position
python goo.gl.py --start-from "aabc" --length 4

# Debug mode with detailed logging
python goo.gl.py --debug --length 4 --no-404
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--length LENGTH` | URL suffix length (4, 5, 6, etc.) | 6 |
| `--output OUTPUT` | Output CSV filename | `goo.gl_urls.csv` |
| `--delay DELAY` | Delay between requests (seconds) | 1.0 |
| `--start-from SUFFIX` | Resume from specific URL suffix | Auto-detect |
| `--test-url URL` | Test a single specific URL | None |
| `--no-404` | Skip recording 404/not found results | False |
| `--debug` | Enable detailed debug logging | False |

### Output Format

Results are saved to CSV with the following columns:
- `short_url` - The goo.gl short URL
- `destination_url` - Where it redirects to
- `status` - Result type (see Status Codes below)
- `timestamp` - When it was processed

### Status Codes

| Status | Description |
|--------|-------------|
| `direct_redirect` | Direct HTTP redirect (no warning page) |
| `resolved_from_warning` | Extracted from Google's warning page |
| `link_not_found` | URL doesn't exist (404 or "Dynamic Link Not Found") |
| `404_error` | HTTP 404 response |
| `request_timeout` | Request timed out |
| `connection_failed` | Network connection error |

## 🔧 Advanced Usage

### Efficient Scanning Strategy

For maximum efficiency, start with shorter URLs:

```bash
# Start with 4-character URLs (14.7M combinations)
python goo.gl.py --length 4 --no-404 --delay 0.5

# Then move to 5-character URLs (916M combinations)
python goo.gl.py --length 5 --no-404 --delay 0.5 --output "goo_gl_5char.csv"

# Finally 6-character URLs (56.8B combinations) - will take very long!
python goo.gl.py --length 6 --no-404 --delay 0.5 --output "goo_gl_6char.csv"
```

### Auto-Resume Feature

The scanner automatically resumes from where it left off:

1. **First run**: Starts from `aaaa` (4-char) or `aaaaaa` (6-char)
2. **Subsequent runs**: Reads CSV file and continues from last processed URL
3. **Manual override**: Use `--start-from` to specify exact starting position


## 📁 Project Structure

```
goo.gl-scanner/
├── goo.gl.py                    # Main scanner script
├── requirements.txt             # Python dependencies  
├── README.md                    # This documentation
├── goo.gl_urls.csv             # Output file (created during scanning)
└── goo_gl_scanner.log          # Log file (created during scanning)
```

## 🛠️ Technical Details

### How It Works

1. **URL Generation**: Creates combinations using `[a-zA-Z0-9]`
2. **Request Handling**: Makes HTTP requests with proper headers and cookies
3. **Warning Page Detection**: Identifies Google's shutdown warning pages
4. **URL Extraction**: Uses regex patterns to extract real destination URLs
5. **Data Storage**: Saves results to CSV with timestamps

### Warning Page Bypass

The script handles Google's warning page that shows:
> "This link will no longer work in the near future. goo.gl links will no longer function after August 25th, 2025."

It automatically extracts the real destination URL without user interaction.

### Rate Limiting

- **Default delay**: 1 second between requests
- **Respectful**: Prevents overwhelming Google's servers
- **Configurable**: Adjust with `--delay` parameter
- **Recommendation**: Keep >= 0.5 seconds to avoid rate limiting

## 🚨 Important Notes
- **Time Sensitive**: Run before August 25th, 2025!

## 📜 License

This project is provided as-is for educational and archival purposes. Please use responsibly and in accordance with Google's Terms of Service.

**⚡ Quick Start Reminder:**
```bash
pip install requests types-requests
python goo.gl.py --length 4 --no-404 --delay 1.0
```

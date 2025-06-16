# Telegram-Bot-Utility

This project provides a collection of utility functions and tools to simplify the development of Telegram bots using Python.

## Key Features & Benefits

*   **Image/GIF Downloading:** Functionality to download images and GIFs from URLs.
*   **Clear Console:** Cross-platform console clearing for cleaner output.
*   **Colored Console Output:** Utilizes `colorama` for enhanced console messages.
*   **Modular Design:**  Easily integrate these utilities into your existing Telegram bot projects.

## Prerequisites & Dependencies

Before you begin, ensure you have the following installed:

*   **Python:** (Version 3.6 or higher recommended)  Download from [python.org](https://www.python.org/downloads/)
*   **Libraries:**  Install the required Python packages using pip:

    ```bash
    pip install requests colorama
    ```

## Installation & Setup Instructions

1.  **Clone the Repository:**

    ```bash
    git clone https://github.com/ZoniBoy00/Telegram-Bot-Utility.git
    cd Telegram-Bot-Utility
    ```

2.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```
    If `requirements.txt` is missing, use:
    ```bash
    pip install requests colorama
    ```

3.  **Place the file:** Place `telegram_bot_utility.py` in your Telegram bot project directory.

## Usage Examples & API Documentation

### Example: Importing and Using the Functions

```python
from telegram_bot_utility import download_image, clear_console
import time

clear_console() # Clear the console

image_url = "https://www.easygifanimator.net/images/samples/video-to-gif-sample.gif" #Example GIF
image_filename = download_image(image_url)

if image_filename:
    print(f"Image downloaded successfully as {image_filename}")
    #Your Code Here to send the image to telegram
else:
    print("Image download failed.")
```

### API Documentation

#### `clear_console()`

Clears the console screen.  Works on Windows, macOS, and Linux.

#### `download_image(image_url)`

Downloads an image or GIF from the provided URL.

*   **Parameters:**
    *   `image_url` (str): The URL of the image or GIF to download.
*   **Returns:**
    *   (str): The filename of the downloaded image if successful, or `None` if the download fails.

## Contributing Guidelines

We welcome contributions to this project! To contribute:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes.
4.  Write tests to ensure your changes work correctly.
5.  Submit a pull request with a clear description of your changes.

## License Information

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Acknowledgments

*   This project utilizes the `requests` library for HTTP requests.
*   `colorama` is used for colored console output.

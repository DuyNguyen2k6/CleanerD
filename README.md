# CleanerD

A Windows desktop utility to clean temporary files, manage system resources, and optimize performance. Built with Python and PyQt6, CleanerD offers a user-friendly interface for safe and efficient system cleanup.

---

## Features

* **Temporary File Cleanup**: Scan and remove files from `%TEMP%`, browser caches, and common junk locations.
* **Recycle Bin Mode**: Send deleted items to Recycle Bin for easy recovery.
* **Disk Usage Analysis**: Visualize disk space usage with interactive charts.
* **Registry Cleanup**: Identify and remove unused registry entries associated with uninstalled applications.
* **Browser History & Cookies**: Clear browsing history, cookies, and download lists for Chrome, Firefox, and Edge.
* **System Information**: View CPU, GPU, memory, and disk partition details in a dedicated tab.
* **Scheduled Cleanup**: Set up recurring cleanup tasks with custom schedules.
* **Dark & Light Themes**: Toggle between themes for comfortable use.

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/DuyNguyen2k6/CleanerD.git
   ```
2. Navigate to the project folder:

   ```bash
   cd CleanerD
   ```
3. (Optional) Create a virtual environment and activate:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
5. Run the application:

   ```bash
   python cleaner_d.py
   ```
6. To build an executable:

   ```bash
   pyinstaller --onefile --windowed --icon=app_icon.ico cleaner_d.py
   ```

---

## Usage

1. **Launch CleanerD**: Open the application window.
2. **Select Cleanup Options**: Choose categories (Temp Files, Registry, Browser Data).
3. **Scan**: Click **Scan** to analyze selected items.
4. **Review & Clean**: Review results and click **Clean** to remove selected items.
5. **Disk Analysis**: Switch to the **Disk Usage** tab for visual reports.
6. **Schedule Tasks**: Use the **Schedule** tab to set automatic cleanups.
7. **Cancel/Abort**: Cancel ongoing scans or cleanups at any time.

---

## File Structure

* `cleaner_d.py`       — Main application script.
* `ui_cleaner.py`      — Auto-generated PyQt6 UI definitions.
* `resources/`         — Icons, images, and stylesheet files.
* `requirements.txt`   — Python dependencies.
* `app_icon.ico`       — Application icon.
* `LICENSE`            — License file.
* `README.md`          — This documentation.

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a branch for your feature:

   ```bash
   git checkout -b feature/my-feature
   ```
3. Commit your changes:

   ```bash
   git commit -m "Add feature: description"
   ```
4. Push to your branch:

   ```bash
   git push origin feature/my-feature
   ```
5. Open a pull request describing your changes.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

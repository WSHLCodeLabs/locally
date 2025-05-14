# Locally - Web Server Manager

## 🌐 Overview

Locally is a Python application for managing and hosting multiple local websites simultaneously. It provides a user-friendly GUI built with customtkinter that allows developers and designers to quickly spin up local web servers for testing and development purposes.

## ✨ Features

- **Multiple Site Management**: Host and manage multiple websites concurrently
- **Automatic Port Management**: Automatic assignment of available ports
- **Import Flexibility**: Import websites from directories or ZIP files
- **One-Click Controls**: Start, stop, and open websites with single-click controls
- **Visual Status Indicators**: Clear visual indicators of site running status

## 🚀 Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Install from Source

1. Clone this repository:
   ```
   git clone https://github.com/WSHLCodeLabs/locally.git
   cd locally
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python locally.py
   ```

## 💻 Usage

### Adding a Website

1. Click the "Add Folder" button to select a directory containing your website files
   - OR -
2. Click the "Add ZIP" button to import a zipped website (it will be extracted automatically)
3. Enter a name for your site when prompted

### Managing Sites

- Sites are listed in the left panel with their running status
- Click on a site to view its details
- Use the quick "Start/Stop" buttons to toggle site status
- Click "Open in Browser" to view the site in your default web browser

### Settings

Locally offers several customization options:

- **Server Settings**: Configure default ports, HTTP/HTTPS options, and SSL certificates
- **UI Settings**: Choose between light and dark mode, adjust interface scaling
- **Startup Settings**: Configure auto-start behavior and session persistence
- **File Locations**: Set default locations for extracted sites

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI library for tkinter.
- Python's http.server and socketserver modules for the core functionality

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/wshlcodelabs">WSHLCodeLabs</a>
</p>

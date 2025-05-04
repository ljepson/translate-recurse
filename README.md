# Chinese to English Code Translator

A Python utility for automatically translating Chinese codebases to English.

## Overview

The `translate-recurse.py` script automates the translation of source code and documentation files from Chinese to English. It recursively processes all files in a directory structure, identifies content containing Chinese characters, and translates them to English using the Google Translate API.

## Features

- **Recursive Directory Traversal**: Automatically processes all files in the project directory and its subdirectories
- **Selective Translation**: Only translates files that contain Chinese characters
- **In-place Replacement**: Modifies files directly, preserving the original file structure
- **Binary File Detection**: Skips binary files and other non-text content
- **Large File Handling**: Chunks large files to avoid API limitations
- **Error Handling**: Continues operation even when individual translations fail
- **Rate Limiting**: Implements delays between API calls to prevent rate limiting issues

## How It Works

1. The script walks through all directories recursively (excluding `.git` directories)
2. For each file, it:
   - Checks if the file is a binary file (based on extension)
   - Attempts to read the file content as UTF-8 text
   - Detects if the content contains Chinese characters
   - For files with Chinese content:
     - Translates the content (in chunks if necessary)
     - Writes the translated content back to the original file
   - Skips files without Chinese content

## Technical Implementation

- Uses the `googletrans` Python library (version >=4.0.0) for translation
- Implements Unicode range checking to detect Chinese characters (`\u4e00` to `\u9fff`)
- Chunks text larger than 5000 characters to handle API limitations
- Implements 1-second delays between chunk translations to avoid rate limiting
- Provides detailed logging of translation progress and errors

## Usage

1. Install required dependencies:

   ```sh
   pip install googletrans==4.0.0-rc1
   ```

2. Place `translate-recurse.py` in the root directory of your project

3. Run the script:

   ```sh
   python translate-recurse.py
   ```

4. Monitor the output to see which files are being translated

## Limitations

- Translation quality depends on Google Translate's capabilities
- Code comments and string literals are translated, which may affect functionality
- Very large files may take significant time to process due to chunking and rate limiting
- Some specialized technical terms may not translate accurately

## Use Cases

- Making Chinese codebases accessible to English-speaking developers
- Facilitating code review of multilingual projects
- Assisting in the internationalization of software projects
- Enabling collaboration between teams with different language backgrounds

from googletrans import Translator
import os
import time

def is_chinese_text(text):
    """Check if the text contains Chinese characters"""
    for char in text:
        # Check for Chinese Unicode ranges
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def translate_text(text, translator):
    """Translate text with chunking for large texts"""
    # If text is too long, split it into chunks
    if len(text) > 5000:
        chunks = []
        # Split text into chunks of 5000 characters
        for i in range(0, len(text), 5000):
            chunk = text[i:i+5000]
            try:
                translated_chunk = translator.translate(chunk, src='zh-CN', dest='en').text
                chunks.append(translated_chunk)
                # Add delay to avoid rate limiting
                time.sleep(1)
            except Exception as e:
                print(f"Error translating chunk: {e}")
                # Return the original chunk if translation fails
                chunks.append(chunk)
        return ''.join(chunks)
    else:
        try:
            return translator.translate(text, src='zh-CN', dest='en').text
        except Exception as e:
            print(f"Error translating text: {e}")
            return text

def translate_file(file_path, translator):
    """Translate a file from Chinese to English and replace it in-place"""
    try:
        # Skip non-text files (binary files)
        if os.path.splitext(file_path)[1].lower() in ['.pyc', '.pyo', '.so', '.dll', '.exe', '.bin']:
            return False
            
        # Read the content of the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Skip files that can't be decoded as text
            return False
            
        # Check if file contains Chinese text
        if not is_chinese_text(content):
            return False
            
        # Translate the content
        translated_content = translate_text(content, translator)
        
        # Write the translated text back to the original file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)
            
        return True
        
    except Exception as e:
        print(f"Error translating {file_path}: {e}")
        return False

def main():
    # Create a translator object
    translator = Translator()
    
    # Count of translated files
    translated_count = 0
    
    # Walk through all directories recursively
    for root, dirs, files in os.walk('.'):
        # Skip .git directory
        if '.git' in dirs:
            dirs.remove('.git')
            
        for file in files:
            file_path = os.path.join(root, file)
            
            # Skip the script itself
            if file_path.endswith('translate.py'):
                continue
                
            print(f"Checking: {file_path}")
            
            # Translate the file if it contains Chinese text
            if translate_file(file_path, translator):
                translated_count += 1
                print(f"Translated: {file_path}")
    
    print(f"Translation complete! {translated_count} files translated.")

if __name__ == "__main__":
    main()
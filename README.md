# kaggle_clean

A fast, lightweight CLI tool to automatically rename and sanitize files so they comply with **Kaggle's strict upload rules**.

When uploading files (datasets, notebooks, archives) to Kaggle, names containing spaces, parentheses, brackets, colons, accents, or special characters cause errors such as *"File name is not appropriate"* or validation failures. `kaggle_clean` sanitizes these names into clean, POSIX-compliant file names.

---

## Features

- **POSIX & Kaggle Compliant**: Replaces forbidden characters (spaces, `()`, `[]`, `:`, `,`, quotes, math symbols, etc.) with safe underscores (`_`).
- **Normalized File Extensions**: Strips internal dots from stems (e.g. `file.v1.pdf` -> `file_v1.pdf`) to avoid Kaggle mime-type bugs, while preserving valid compound extensions like `.tar.gz`.
- **Accented Character Stripping**: Converts Unicode characters with diacritics into ASCII (e.g. `résumé.pdf` -> `resume.pdf`).
- **Collision Safe**: If a target file already exists, appends incremental suffixes (`_1`, `_2`) instead of overwriting.
- **Dry-Run Mode (`-n`)**: Preview renames before executing them.
- **Batch & Recursive**: Clean the current directory (`kaggle_clean .`), specific files, or nested directories recursively (`-r`).
- **Zero Dependencies**: Pure standard library Python.

---

## Installation

```bash
# Install in editable mode for local development:
pip install -e . --break-system-packages
```

Once installed, both `kaggle_clean` and the alias `kagle_clean` are available from any terminal path.

---

## Usage

### 1. Clean a Single File
```bash
kaggle_clean "My Book [Lecture 1] (Final).pdf"
# Output: 'My Book [Lecture 1] (Final).pdf' -> 'My_Book_Lecture_1_Final.pdf'
```

### 2. Clean All Files in Current Directory
```bash
kaggle_clean .
```

### 3. Dry-Run (Preview Changes)
```bash
kaggle_clean . --dry-run
```

### 4. Filter by Specific File Types
```bash
kaggle_clean . --ext pdf,txt,md,mp3,opus,wav
```

### 5. Recursive Directory Cleaning
```bash
kaggle_clean ./my_dataset -r
```

### 6. Convert Filenames to Lowercase
```bash
kaggle_clean . --lower
```

---

## Examples

| Original Name | Kaggle-Cleaned Name |
|---|---|
| `My Document [Lecture 1] (Final).pdf` | `My_Document_Lecture_1_Final.pdf` |
| `Chapter 1: Deep Learning & AI.txt` | `Chapter_1_Deep_Learning_AI.txt` |
| `README (v1.2).md` | `README_v1_2.md` |
| `Track 01 - Speech (Audio).mp3` | `Track_01_Speech_Audio.mp3` |
| `podcast sample [raw].opus` | `podcast_sample_raw.opus` |
| `voice (take 2).wav` | `voice_take_2.wav` |
| `100% Guaranteed $Profit?.pdf` | `100_Guaranteed_Profit.pdf` |
| `résumé 2024.txt` | `resume_2024.txt` |

---

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```

# Loquendon't

OpenSource TTS script that ONLY WORKS ON WINDOWS

Hi there! This is a TTS script coded in Python, designed to combine offline SAPI5 voices with online Edge-TTS voices into a single audio file.

## How to run it

You will need Python 3.12 or newer to run the script.
You will need the following libraries: `pyttsx3`, `edge-tts`, and `pydub`. These can be installed with the following command:

```bash
pip install pyttsx3 edge-tts pydub
```

You will also need to have **FFMPEG** installed and added to your system PATH for audio merging to work.

### Running the Script

1. Download the repo and save it to a folder.
2. Open your terminal and `cd` into that folder.
3. Run the script: `python s.py`.

## New Features

* **Persistent Log History**: Tracks FATAL, CRITICAL, and WARNING errors in a buffer that persists even after screen clears.
* **Progress Tracker**: A visual progress bar that tracks the synthesis of both online and local voice segments in real-time.
* **Configuration Menu**: An in-app menu to adjust punctuation pause timings (e.g., how long the program waits for a comma vs. a period).
* **Error Handling**: If an incorrect menu option is selected, the screen clears, a system bell sounds, and the program displays the unrecognized input before allowing you to try again.

## Input File Structure

The program processes text files using simple commands.

* **/voice=VoiceId**: Switches the current voice. `VoiceId` can be found by selecting option `1` in the main menu.
* **/pause=Milliseconds**: Inserts a silent pause of a specific length (e.g., `/pause=1000` for 1 second).

## Usage

1. **List Voices**: Use option `1` to see all available local (pyttsx3) and online (edge-tts) voices.
2. **Process File**: Use option `2`. Provide the full path to your text file and the desired path for the output `.wav` or `.mp3` file.
3. **Settings**: Use option `3` to customize how long the program pauses for specific punctuation marks or to clear your log history.

## Warning

This program is provided as-is and may not be actively maintained.

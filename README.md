# Tech Pipeline

Survey CSV and interview transcript analysis tool with AI summaries and PDF reports.

---

## Setup (one time)

**1. Install Python 3.10+** from [python.org](https://www.python.org/downloads/)
> Windows: check **"Add Python to PATH"** during install.

**2. Install the app**
```
pip install git+https://github.com/goelb/Tech-Pipeline.git
```

**3. Create a `.env` file** in any folder with your Groq API key:
```
GROQ_API_KEY=your_key_here
```
Get a free key at [console.groq.com](https://console.groq.com).

---

## Running

Navigate to your `.env` folder and run:
```
tech-pipeline
```
Browser opens automatically. Enter the password when prompted (ask the team lead).

---

## Updating

```
pip install --upgrade git+https://github.com/goelb/Tech-Pipeline.git
```

---

## Transcript format

Transcripts must be `.txt` files with speaker labels:
```
Interviewer: Your question here.
Interviewee: Their response here.
```
Generic labels like `Speaker 1:` / `Speaker 2:` also work.

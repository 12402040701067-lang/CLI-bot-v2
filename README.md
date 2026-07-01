# CLI Bot V2

This directory contains the complete CLI application deliverables. It integrates a Node.js CLI controller with a Python backend to communicate across three AI providers (OpenAI, Gemini, and Anthropic).

---

## ✨ Key Features

* **Advanced Model Configurations & Cost Calculation**: Fully nested and customized pricing for:
  * **OpenAI**: `gpt-4o-mini`, `gpt-4o`
  * **Google Gemini**: `gemini-1.5-flash`, `gemini-1.5-pro`
  * **Anthropic**: `claude-3-haiku-20240307`, `claude-3-5-sonnet-20241022`
* **Dynamic Generation Tuning & Slash Commands**: Adds live parameters via runtime CLI console slash commands:
  * `/temperature <val>` (tunes temperature from `0.0` to `2.0`)
  * `/max_tokens <val>` (sets output limits)
  * `--model <name>` (startup flag to specify a custom model)
* **Robust CLI Execution (Windows Unicode Crash Fix)**: Escapes unicode data through JSON objects from Python backend to Node.js, resolving encoding crashes on Windows terminals.
* **Context-Aware Persona Greetings**: Automatically remembers your name from earlier turns in the conversation history and formats custom greeting responses inside:
  * **Standard**: *"Hello Himalya! Nice to meet you..."*
  * **Pirate (Captain Jack Sparrow)**: *"Ahoy Himalya! Welcome aboard my ship..."*
  * **Wizard (Dumbledore)**: *"Greetings, Himalya! What magic brings you to my tower today?"*
* **Polite Greeting Recognition**: Recognizes phrases like *"nice to meet you"* and responds with custom persona templates utilizing your extracted name.
* **Code Syntax Highlighting in CLI**: Formats markdown code blocks (` ```python `) inside the CLI using ANSI color escape sequences:
  * **Keywords** -> Cyan
  * **Strings** -> Yellow/Orange
  * **Numbers** -> Magenta
  * **Comments / delimiters** -> Dim Gray

---

## 📂 Directory Contents

* **`chatbot.js`**: Node.js coordinator script that initializes the terminal user interface, reads prompt inputs, and spawns the Python backend.
* **`chatbot.py`**: Python backend script that handles API calls, translates alternating chat histories for each SDK schema, estimates token usage, and calculates real-time conversation costs.
* **`package.json` / `package-lock.json`**: Node.js project configurations and dependencies.
* **`.env.example`**: Example template file for configuring API keys.

---

## 🛠️ Setup Instructions

### 1. Install Dependencies

Install Node.js packages:
```bash
npm install
```

Install Python SDK packages:
```bash
pip install openai google-generativeai anthropic python-dotenv
```

### 2. Configure Environment Keys

Copy the example environment configuration:
```bash
copy .env.example .env
```
Open `.env` in a text editor and add your API keys:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

*Note: If keys are missing, the CLI automatically falls back to an interactive **Mock/Simulation mode** so that the application remains functional and still reports estimated tokens and costs.*

---

## 🚀 Running the Chatbot CLI

Start the CLI using Node and specify your desired provider via the `--provider` flag:

```bash
# To run with Google Gemini (Flash)
node chatbot.js --provider gemini

# To run with OpenAI (GPT-4o-mini)
node chatbot.js --provider openai

# To run with Anthropic (Claude 3 Haiku)
node chatbot.js --provider anthropic
```

To close the session at any time, type `exit`.

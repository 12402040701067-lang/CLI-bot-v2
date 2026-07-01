import { spawn } from "child_process";
import readline from "readline";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Parse command line arguments
let provider = "anthropic";
let model = "";
const args = process.argv.slice(2);

const providerIndex = args.indexOf("--provider");
if (providerIndex !== -1 && providerIndex + 1 < args.length) {
    provider = args[providerIndex + 1].toLowerCase();
}

const modelIndex = args.indexOf("--model");
if (modelIndex !== -1 && modelIndex + 1 < args.length) {
    model = args[modelIndex + 1];
}

const validProviders = ["anthropic", "openai", "gemini"];
if (!validProviders.includes(provider)) {
    console.error(`Error: Invalid provider '${provider}'. Valid options are: ${validProviders.join(", ")}`);
    process.exit(1);
}

// Spawn the Python process with the --provider and optional --model flags
const spawnArgs = [path.join(__dirname, "chatbot.py"), "--provider", provider];
if (model) {
    spawnArgs.push("--model", model);
}
const pythonProcess = spawn("python", spawnArgs);

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

const providerNames = {
    anthropic: "Anthropic Claude",
    openai: "OpenAI GPT",
    gemini: "Google Gemini"
};

const THEMES = {
    classic: {
        prompt: "\x1b[1;34mYou:\x1b[0m ",        // Bold Blue
        botHeader: "\x1b[1;32mBot:\x1b[0m ",     // Bold Green
        text: "\x1b[0m",                         // Default Reset
        stats: "\x1b[90m",                       // Gray
        command: "\x1b[36m"                      // Cyan
    },
    matrix: {
        prompt: "\x1b[1;32mYou:\x1b[0m ",        // Bold Green
        botHeader: "\x1b[1;32mBot:\x1b[0m ",     // Bold Green
        text: "\x1b[32m",                        // Green
        stats: "\x1b[32m",                       // Green
        command: "\x1b[1;32m"                    // Bold Green
    },
    cyberpunk: {
        prompt: "\x1b[1;35mYou:\x1b[0m ",        // Bold Pink/Magenta
        botHeader: "\x1b[1;36mBot:\x1b[0m ",     // Bold Cyan
        text: "\x1b[97m",                        // Bright White
        stats: "\x1b[93m",                       // Bright Yellow
        command: "\x1b[1;35m"                    // Bold Pink/Magenta
    }
};

let currentTheme = "classic";

console.log(`🤖 Multi-Provider Chatbot [Active: ${providerNames[provider]}]\nType 'exit' to quit. Available commands:\n` +
            `  /provider <name> [model]  Switch AI provider and select model\n` +
            `  /system [instruction]     Set custom system instructions\n` +
            `  /temperature <val>        Set generation temperature (0.0 to 2.0)\n` +
            `  /max_tokens <val>         Set max response tokens\n` +
            `  /stats                    View cumulative session stats\n` +
            `  /theme <name>             Switch themes (classic, matrix, cyberpunk)\n` +
            `  /export                   Export chat history to Markdown\n`);

pythonProcess.on("close", (code) => {
    if (code !== 0 && code !== null) {
        console.log(`\nPython backend exited with code ${code}`);
    }
    process.exit();
});

let stdoutData = "";
let pendingCallback = null;

pythonProcess.stdout.on("data", (data) => {
    stdoutData += data.toString();
    if (stdoutData.includes("\n")) {
        const lines = stdoutData.split("\n");
        stdoutData = lines.pop();
        for (const line of lines) {
            if (line.trim() && pendingCallback) {
                try {
                    const response = JSON.parse(line);
                    pendingCallback(response);
                } catch (e) {
                    console.error("Error parsing Python output:", line);
                }
            }
        }
    }
});

pythonProcess.stderr.on("data", (data) => {
    console.error(`Python Error: ${data}`);
});

function highlightCode(code, lang) {
    if (!lang) return code;
    lang = lang.toLowerCase();
    
    if (lang === 'python' || lang === 'py' || lang === 'javascript' || lang === 'js' || lang === 'json') {
        const lines = code.split('\n');
        const highlightedLines = lines.map(line => {
            if (line.trim().startsWith('#') || line.trim().startsWith('//')) {
                return `\x1b[90m${line}\x1b[0m`; // Gray for comments
            }
            
            const strings = [];
            // Match double-quoted and single-quoted strings
            const stringPattern = /(["'])(?:(?=(\\?))\2.)*?\1/g;
            let tempLine = line.replace(stringPattern, (match) => {
                strings.push(`\x1b[33m${match}\x1b[0m`); // Yellow/Orange for strings
                return `__STR_PLACEHOLDER_${strings.length - 1}__`;
            });
            
            // Highlight keywords
            const keywords = /\b(def|class|return|import|from|as|if|else|elif|for|in|while|try|except|with|print|const|let|var|function|async|await|default)\b/g;
            tempLine = tempLine.replace(keywords, `\x1b[36m$1\x1b[0m`); // Cyan for keywords
            
            // Highlight numbers
            const numbers = /\b(\d+)\b/g;
            tempLine = tempLine.replace(numbers, `\x1b[35m$1\x1b[0m`); // Magenta for numbers
            
            // Restore strings
            tempLine = tempLine.replace(/__STR_PLACEHOLDER_(\d+)__/g, (match, idx) => {
                return strings[parseInt(idx)];
            });
            
            return tempLine;
        });
        return highlightedLines.join('\n');
    }
    return code;
}

function formatMessage(message, themeName) {
    const themeText = THEMES[themeName].text || "";
    
    // Split the message by code blocks
    const parts = message.split(/(```[\s\S]*?```)/g);
    
    const formattedParts = parts.map(part => {
        if (part.startsWith("```") && part.endsWith("```")) {
            // It's a code block
            const match = part.match(/^```(\w+)?\n([\s\S]*?)\n?```$/);
            if (match) {
                const lang = match[1] || "";
                const code = match[2] || "";
                const highlighted = highlightCode(code, lang);
                const header = `\x1b[90m\`\`\`${lang}\x1b[0m`;
                const footer = `\x1b[90m\`\`\`\x1b[0m`;
                return `${header}\n${highlighted}\n${footer}`;
            }
            return part; // Fallback
        } else {
            // Normal text: apply theme styling
            return `${themeText}${part}\x1b[0m`;
        }
    });
    
    return formattedParts.join("");
}

function promptUser() {
    rl.question(THEMES[currentTheme].prompt, (msg) => {
        if (msg.trim().toLowerCase() === "exit") {
            console.log("Bye 👋");
            pythonProcess.kill();
            rl.close();
            return;
        }
        
        let botResponseBuffer = "";
        pendingCallback = (response) => {
            if (response.status === "chunk") {
                botResponseBuffer += response.text;
            } else if (response.status === "done") {
                process.stdout.write("\n" + THEMES[currentTheme].botHeader);
                process.stdout.write(formatMessage(botResponseBuffer, currentTheme));
                process.stdout.write("\x1b[0m"); // Reset text style
                console.log(`\n\n${THEMES[currentTheme].stats}${response.display_stats}\x1b[0m\n`);
                pendingCallback = null;
                promptUser();
            } else if (response.status === "command_success") {
                if (response.theme) {
                    currentTheme = response.theme;
                }
                console.log(`\n${THEMES[currentTheme].command}${response.message}\x1b[0m\n`);
                pendingCallback = null;
                promptUser();
            } else if (response.status === "command_error") {
                console.log(`\n\x1b[1;31m${response.message}\x1b[0m\n`);
                pendingCallback = null;
                promptUser();
            } else if (response.status === "error") {
                console.log(`\n\x1b[1;31mError: ${response.message}\x1b[0m\n`);
                pendingCallback = null;
                promptUser();
            }
        };

        pythonProcess.stdin.write(msg.trim() + "\n");
    });
}

promptUser();

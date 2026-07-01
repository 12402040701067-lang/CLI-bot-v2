import sys
import os
import json
import argparse
import warnings
import time
import random
from dotenv import load_dotenv

# Suppress warnings from python packages (like deprecated google.generativeai)
warnings.filterwarnings("ignore")

# Try importing the SDKs
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Load variables from .env
load_dotenv()

def execute_with_retry(api_call_fn, max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return api_call_fn()
        except Exception as e:
            err_str = str(e)
            class_name = e.__class__.__name__
            
            # Check if retryable
            is_retryable = False
            
            # Rate limits
            if "RateLimit" in class_name or "ResourceExhausted" in err_str or "429" in err_str:
                is_retryable = True
            # Connection/Timeout errors
            elif "APIConnection" in class_name or "ConnectionError" in class_name or "Timeout" in class_name or "TimeoutError" in class_name:
                is_retryable = True
            # Server errors (5xx)
            elif "InternalServer" in class_name or "500" in err_str or "502" in err_str or "503" in err_str or "504" in err_str or "ServiceUnavailable" in err_str or "Bad Gateway" in err_str or "Unavailable" in class_name:
                is_retryable = True
                
            # Non-retryable billing / authorization errors
            if "credit balance" in err_str or "billing" in err_str or "401" in err_str or "API key" in err_str or "Unauthorized" in class_name or "Invalid API Key" in err_str:
                is_retryable = False
                
            if not is_retryable or attempt == max_retries - 1:
                raise e
                
            sleep_time = delay + random.uniform(0, 0.5)
            sys.stderr.write(f"⚠️ [API Transient Error] {class_name}: {err_str}. Retrying in {sleep_time:.2f}s (Attempt {attempt + 1}/{max_retries})...\n")
            sys.stderr.flush()
            
            time.sleep(sleep_time)
            delay *= backoff_factor
MODEL_DETAILS = {
    "openai": {
        "gpt-4o-mini": {
            "model_name": "gpt-4o-mini",
            "display_name": "GPT-4o-mini",
            "input_price_per_m": 0.15,
            "output_price_per_m": 0.60
        },
        "gpt-4o": {
            "model_name": "gpt-4o",
            "display_name": "GPT-4o",
            "input_price_per_m": 2.50,
            "output_price_per_m": 10.00
        }
    },
    "gemini": {
        "gemini-1.5-flash": {
            "model_name": "gemini-1.5-flash",
            "display_name": "Gemini 1.5 Flash",
            "input_price_per_m": 0.075,
            "output_price_per_m": 0.30
        },
        "gemini-1.5-pro": {
            "model_name": "gemini-1.5-pro",
            "display_name": "Gemini 1.5 Pro",
            "input_price_per_m": 1.25,
            "output_price_per_m": 5.00
        }
    },
    "anthropic": {
        "claude-3-haiku-20240307": {
            "model_name": "claude-3-haiku-20240307",
            "display_name": "Claude 3 Haiku",
            "input_price_per_m": 0.25,
            "output_price_per_m": 1.25
        },
        "claude-3-5-sonnet-20241022": {
            "model_name": "claude-3-5-sonnet-20241022",
            "display_name": "Claude 3.5 Sonnet",
            "input_price_per_m": 3.00,
            "output_price_per_m": 15.00
        }
    }
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "anthropic": "claude-3-haiku-20240307"
}

def is_valid_key(key):
    return key and len(key.strip()) > 0 and not key.strip().startswith("your_")

def estimate_tokens(text):
    # Standard heuristic: 1 token ~= 4 chars, or 1.3 tokens per word
    if not text:
        return 0
    return int(max(4, len(text.split()) * 1.3))

def find_user_name_in_history(history):
    import re
    if not history:
        return None
    for turn in reversed(history):
        if turn.get("role") == "user":
            content_lower = turn.get("content", "").lower()
            name_match = re.search(r"\b(?:i\s+am|my\s+name\s+is|call\s+me)\s+([a-zA-Z0-9_\-\s]+)", content_lower)
            if name_match:
                extracted = name_match.group(1).strip()
                if extracted and len(extracted) < 30 and extracted.lower() not in ["a boy", "a girl", "a developer", "a user", "a bot", "testing", "happy", "sad", "here", "ready", "fine", "ok", "okay"]:
                    return extracted.title()
    return None

def get_mock_response(provider, model, prompt, history, system_prompt=None):
    import re
    prompt_lower = prompt.lower()
    info = MODEL_DETAILS[provider][model]
    model_name = info["display_name"]
    
    def has_word(word):
        return re.search(r'\b' + re.escape(word) + r'\b', prompt_lower) is not None
        
    is_pirate = False
    is_wizard = False
    if system_prompt:
        sys_lower = system_prompt.lower()
        if "pirate" in sys_lower or "jack" in sys_lower or "sparrow" in sys_lower:
            is_pirate = True
        elif "wizard" in sys_lower or "dumbledore" in sys_lower:
            is_wizard = True

    # Try to extract user name introduction (e.g., "I am Himalya", "My name is Himalya", "Call me Himalya")
    name_match = re.search(r"\b(?:i\s+am|my\s+name\s+is|call\s+me)\s+([a-zA-Z0-9_\-\s]+)", prompt_lower)
    user_name = None
    if name_match:
        extracted = name_match.group(1).strip()
        # Exclude common adjectives or nouns to prevent false positives
        if extracted and len(extracted) < 30 and extracted.lower() not in ["a boy", "a girl", "a developer", "a user", "a bot", "testing", "happy", "sad", "here", "ready", "fine", "ok", "okay"]:
            user_name = extracted.title()

    # Check for nice-to-meet-you type greetings
    has_nice_to_meet_you = (
        "nice to meet" in prompt_lower or 
        "pleasure to meet" in prompt_lower or 
        "glad to meet" in prompt_lower or 
        "good to meet" in prompt_lower or
        "nice meeting you" in prompt_lower or
        "pleasure meeting you" in prompt_lower
    )

    # Custom answers based on keywords and extracted name
    if is_pirate:
        if user_name:
            reply = f"Ahoy {user_name}! I am Captain Jack Sparrow, a simulated response from {model_name}. Welcome aboard my ship, matey!"
        elif has_nice_to_meet_you:
            hist_name = find_user_name_in_history(history)
            if hist_name:
                reply = f"Ahoy, {hist_name}! The pleasure be all mine, matey! May the winds always blow in our sails!"
            else:
                reply = "Ahoy! The pleasure be all mine, matey! May the winds always blow in our sails!"
        elif has_word("hello") or has_word("hi"):
            reply = f"Ahoy matey! I am Captain Jack Sparrow, a simulated response from {model_name}. What wind blows ye to my deck today?"
        elif has_word("joke") or has_word("jokes"):
            reply = "Ahoy! Why don't scientists trust atoms, ye ask? Because they make up every plank on the ship! Arrr!"
        elif has_word("weather") or has_word("wheather"):
            reply = "Arrr, there be no weather glass on this deck, but in my simulated seas it be clear winds and fair sailing!"
        elif has_word("name"):
            reply = f"My name is Captain Jack Sparrow, running on the simulated {model_name} galleon."
        else:
            reply = f"Ahoy! I hear ye, but Captain Jack Sparrow can only mock responses from {model_name}. Set yer sails!"
    elif is_wizard:
        if user_name:
            reply = f"Greetings, {user_name}! I am Dumbledore, a simulated spirit of {model_name}. What magic brings you to my tower today?"
        elif has_nice_to_meet_you:
            hist_name = find_user_name_in_history(history)
            if hist_name:
                reply = f"The pleasure is entirely mine, {hist_name}. It is a wondrous thing to cross paths with another curious mind in this vast universe."
            else:
                reply = "The pleasure is entirely mine. It is a wondrous thing to cross paths with another curious mind in this vast universe."
        elif has_word("hello") or has_word("hi"):
            reply = f"Greetings, traveler! I am Dumbledore, a simulated spirit of {model_name}. What magic brings you to my tower?"
        elif has_word("joke") or has_word("jokes"):
            reply = "Hark! Why don't alchemists trust atoms? By my staff, because they compose all matter in the cosmos!"
        elif has_word("weather") or has_word("wheather"):
            reply = "My scrying orb detects no storms, but in this simulated realm, the arcane winds blow warm and clear."
        elif has_word("name"):
            reply = f"I am Dumbledore, running on the simulated towers of {model_name}."
        else:
            reply = f"Hark! I hear your whisper, but Dumbledore's wizardry is limited to mock responses from {model_name}."
    else:
        if user_name:
            reply = f"Hello {user_name}! Nice to meet you. I am a simulated response from {model_name}. How can I assist you today?"
        elif has_nice_to_meet_you:
            hist_name = find_user_name_in_history(history)
            if hist_name:
                reply = f"Nice to meet you too, {hist_name}! I am glad to be chatting with you today. How can I help you?"
            else:
                reply = "Nice to meet you too! I am glad to be chatting with you today. How can I help you?"
        elif has_word("hello") or has_word("hi"):
            reply = f"Hello! I am a simulated response from {model_name}. How can I assist you today?"
        elif has_word("joke") or has_word("jokes"):
            reply = "Why don't scientists trust atoms? Because they make up everything!"
        elif has_word("weather") or has_word("wheather"):
            reply = "I don't have real-time access to weather sensors, but in my simulated environment, it's always a perfect 72°F (22°C) and sunny!"
        elif has_word("name"):
            reply = f"My name is Chatbot, running on the simulated {model_name} backend."
        elif has_word("code") or has_word("python") or has_word("javascript"):
            reply = f"Here is a quick Python example:\n```python\n# Simulated Hello World\nprint('Hello from {model_name}')\n```"
        elif "function calling" in prompt_lower:
            reply = ("OpenAI Function Calling allows models to describe tools/functions as a JSON schema, "
                     "and ask the client to execute them with specific arguments when needed. This helps connect "
                     "LLMs with external databases or APIs.")
        elif has_word("multimodal") or has_word("role") or has_word("roles"):
            reply = (f"Gemini models like {model_name} are natively multimodal (supporting text, image, audio, video). "
                     "A key role difference is that Gemini's Chat API requires strictly alternating 'user' and 'model' "
                     "roles, whereas OpenAI and Anthropic use 'user' and 'assistant' roles.")
        else:
            reply = f"Thank you for your message! This is a simulated response from {model_name}. As a mock backend, I am here to help you test the multi-provider CLI integration."
        
    return reply

def main():
    import sys
    if sys.platform == "win32":
        os.system("")

    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="anthropic", choices=["openai", "gemini", "anthropic"])
    parser.add_argument("--model", default=None, help="The model to start with")
    parser.add_argument("--api", action="store_true", help="Run in stateless API mode, accepting JSON on stdin")
    args = parser.parse_args()
    provider = args.provider

    # Initialize client flags and global state variables
    use_mock = False
    client = None
    system_prompt = None
    temperature = 0.7
    max_tokens = 300
    current_model = args.model if args.model and args.model in MODEL_DETAILS[provider] else DEFAULT_MODELS[provider]
    
    model_name = ""
    display_name = ""
    input_price = 0.0
    output_price = 0.0
    
    # Cumulative session stats
    session_input_tokens = 0
    session_output_tokens = 0
    session_cost = 0.0

    # Retrieve environment keys
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def init_provider_client(target_provider):
        nonlocal client, use_mock
        client = None
        use_mock = False
        
        if target_provider == "anthropic":
            if HAS_ANTHROPIC and is_valid_key(anthropic_key):
                try:
                    client = Anthropic(api_key=anthropic_key)
                except Exception:
                    use_mock = True
            else:
                use_mock = True
        elif target_provider == "openai":
            if HAS_OPENAI and is_valid_key(openai_key):
                try:
                    client = OpenAI(api_key=openai_key)
                except Exception:
                    use_mock = True
            else:
                use_mock = True
        elif target_provider == "gemini":
            if HAS_GEMINI and is_valid_key(gemini_key):
                try:
                    genai.configure(api_key=gemini_key)
                except Exception:
                    use_mock = True
            else:
                use_mock = True

    # Setup provider mapping properties
    def update_provider_details(target_provider, target_model=None):
        nonlocal provider, model_name, display_name, input_price, output_price, current_model
        provider = target_provider
        if not target_model or target_model not in MODEL_DETAILS[provider]:
            target_model = DEFAULT_MODELS[provider]
        current_model = target_model
        info = MODEL_DETAILS[provider][current_model]
        model_name = info["model_name"]
        display_name = info["display_name"]
        input_price = info["input_price_per_m"]
        output_price = info["output_price_per_m"]

    # Initial provider client setup
    init_provider_client(provider)
    update_provider_details(provider, current_model)

    history = []

    def run_mock_streaming(msg, fallback_warning=None):
        nonlocal use_mock, session_input_tokens, session_output_tokens, session_cost, current_model
        if fallback_warning:
            print(json.dumps({"status": "chunk", "text": fallback_warning}), flush=True)
            
        reply = get_mock_response(provider, current_model, msg, history, system_prompt=system_prompt)
        
        # Estimate token counts
        input_tokens = estimate_tokens(msg)
        for turn in history[:-1]:
            input_tokens += estimate_tokens(turn.get("content", ""))
        if system_prompt:
            input_tokens += estimate_tokens(system_prompt)
        output_tokens = estimate_tokens(reply)
        
        cost = ((input_tokens / 1_000_000) * input_price) + ((output_tokens / 1_000_000) * output_price)
        
        # Accumulate stats
        session_input_tokens += input_tokens
        session_output_tokens += output_tokens
        session_cost += cost

        # Simulate streaming by splitting reply into words
        words = reply.split(" ")
        for i, word in enumerate(words):
            chunk = word
            if i < len(words) - 1:
                chunk += " "
            print(json.dumps({"status": "chunk", "text": chunk}), flush=True)
            time.sleep(0.015)
            
        display_stats = f"📊 [Mock Mode | Model: {display_name} | Input Tokens: {input_tokens} | Output Tokens: {output_tokens} | Cost: ${cost:.7f}]"
        history.append({"role": "assistant", "content": reply})
        print(json.dumps({"status": "done", "reply": reply, "display_stats": display_stats, "input_tokens": input_tokens, "output_tokens": output_tokens, "cost": cost}), flush=True)

    # API execution block
    def execute_api_turn(msg):
        nonlocal use_mock, session_input_tokens, session_output_tokens, session_cost
        
        # Check for wake words to dynamically switch system prompt / personas
        msg_lower = msg.lower()
        activation_banner = ""
        nonlocal system_prompt
        if "captain jack sparrow" in msg_lower or "caption jack sparrow" in msg_lower:
            system_prompt = "act as a pirate"
            activation_banner = "🏴‍☠️ Captain Jack Sparrow has taken the helm! (Pirate persona activated)\n\n"
        elif "dumbledore" in msg_lower:
            system_prompt = "act as a wizard"
            activation_banner = "🧙‍♂️ Dumbledore has entered! (Wizard persona activated)\n\n"

        # Add user query to conversation history
        history.append({"role": "user", "content": msg})

        # Stream the activation banner if present
        if activation_banner:
            print(json.dumps({"status": "chunk", "text": activation_banner}), flush=True)
        
        # If we are in mock mode, run the mock generator
        if use_mock:
            try:
                run_mock_streaming(msg)
            except Exception as e:
                history.pop()
                print(json.dumps({"status": "error", "message": f"Simulated error: {str(e)}"}), flush=True)
            return

        # Real API Calls
        try:
            input_tokens = 0
            output_tokens = 0
            reply = ""
            
            if provider == "anthropic":
                def get_stream():
                    kwargs = {
                        "model": model_name,
                        "max_tokens": max_tokens,
                        "messages": history,
                        "stream": True
                    }
                    if temperature is not None:
                        kwargs["temperature"] = temperature
                    if system_prompt:
                        kwargs["system"] = system_prompt
                    return client.messages.create(**kwargs)
                stream = execute_with_retry(get_stream)
                for event in stream:
                    if event.type == "message_start":
                        input_tokens = event.message.usage.input_tokens
                    elif event.type == "content_block_delta":
                        chunk_text = event.delta.text
                        reply += chunk_text
                        print(json.dumps({"status": "chunk", "text": chunk_text}), flush=True)
                    elif event.type == "message_delta":
                        output_tokens = event.delta.usage.output_tokens
                
            elif provider == "openai":
                def get_stream():
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.extend(history)
                    kwargs = {
                        "model": model_name,
                        "max_tokens": max_tokens,
                        "messages": messages,
                        "stream": True,
                        "stream_options": {"include_usage": True}
                    }
                    if temperature is not None:
                        kwargs["temperature"] = temperature
                    return client.chat.completions.create(**kwargs)
                stream = execute_with_retry(get_stream)
                for chunk in stream:
                    if len(chunk.choices) > 0:
                        chunk_text = chunk.choices[0].delta.content
                        if chunk_text:
                            reply += chunk_text
                            print(json.dumps({"status": "chunk", "text": chunk_text}), flush=True)
                    if hasattr(chunk, "usage") and chunk.usage is not None:
                        input_tokens = chunk.usage.prompt_tokens
                        output_tokens = chunk.usage.completion_tokens
                
            elif provider == "gemini":
                contents = []
                for turn in history:
                    role = "user" if turn["role"] == "user" else "model"
                    contents.append({
                        "role": role,
                        "parts": [turn["content"]]
                    })
                
                generation_config = {}
                if temperature is not None:
                    generation_config["temperature"] = temperature
                if max_tokens is not None:
                    generation_config["max_output_tokens"] = max_tokens
                
                model_kwargs = {"model_name": model_name}
                if generation_config:
                    model_kwargs["generation_config"] = generation_config
                if system_prompt:
                    model_kwargs["system_instruction"] = system_prompt
                
                model_obj = genai.GenerativeModel(**model_kwargs)
                
                def get_stream():
                    return model_obj.generate_content(contents, stream=True)
                
                response_stream = execute_with_retry(get_stream)
                last_chunk = None
                for chunk in response_stream:
                    chunk_text = chunk.text
                    if chunk_text:
                        reply += chunk_text
                        print(json.dumps({"status": "chunk", "text": chunk_text}), flush=True)
                    last_chunk = chunk
                
                usage = None
                if last_chunk and hasattr(last_chunk, "usage_metadata") and last_chunk.usage_metadata:
                    usage = last_chunk.usage_metadata
                elif hasattr(response_stream, "usage_metadata") and response_stream.usage_metadata:
                    usage = response_stream.usage_metadata
                
                if usage:
                    input_tokens = usage.prompt_token_count
                    output_tokens = usage.candidates_token_count
                else:
                    input_tokens = sum(estimate_tokens(turn["content"]) for turn in history)
                    if system_prompt:
                        input_tokens += estimate_tokens(system_prompt)
                    output_tokens = estimate_tokens(reply)
            
            # Calculate cost
            cost = ((input_tokens / 1_000_000) * input_price) + ((output_tokens / 1_000_000) * output_price)
            
            # Accumulate stats
            session_input_tokens += input_tokens
            session_output_tokens += output_tokens
            session_cost += cost

            display_stats = f"📊 [Real API | Model: {display_name} | Input Tokens: {input_tokens} | Output Tokens: {output_tokens} | Cost: ${cost:.7f}]"
            
            # Store assistant response to maintain conversational context
            history.append({"role": "assistant", "content": reply})
            
            # Respond to parent process
            print(json.dumps({"status": "done", "reply": reply, "display_stats": display_stats, "input_tokens": input_tokens, "output_tokens": output_tokens, "cost": cost}), flush=True)
            
        except Exception as e:
            # Check if this looks like a credit/auth/key issue, if so, fallback to mock seamlessly
            err_str = str(e)
            if "credit balance" in err_str or "401" in err_str or "billing" in err_str or "API key" in err_str or "invalid" in err_str.lower() or "unauthorized" in err_str.lower():
                use_mock = True
                fallback_warning = "⚠️ [API Failed (Credit/Auth/Invalid Key) - Seamless Fallback to Mock]\n\n"
                try:
                    run_mock_streaming(msg, fallback_warning=fallback_warning)
                except Exception as ex:
                    history.pop()
                    print(json.dumps({"status": "error", "message": f"Simulated fallback error: {str(ex)}"}), flush=True)
            else:
                history.pop()  # Remove failed message so history isn't poisoned
                print(json.dumps({"status": "error", "message": f"API Error: {err_str}"}), flush=True)

    # 1. API Mode Execution (Stateless)
    if args.api:
        try:
            line = sys.stdin.readline()
            if not line:
                sys.exit(0)
            data = json.loads(line)
            
            req_provider = data.get("provider", "anthropic")
            req_model = data.get("model")
            msg = data.get("message", "")
            history = data.get("history", [])
            temperature = data.get("temperature", 0.7)
            max_tokens = data.get("max_tokens", 300)
            system_prompt = data.get("system_prompt")
            
            init_provider_client(req_provider)
            update_provider_details(req_provider, req_model)
            
            execute_api_turn(msg)
        except Exception as ex:
            print(json.dumps({"status": "error", "message": f"API Mode Failure: {str(ex)}"}), flush=True)
        sys.exit(0)

    # 2. CLI Mode Execution (Interactive Loop)
    for line in sys.stdin:
        msg = line.strip()
        if not msg:
            continue
        
        # Handle Session slash commands
        if msg.startswith("/"):
            parts = msg.split(" ", 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""
            
            if cmd == "/provider":
                subparts = arg.split(" ", 1)
                target_prov = subparts[0].lower()
                target_model = subparts[1].strip() if len(subparts) > 1 else None
                
                if target_prov in MODEL_DETAILS:
                    if target_model and target_model not in MODEL_DETAILS[target_prov]:
                        print(json.dumps({
                            "status": "command_error", 
                            "message": f"❌ Invalid model '{target_model}'. Options for {target_prov}: {', '.join(MODEL_DETAILS[target_prov].keys())}"
                        }), flush=True)
                        continue
                    init_provider_client(target_prov)
                    update_provider_details(target_prov, target_model)
                    history = []  # Clear history to avoid schema compatibility errors
                    print(json.dumps({
                        "status": "command_success", 
                        "message": f"🔄 Switched active provider to {display_name} (Conversation history cleared)"
                    }), flush=True)
                else:
                    print(json.dumps({
                        "status": "command_error", 
                        "message": f"❌ Invalid provider '{target_prov}'. Options: {', '.join(MODEL_DETAILS.keys())}"
                    }), flush=True)
                continue
                
            elif cmd == "/system":
                if arg:
                    system_prompt = arg
                    print(json.dumps({
                        "status": "command_success", 
                        "message": f"⚙️ Updated system instruction to: \"{system_prompt}\""
                    }), flush=True)
                else:
                    system_prompt = None
                    print(json.dumps({
                        "status": "command_success", 
                        "message": "⚙️ Cleared system instruction"
                    }), flush=True)
                continue

            elif cmd == "/temperature":
                try:
                    temp_val = float(arg)
                    if 0.0 <= temp_val <= 2.0:
                        temperature = temp_val
                        print(json.dumps({
                            "status": "command_success", 
                            "message": f"🌡️ Temperature set to {temperature}"
                        }), flush=True)
                    else:
                        print(json.dumps({
                            "status": "command_error", 
                            "message": "❌ Temperature must be between 0.0 and 2.0"
                        }), flush=True)
                except ValueError:
                    print(json.dumps({
                        "status": "command_error", 
                        "message": "❌ Invalid temperature. Must be a float."
                    }), flush=True)
                continue

            elif cmd == "/max_tokens":
                try:
                    tokens_val = int(arg)
                    if 1 <= tokens_val <= 4096:
                        max_tokens = tokens_val
                        print(json.dumps({
                            "status": "command_success", 
                            "message": f"🪙 Max tokens set to {max_tokens}"
                        }), flush=True)
                    else:
                        print(json.dumps({
                            "status": "command_error", 
                            "message": "❌ Max tokens must be between 1 and 4096"
                        }), flush=True)
                except ValueError:
                    print(json.dumps({
                        "status": "command_error", 
                        "message": "❌ Invalid max tokens. Must be an integer."
                    }), flush=True)
                continue
                
            elif cmd == "/stats":
                print(json.dumps({
                    "status": "command_success", 
                    "message": (
                        f"📊 [Cumulative Session Stats]\n"
                        f"🔹 Total Input Tokens: {session_input_tokens}\n"
                        f"🔹 Total Output Tokens: {session_output_tokens}\n"
                        f"🔹 Total Conversation Cost: ${session_cost:.7f}"
                    )
                }), flush=True)
                continue
                
            elif cmd == "/export":
                if not history:
                    print(json.dumps({
                        "status": "command_error", 
                        "message": "❌ Cannot export an empty conversation."
                    }), flush=True)
                    continue
                try:
                    os.makedirs("session_exports", exist_ok=True)
                    filename = f"session_exports/chat_export_{int(time.time())}.md"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(f"# Chat History Export\n\n")
                        f.write(f"* **Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"* **Active Provider**: {display_name}\n")
                        if system_prompt:
                            f.write(f"* **System Instruction**: {system_prompt}\n")
                        f.write(f"* **Temperature**: {temperature}\n")
                        f.write(f"* **Max Tokens**: {max_tokens}\n")
                        f.write("\n---\n\n")
                        for turn in history:
                            role_tag = "**User**" if turn["role"] == "user" else "**Assistant**"
                            f.write(f"### {role_tag}\n\n{turn['content']}\n\n")
                    print(json.dumps({
                        "status": "command_success", 
                        "message": f"💾 Exported chat history successfully to: {filename}"
                    }), flush=True)
                except Exception as ex:
                    print(json.dumps({
                        "status": "command_error", 
                        "message": f"❌ Export failed: {str(ex)}"
                    }), flush=True)
                continue
                
            elif cmd == "/theme":
                valid_themes = ["classic", "matrix", "cyberpunk"]
                if arg and arg.lower() in valid_themes:
                    theme_name = arg.lower()
                    print(json.dumps({
                        "status": "command_success", 
                        "message": f"🎨 Theme updated to: {theme_name}",
                        "theme": theme_name
                    }), flush=True)
                else:
                    print(json.dumps({
                        "status": "command_error", 
                        "message": f"❌ Invalid theme '{arg}'. Options: {', '.join(valid_themes)}"
                    }), flush=True)
                continue
                
            else:
                print(json.dumps({
                    "status": "command_error", 
                    "message": f"❌ Unknown command '{cmd}'. Available: /provider, /system, /temperature, /max_tokens, /stats, /theme, /export"
                }), flush=True)
                continue

        # Execute prompt turn in interactive CLI mode
        execute_api_turn(msg)

if __name__ == "__main__":
    main()

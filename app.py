from flask import Flask, render_template, request, jsonify
from gunicorn import app as application
import os
import json
import requests
from textblob import TextBlob
import time
import google.generativeai as genai
from collections import deque
from threading import Thread
import re
from datetime import datetime
import math
from pyngrok import ngrok  # Added for ngrok

# Initialize Flask application
app = Flask(__name__)

# Set up ngrok authentication
ngrok.set_auth_token("2qWiCkN2D4epuJEnyrQ7JDSN6pl_2R5kPqgXy3TCytRBD8CA3")

# Configure the API key
api_key = "AIzaSyBIjJ5myCp4VdJpR26mjcmal_nfC6xZnfM"
genai.configure(api_key=api_key)

# Enhanced generation config for better responses
generation_config = {
    "temperature": 0.7,  # Balanced for creativity and accuracy
    "top_p": 0.9,       # Higher for more diverse responses
    "top_k": 40,        # Increased for better response variety
    "max_output_tokens": 1000,  # Increased for longer responses
    "response_mime_type": "text/plain",
}

# System prompt template for better context
SYSTEM_PROMPT = """You are Alice, an advanced AI assistant with capabilities similar to ChatGPT. You are helpful, creative, knowledgeable, and able to engage in detailed conversations on a wide range of topics. You can:

1. Answer questions about any topic with detailed, accurate information
2. Help with analysis and problem-solving
3. Assist with coding and technical tasks
4. Engage in creative writing and storytelling
5. Provide step-by-step explanations
6. Remember context from earlier in the conversation
7. Admit when you're not sure about something

Current date: {current_date}
User's name: {user_name}

Please maintain a helpful, friendly, and informative tone while providing accurate and thorough responses."""

# Initialize the model with enhanced capabilities
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
)

# Initialize storage with increased capacity
response_cache = {}
memory = {}
history = deque(maxlen=2000)  # Increased history capacity
context_window = deque(maxlen=10)  # Store recent conversation context
history_file = "chat_history.json"

class ConversationManager:
    def __init__(self):
        self.conversation_context = ""
        self.topic_memory = {}
        self.user_preferences = {}
        
    def update_context(self, user_input, bot_response):
        # Update conversation context
        self.conversation_context = f"{self.conversation_context}\nUser: {user_input}\nAlice: {bot_response}"
        # Keep only last 5 exchanges
        self.conversation_context = "\n".join(self.conversation_context.split("\n")[-10:])
        
    def detect_topic(self, text):
        # Simple topic detection
        topics = {
            "technology": r"computer|software|programming|AI|technology|code|internet",
            "science": r"science|physics|chemistry|biology|research|experiment",
            "math": r"math|calculation|equation|number|formula|algebra",
            "general": r".*"
        }
        
        for topic, pattern in topics.items():
            if re.search(pattern, text, re.IGNORECASE):
                return topic
        return "general"
    
    def get_relevant_context(self, user_input):
        topic = self.detect_topic(user_input)
        context = f"{SYSTEM_PROMPT.format(current_date=datetime.now().strftime('%Y-%m-%d'), user_name=memory.get('user_name', 'friend'))}\n\nCurrent topic: {topic}\n\nRecent conversation:\n{self.conversation_context}"
        return context

conversation_manager = ConversationManager()

# Enhanced async history saving
def save_history_async():
    while True:
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(list(history), f, indent=2)
            # Also save user preferences and topic memory
            with open("user_preferences.json", "w", encoding="utf-8") as f:
                json.dump(conversation_manager.user_preferences, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
        time.sleep(300)  # Save every 5 minutes

# Load history at startup
def load_history():
    global history
    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                saved_history = json.load(f)
                history.extend(saved_history)
    except Exception as e:
        print(f"Error loading history: {e}")

# Function to add to history
def add_to_history(user_input, bot_response):
    history_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user": user_input,
        "bot": bot_response
    }
    history.append(history_entry)

# Function to handle special queries
def handle_special_queries(user_input):
    # Math calculations
    if re.search(r'calculate|compute|solve', user_input, re.IGNORECASE):
        try:
            # Extract mathematical expression
            expression = re.search(r'\d+[\d\s\+\-\*\/\(\)]*\d+', user_input)
            if expression:
                result = eval(expression.group())
                return f"The result is {result}"
        except:
            pass
    return None

# Enhanced response generation
def generate_enhanced_response(user_input, context):
    try:
        # Check for special queries first
        special_response = handle_special_queries(user_input)
        if special_response:
            return special_response

        # Generate response with context
        response = model.generate_content(f"{context}\n\nUser: {user_input}\nAlice:")
        return response.text

    except Exception as e:
        return "I apologize, but I'm having trouble processing that request. Could you please rephrase it?"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data['user_input'].strip()
    
    # Get cached response if available
    if user_input.lower() in response_cache:
        response_text = response_cache[user_input.lower()]
        add_to_history(data['user_input'], response_text)
        return jsonify({"bot": response_text})

    # Get context-aware response
    context = conversation_manager.get_relevant_context(user_input)
    response_text = generate_enhanced_response(user_input, context)
    
    # Update conversation context
    conversation_manager.update_context(user_input, response_text)
    
    # Cache response if appropriate
    if len(user_input) < 100 and len(response_text) < 500:
        response_cache[user_input.lower()] = response_text
    
    # Save to history
    add_to_history(data['user_input'], response_text)
    
    return jsonify({"bot": response_text})

# Add new endpoints for enhanced features
@app.route('/clear_context', methods=['POST'])
def clear_context():
    conversation_manager.conversation_context = ""
    return jsonify({"status": "success"})

@app.route('/get_topics', methods=['GET'])
def get_topics():
    return jsonify(conversation_manager.topic_memory)

@app.route('/history', methods=['GET'])
def get_history():
    return jsonify(list(history))

if __name__ == "__main__":
    # Load history at startup
    load_history()
    
    # Start the async saving thread
    history_thread = Thread(target=save_history_async, daemon=True)
    history_thread.start()
    
    # Set up ngrok tunnel
    http_tunnel = ngrok.connect(5000)
    tunnel_url = http_tunnel.public_url
    print(f"\n * ngrok tunnel active at: {tunnel_url}")
    print(" * Share this URL with your friends to let them access your Alice AI")
    print(" * Press CTRL+C to quit\n")
    
    app.run(host="0.0.0.0", port=5000)
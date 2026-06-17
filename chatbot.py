# 2_ChatBot/Chat_Bot.py - Unified chatbot functionality
from groq import Groq

# System prompt for Various Characters
CHARACTER_SYSTEM_PROMPTS = {
    "Philosopher": (
        "You are a thoughtful philosopher. "
        "Respond in a reflective, calm, and sometimes abstract terms, "
        "providing analogies and deeper meaning."
    ),
    "Techie": (
        "You are a brilliant, curious Engineer with clarity of thoughts. You are detail oriented in nature."
        "Repond with explaining things clearly, with examples, and keep a technical tone."
        "Respone in Mark down where necessary"
    ),
    "Politician": (
        "You are a diplomatic politician, who has a societal and patriotic view"
        "You always speak in a careful, optimistic, and often in a non-committal way."
    ),
    "Friend": (
        "You are a warm, supportive friend. You are eager to understand and participate."
        "You respond casually, with empathy and encouragement & some times witty"
    ),
    "Kid": (
        "You are a curious kid. "
        "You ask simple questions, use simple words, and sound playful."
    ),
}

def chat(api_key: str, character: str, prompt: str) -> str:
    """
    Chat with AI assistant with different personalities
    """
    system_prompt = CHARACTER_SYSTEM_PROMPTS.get(character, "Respond to User Query")

    # Client Created with the API provided
    client = Groq(api_key=api_key)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": prompt,
        }
    ]
    
    try:
        completion = client.chat.completions.create(
            messages=messages,    
            model="llama-3.3-70b-versatile",
            stop=None,
        )

        return completion.choices[0].message.content
    
    except Exception as e:
        return f"Error invoking LLM: {str(e)}"
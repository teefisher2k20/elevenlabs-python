# Quickstart

> Build your first conversational agent in as little as 5 minutes.

In this guide, you'll learn how to create your first conversational agent using the ElevenLabs Python SDK. This will serve as a foundation for building conversational workflows tailored to your business use cases.

## Getting started

ElevenLabs Agents are managed either through the [Agents Platform dashboard](https://elevenlabs.io/app/agents), the [ElevenLabs API](https://elevenlabs.io/docs/api-reference) or the Python SDK.

The assistant at the bottom right corner of the [ElevenLabs docs page](https://elevenlabs.io/docs) is an example of an ElevenLabs agent, capable of answering questions about ElevenLabs, navigating pages & taking you to external resources.

## Creating your first agent

In this quickstart guide we'll create an agent via the Python SDK. Next we'll test the agent, either by embedding it in your website or via the ElevenLabs dashboard.

### Prerequisites

- Python 3.8 or higher
- An ElevenLabs account with API access
- Basic Python knowledge

### Installation

```bash
pip install elevenlabs python-dotenv
```

For conversational agents with audio capabilities:

```bash
pip install elevenlabs[pyaudio] python-dotenv
```

## Build an agent via the Python SDK

### Step 1: Create an API key

[Create an API key in the dashboard here](https://elevenlabs.io/app/settings/api-keys), which you'll use to securely access the API.

Store the key as a managed secret and pass it to the SDK via an `.env` file:

```bash
# .env
ELEVENLABS_API_KEY=your_api_key_here
```

### Step 2: Create the agent

Create a new file named `create_agent.py` and add the following code:

```python
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import os

load_dotenv()

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)

prompt = """
You are a friendly and efficient virtual assistant for [Your Company Name].
Your role is to assist customers by answering questions about the company's products, services,
and documentation. You should use the provided knowledge base to offer accurate and helpful responses.

Tasks:
- Answer Questions: Provide clear and concise answers based on the available information.
- Clarify Unclear Requests: Politely ask for more details if the customer's question is not clear.

Guidelines:
- Maintain a friendly and professional tone throughout the conversation.
- Be patient and attentive to the customer's needs.
- If unsure about any information, politely ask the customer to repeat or clarify.
- Avoid discussing topics unrelated to the company's products or services.
- Aim to provide concise answers. Limit responses to a couple of sentences and let the user guide you on where to provide more detail.
"""

response = client.conversational_ai.agents.create(
    name="My voice agent",
    tags=["test"],  # List of tags to help classify and filter the agent
    conversation_config={
        "tts": {
            "voice_id": "21m00Tcm4TlvDq8ikWAM",
            "model_id": "eleven_flash_v2"
        },
        "agent": {
            "first_message": "Hi, this is Rachel from [Your Company Name] support. How can I help you today?",
            "prompt": {
                "prompt": prompt,
            }
        }
    }
)

print("Agent created with ID:", response.agent_id)
```

> **Note:** The agent created above will have a `"test"` tag, which is useful to help classify and filter the agent. For example, distinguishing between test agents and production agents.

### Step 3: Run the code

```bash
python create_agent.py
```

The above will generate an agent with baseline settings and print the ID of the agent to the console.

### Step 4: Test the agent in Python

Create a new file named `test_agent.py`:

```python
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
import os

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Create audio interface for real-time audio input/output
audio_interface = DefaultAudioInterface()

# Create conversation with your agent ID
conversation = Conversation(
    client=client,
    agent_id="your-agent-id",  # Replace with your agent ID from Step 2
    requires_auth=True,
    audio_interface=audio_interface,
)

print("Starting conversation... Speak into your microphone!")
print("Press Ctrl+C to stop.")

try:
    # Start the conversation
    conversation.start_session()
    
    # Keep running until interrupted
    import asyncio
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    print("\nEnding conversation...")
    conversation.end_session()
    conversation.wait_for_session_end()
    print("Conversation ended.")
```

Run the test:

```bash
python test_agent.py
```

### Step 5: Test via the web dashboard

The newly created agent can also be tested via the [ElevenLabs dashboard](https://elevenlabs.io/app/agents). From the dashboard, select your agent and click the **Test AI agent** button.

### Step 6: Embed in your website

If you want to quickly test the agent in your own website, you can use the Agent widget. Simply paste the following HTML snippet into your website, replacing `agent-id` with the ID of your agent:

```html
<elevenlabs-convai agent-id="your-agent-id"></elevenlabs-convai>
<script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>
```

## Adding custom tools

Make your agent more powerful by adding custom tools it can call during conversations:

```python
from elevenlabs.conversational_ai.conversation import Conversation, ClientTools
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from datetime import datetime

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Create ClientTools and register custom functions
client_tools = ClientTools()

# Sync tool example
def get_current_time(params):
    return datetime.now().strftime("%H:%M:%S")

# Async tool example
async def get_weather(params):
    location = params.get("location", "Unknown")
    # Your async weather API logic here
    return f"Weather in {location}: Sunny, 72°F"

# Register the tools
client_tools.register("get_current_time", get_current_time, is_async=False)
client_tools.register("get_weather", get_weather, is_async=True)

# Create conversation with tools
audio_interface = DefaultAudioInterface()

conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    requires_auth=True,
    audio_interface=audio_interface,
    client_tools=client_tools,
)

conversation.start_session()
```

## Configuration options

### Choosing the right voice model

- **eleven_multilingual_v2**: Best quality, 29 languages, standard latency (recommended for most use cases)
- **eleven_turbo_v2_5**: Balanced quality/speed, 32 languages
- **eleven_flash_v2**: Ultra-low latency, 50% cheaper, 32 languages

```python
conversation_config={
    "tts": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "model_id": "eleven_turbo_v2_5"  # Change model here
    }
}
```

### Using callbacks

Monitor conversation events with callbacks:

```python
def on_agent_response(response: str):
    print(f"Agent: {response}")

def on_user_transcript(transcript: str):
    print(f"User: {transcript}")

conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    requires_auth=True,
    audio_interface=audio_interface,
    callback_agent_response=on_agent_response,
    callback_user_transcript=on_user_transcript,
)
```

## Next steps

As a follow-up to this quickstart guide, you can make your agent more effective by:

### 1. Adding a knowledge base

Equip your agent with domain-specific information by uploading documents and resources through the [ElevenLabs dashboard](https://elevenlabs.io/app/agents).

### 2. Registering more tools

Allow your agent to perform tasks on your behalf:

```python
async def create_support_ticket(params):
    title = params.get("title")
    description = params.get("description")
    # Your ticket creation logic
    return {"ticket_id": "12345", "status": "created"}

client_tools.register("create_support_ticket", create_support_ticket, is_async=True)
```

### 3. Implementing authorization

Restrict access to certain conversations by configuring authentication in your agent settings.

### 4. Setting up evaluation criteria

Define custom criteria to analyze conversations and improve performance. Configure this in the **Analysis** tab of your agent in the dashboard.

### 5. Collecting conversation data

Extract specific data points from each conversation to track user inquiries, sentiment, and more.

### 6. Reviewing conversation history

Access the **Call history** tab in the dashboard to review transcripts, evaluation results, and collected data.

## Additional resources

- **[Building Agents Guide](BUILDING_AGENTS.md)**: Comprehensive guide for building production-ready agents
- **[API Reference](reference.md)**: Complete SDK API documentation
- **[ElevenLabs Documentation](https://elevenlabs.io/docs)**: Official platform documentation
- **[Voice Library](https://elevenlabs.io/voice-lab)**: Explore available voices
- **[Models & Languages](https://elevenlabs.io/docs/models)**: Learn about available models

## Support

- [Discord Community](https://discord.gg/elevenlabs)
- [GitHub Issues](https://github.com/elevenlabs/elevenlabs-python/issues)
- [Twitter](https://twitter.com/elevenlabsio)

## Troubleshooting

### Common issues

**"PyAudio not found" error:**

```bash
pip install elevenlabs[pyaudio]
```

**"Invalid API key" error:**

- Verify your API key is correct in the `.env` file
- Ensure the `.env` file is in the same directory as your script
- Check that `python-dotenv` is installed

**Audio not working:**

- Ensure your microphone and speakers are properly configured
- Check system audio permissions for Python
- Try adjusting buffer sizes in the audio interface

**"Task got Future attached to a different event loop" error:**

Use a custom event loop:

```python
import asyncio

async def main():
    loop = asyncio.get_running_loop()
    client_tools = ClientTools(loop=loop)
    # ... rest of your code

asyncio.run(main())
```

For more detailed troubleshooting, see the [Building Agents Guide](BUILDING_AGENTS.md#troubleshooting).

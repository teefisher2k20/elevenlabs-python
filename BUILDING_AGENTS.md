# Building AI Agents with ElevenLabs Python SDK

This guide provides comprehensive patterns and best practices for building AI agents using the ElevenLabs Python SDK, with a focus on the Conversational AI features.

## Table of Contents

- [Getting Started](#getting-started)
- [Basic Agent Setup](#basic-agent-setup)
- [Audio Interface Implementation](#audio-interface-implementation)
- [Tool Registration & Custom Functions](#tool-registration--custom-functions)
- [Event Loop Management](#event-loop-management)
- [Streaming & Real-time Communication](#streaming--real-time-communication)
- [Error Handling](#error-handling)
- [Testing Your Agents](#testing-your-agents)
- [Advanced Patterns](#advanced-patterns)

## Getting Started

### Installation

```bash
pip install elevenlabs[pyaudio]
```

The `pyaudio` extra provides audio input/output capabilities for conversational agents.

### Basic Requirements

- **Python**: 3.8 - 3.12
- **API Key**: Set `ELEVENLABS_API_KEY` environment variable or pass directly to client
- **Audio Hardware**: Microphone and speakers for real-time conversations

## Basic Agent Setup

### Minimal Conversational Agent

```python
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

# Initialize client
client = ElevenLabs(api_key="YOUR_API_KEY")

# Create audio interface for real-time audio I/O
audio_interface = DefaultAudioInterface()

# Create conversation
conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    requires_auth=True,
    audio_interface=audio_interface,
)

# Start the conversation
conversation.start_session()

# The conversation runs in background
# Stop when done
conversation.end_session()
```

### With Callbacks

```python
def on_agent_response(response: str):
    """Called when agent sends a text response"""
    print(f"Agent said: {response}")

def on_user_transcript(transcript: str):
    """Called when user speech is transcribed"""
    print(f"User said: {transcript}")

conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    requires_auth=True,
    audio_interface=audio_interface,
    callback_agent_response=on_agent_response,
    callback_user_transcript=on_user_transcript,
)
```

## Audio Interface Implementation

### Understanding AudioInterface

The `AudioInterface` ABC defines how your agent handles audio input/output:

```python
from abc import ABC, abstractmethod
from typing import Callable

class AudioInterface(ABC):
    @abstractmethod
    def start(self, input_callback: Callable[[bytes], None]):
        """Start audio capture and playback.
        
        Args:
            input_callback: Call this with audio bytes (16-bit PCM mono @ 16kHz)
                           Recommended chunk size: 4000 samples (250ms)
        """
        pass
    
    @abstractmethod
    def stop(self):
        """Stop audio streams and clean up resources"""
        pass
    
    @abstractmethod
    def output(self, audio: bytes):
        """Play audio bytes (should be non-blocking)"""
        pass
    
    @abstractmethod
    def interrupt(self):
        """Immediately stop current audio playback"""
        pass
```

### Custom Audio Interface Example

```python
import queue
import threading
import pyaudio

class CustomAudioInterface(AudioInterface):
    INPUT_FRAMES = 4000   # 250ms @ 16kHz
    OUTPUT_FRAMES = 1000  # 62.5ms @ 16kHz
    
    def __init__(self):
        self.pyaudio = pyaudio.PyAudio()
        self.output_queue = queue.Queue()
        self.should_stop = threading.Event()
    
    def start(self, input_callback: Callable[[bytes], None]):
        self.input_callback = input_callback
        
        # Input stream with callback
        self.in_stream = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            stream_callback=self._input_callback,
            frames_per_buffer=self.INPUT_FRAMES,
        )
        
        # Output stream (separate thread)
        self.out_stream = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
            frames_per_buffer=self.OUTPUT_FRAMES,
        )
        
        # Start output thread
        self.output_thread = threading.Thread(target=self._output_worker)
        self.output_thread.start()
    
    def stop(self):
        self.should_stop.set()
        self.output_thread.join()
        self.in_stream.close()
        self.out_stream.close()
        self.pyaudio.terminate()
    
    def output(self, audio: bytes):
        """Queue audio for playback"""
        self.output_queue.put(audio)
    
    def interrupt(self):
        """Clear queued audio"""
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break
    
    def _input_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - forward to conversation"""
        self.input_callback(in_data)
        return (None, pyaudio.paContinue)
    
    def _output_worker(self):
        """Worker thread for audio playback"""
        while not self.should_stop.is_set():
            try:
                audio = self.output_queue.get(timeout=0.25)
                self.out_stream.write(audio)
            except queue.Empty:
                continue
```

## Tool Registration & Custom Functions

### Basic Tool Registration

Tools allow your agent to call custom Python functions during conversations:

```python
from elevenlabs.conversational_ai.conversation import ClientTools

client_tools = ClientTools()

# Synchronous tool
def get_current_time(params):
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

# Asynchronous tool
async def fetch_weather(params):
    import httpx
    location = params.get("location", "San Francisco")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.weather.com/v1/{location}")
        return response.json()

# Register tools
client_tools.register("get_current_time", get_current_time, is_async=False)
client_tools.register("fetch_weather", fetch_weather, is_async=True)

# Use with conversation
conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    requires_auth=True,
    audio_interface=audio_interface,
    client_tools=client_tools,
)
```

### Tool Parameters

Tools receive a dictionary with:

- User-defined parameters from the agent's tool call
- `tool_call_id`: Unique identifier for correlating responses

```python
def calculator(params):
    operation = params.get("operation")  # "add", "subtract", etc.
    numbers = params.get("numbers", [])
    
    if operation == "add":
        return sum(numbers)
    elif operation == "multiply":
        result = 1
        for n in numbers:
            result *= n
        return result
    else:
        raise ValueError(f"Unknown operation: {operation}")

client_tools.register("calculator", calculator, is_async=False)
```

### Error Handling in Tools

Tools automatically wrap exceptions and return them to the agent:

```python
async def database_query(params):
    query = params.get("query")
    
    if not query:
        raise ValueError("Missing required parameter: query")
    
    # Execute query
    try:
        result = await db.execute(query)
        return {"rows": result, "count": len(result)}
    except Exception as e:
        # Error will be sent to agent with is_error: true
        raise RuntimeError(f"Database error: {str(e)}")

client_tools.register("database_query", database_query, is_async=True)
```

## Event Loop Management

### Default Event Loop (Automatic)

```python
# ClientTools creates its own event loop
client_tools = ClientTools()
client_tools.start()

# Tool execution happens automatically
# Stop when done
client_tools.stop()
```

### Custom Event Loop (Advanced)

**Use when you need:**

- Request-scoped state propagation
- Shared async resources (DB connections, HTTP sessions)
- Integration with existing async frameworks (FastAPI, aiohttp)

```python
import asyncio
from elevenlabs.conversational_ai.conversation import ClientTools, Conversation

async def main():
    # Get running event loop
    custom_loop = asyncio.get_running_loop()
    
    # Pass loop to ClientTools
    client_tools = ClientTools(loop=custom_loop)
    
    # Tools can now access loop-scoped resources
    async def get_user_data(params):
        user_id = params.get("user_id")
        # Access loop-local resources
        async with get_db_session() as session:
            user = await session.query(User).filter_by(id=user_id).first()
            return {"name": user.name, "email": user.email}
    
    client_tools.register("get_user_data", get_user_data, is_async=True)
    
    # Create conversation with custom tools
    conversation = Conversation(
        client=client,
        agent_id="your-agent-id",
        requires_auth=True,
        audio_interface=audio_interface,
        client_tools=client_tools,
    )
    
    conversation.start_session()
    
    # Keep running until interrupted
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        conversation.end_session()

# Run with asyncio
asyncio.run(main())
```

### Integration with FastAPI

```python
from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager

app = FastAPI()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    loop = asyncio.get_running_loop()
    app.state.client_tools = ClientTools(loop=loop)
    
    async def check_inventory(params):
        product_id = params.get("product_id")
        # Use FastAPI's dependency injection or shared resources
        inventory = await get_inventory(product_id)
        return {"in_stock": inventory.quantity > 0}
    
    app.state.client_tools.register("check_inventory", check_inventory, is_async=True)
    yield
    # Cleanup
    app.state.client_tools.stop()

@app.websocket("/agent")
async def agent_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    conversation = Conversation(
        client=client,
        agent_id="support-agent",
        requires_auth=True,
        audio_interface=audio_interface,
        client_tools=app.state.client_tools,
    )
    
    conversation.start_session()
    # Handle WebSocket communication
```

## Streaming & Real-time Communication

### Text-to-Speech Streaming

```python
from elevenlabs import ElevenLabs
from elevenlabs.realtime_tts import text_chunker

client = ElevenLabs()

def text_generator():
    """Simulate streaming text"""
    yield "Hello, this is a streaming test. "
    yield "Text is chunked at punctuation marks. "
    yield "This creates natural pauses in speech!"

# Use text_chunker for better natural pauses
audio_stream = client.text_to_speech.convert_realtime(
    voice_id="21m00Tcm4TlvDq8ikWAM",
    text=text_chunker(text_generator()),
    model_id="eleven_multilingual_v2"
)

# Process streaming audio
for audio_chunk in audio_stream:
    if isinstance(audio_chunk, bytes):
        # Play or save audio
        play(audio_chunk)
```

### Understanding text_chunker

Splits text on natural boundaries for better speech quality:

```python
def text_chunker(chunks: Iterator[str]) -> Iterator[str]:
    """Chunks on: . , ? ! ; : — - ( ) [ ] } and space"""
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""
    for text in chunks:
        if buffer.endswith(splitters):
            yield buffer if buffer.endswith(" ") else buffer + " "
            buffer = text
        elif text.startswith(splitters):
            output = buffer + text[0]
            yield output if output.endswith(" ") else output + " "
            buffer = text[1:]
        else:
            buffer += text
    if buffer:
        yield buffer + " "
```

## Error Handling

### Typed Error Hierarchy

```python
from elevenlabs.errors import (
    BadRequestError,           # 400 - Invalid parameters
    UnauthorizedError,         # 401 - Missing/invalid API key
    ForbiddenError,           # 403 - Insufficient permissions
    NotFoundError,            # 404 - Resource not found
    ConflictError,            # 409 - Resource conflict
    UnprocessableEntityError, # 422 - Validation failed
    TooEarlyError            # 425 - Resource not ready
)

try:
    conversation.start_session()
except UnauthorizedError:
    print("Invalid API key")
except NotFoundError:
    print("Agent ID not found")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Graceful Error Recovery

```python
def create_resilient_conversation():
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            conversation = Conversation(
                client=client,
                agent_id="your-agent-id",
                requires_auth=True,
                audio_interface=audio_interface,
            )
            conversation.start_session()
            return conversation
        except (UnauthorizedError, NotFoundError):
            # Don't retry on authentication/not found errors
            raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
            time.sleep(retry_delay)
```

## Testing Your Agents

### Mock WebSocket Connections

```python
from unittest.mock import MagicMock, patch
import json
import pytest

def create_mock_websocket(messages=None):
    """Standard pattern for testing WebSocket interactions"""
    if messages is None:
        messages = [
            {
                "type": "conversation_initiation_metadata",
                "conversation_initiation_metadata_event": {"conversation_id": "test123"},
            },
            {
                "type": "agent_response",
                "agent_response_event": {"agent_response": "Hello!"}
            },
        ]
    
    def response_generator():
        for msg in messages:
            yield json.dumps(msg)
        while True:
            yield '{"type": "keep_alive"}'
    
    mock_ws = MagicMock()
    mock_ws.recv = MagicMock(side_effect=response_generator())
    return mock_ws

def test_conversation_flow():
    mock_ws = create_mock_websocket()
    mock_client = MagicMock()
    mock_client._client_wrapper.get_base_url.return_value = "https://api.elevenlabs.io"
    
    conversation = Conversation(
        client=mock_client,
        agent_id="test_agent",
        requires_auth=False,
        audio_interface=MockAudioInterface(),
    )
    
    with patch("elevenlabs.conversational_ai.conversation.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_ws
        conversation.start_session()
        # Add assertions
        conversation.end_session()
```

### Mock Audio Interface

```python
class MockAudioInterface(AudioInterface):
    def __init__(self):
        self.input_callback = None
        self.output_chunks = []
    
    def start(self, input_callback):
        self.input_callback = input_callback
    
    def stop(self):
        pass
    
    def output(self, audio):
        self.output_chunks.append(audio)
    
    def interrupt(self):
        self.output_chunks.clear()
    
    def simulate_user_speech(self, audio_bytes):
        """Helper for testing"""
        if self.input_callback:
            self.input_callback(audio_bytes)
```

### Testing Tools

```python
@pytest.mark.asyncio
async def test_tool_execution():
    custom_loop = asyncio.get_running_loop()
    client_tools = ClientTools(loop=custom_loop)
    
    async def test_tool(params):
        await asyncio.sleep(0.01)
        return f"result: {params.get('input')}"
    
    client_tools.register("test_tool", test_tool, is_async=True)
    client_tools.start()
    
    try:
        result = await client_tools.handle("test_tool", {"input": "test_value"})
        assert result == "result: test_value"
    finally:
        client_tools.stop()
```

## Advanced Patterns

### Multi-Agent Orchestration

```python
class AgentOrchestrator:
    def __init__(self, client: ElevenLabs):
        self.client = client
        self.agents = {}
    
    def register_agent(self, name: str, agent_id: str, tools: ClientTools):
        """Register a specialized agent"""
        self.agents[name] = {
            "agent_id": agent_id,
            "tools": tools,
            "conversation": None
        }
    
    async def start_agent(self, name: str, audio_interface: AudioInterface):
        """Start a specific agent"""
        if name not in self.agents:
            raise ValueError(f"Unknown agent: {name}")
        
        agent = self.agents[name]
        conversation = Conversation(
            client=self.client,
            agent_id=agent["agent_id"],
            requires_auth=True,
            audio_interface=audio_interface,
            client_tools=agent["tools"],
        )
        conversation.start_session()
        agent["conversation"] = conversation
        return conversation
    
    def switch_agent(self, from_name: str, to_name: str):
        """Switch between agents"""
        if from_name in self.agents and self.agents[from_name]["conversation"]:
            self.agents[from_name]["conversation"].end_session()
        
        return self.start_agent(to_name, self.agents[to_name]["audio_interface"])

# Usage
orchestrator = AgentOrchestrator(client)

# Sales agent
sales_tools = ClientTools()
sales_tools.register("check_pricing", check_pricing_func, is_async=True)
orchestrator.register_agent("sales", "sales-agent-id", sales_tools)

# Support agent
support_tools = ClientTools()
support_tools.register("create_ticket", create_ticket_func, is_async=True)
orchestrator.register_agent("support", "support-agent-id", support_tools)

# Start with sales, switch to support if needed
await orchestrator.start_agent("sales", audio_interface)
```

### Context-Aware Tools with State

```python
class StatefulTools:
    def __init__(self):
        self.client_tools = ClientTools()
        self.conversation_state = {}
    
    def register_tools(self, session_id: str):
        """Register tools with access to session state"""
        
        def get_context(params):
            key = params.get("key")
            return self.conversation_state.get(session_id, {}).get(key)
        
        def set_context(params):
            key = params.get("key")
            value = params.get("value")
            if session_id not in self.conversation_state:
                self.conversation_state[session_id] = {}
            self.conversation_state[session_id][key] = value
            return f"Set {key} to {value}"
        
        self.client_tools.register("get_context", get_context, is_async=False)
        self.client_tools.register("set_context", set_context, is_async=False)
        
        return self.client_tools
    
    def cleanup_session(self, session_id: str):
        """Clean up session state"""
        self.conversation_state.pop(session_id, None)

# Usage
tools = StatefulTools()
session_id = "user-123"
client_tools = tools.register_tools(session_id)

conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    requires_auth=True,
    audio_interface=audio_interface,
    client_tools=client_tools,
)
```

### Dynamic Configuration

```python
from elevenlabs.conversational_ai.conversation import ConversationInitiationData

# Configure conversation with dynamic variables
config = ConversationInitiationData(
    user_id="user-123",
    dynamic_variables={
        "user_name": "Alice",
        "account_type": "premium",
        "language": "en-US"
    },
    conversation_config_override={
        "tts": {"model_id": "eleven_turbo_v2_5"},
        "asr": {"language": "en"}
    }
)

conversation = Conversation(
    client=client,
    agent_id="your-agent-id",
    config=config,
    requires_auth=True,
    audio_interface=audio_interface,
)
```

## Best Practices

### 1. Always Clean Up Resources

```python
try:
    conversation.start_session()
    # Your logic here
finally:
    conversation.end_session()
    conversation.wait_for_session_end()
```

### 2. Use Appropriate Timeouts

```python
# For long-running operations (audio generation)
client = ElevenLabs(timeout=240)  # 240 seconds default
```

### 3. Handle Interruptions Gracefully

```python
# Implement interrupt() in your AudioInterface
def interrupt(self):
    """Clear buffered audio when user interrupts"""
    while not self.output_queue.empty():
        try:
            self.output_queue.get_nowait()
        except queue.Empty:
            break
```

### 4. Log for Debugging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def on_agent_response(response: str):
    logger.info(f"Agent response: {response}")

def on_error(error: Exception):
    logger.error(f"Conversation error: {error}", exc_info=True)
```

### 5. Choose the Right Model

- **eleven_multilingual_v2**: Best quality, 29 languages, standard latency
- **eleven_turbo_v2_5**: Balanced quality/speed, 32 languages
- **eleven_flash_v2_5**: Ultra-low latency, 50% cheaper, 32 languages

## Troubleshooting

### "Task got Future attached to a different event loop"

**Solution**: Use custom event loop

```python
loop = asyncio.get_running_loop()
client_tools = ClientTools(loop=loop)
```

### Audio playback stuttering

**Solution**: Increase buffer sizes or use separate thread

```python
class OptimizedAudioInterface(AudioInterface):
    OUTPUT_FRAMES_PER_BUFFER = 2000  # Increase from 1000
```

### Tools not executing

**Solution**: Ensure tools are registered before `start_session()`

```python
client_tools.register("my_tool", my_func, is_async=True)
client_tools.start()  # Start before creating conversation
conversation = Conversation(..., client_tools=client_tools)
```

## Additional Resources

- [ElevenLabs API Documentation](https://elevenlabs.io/docs/api-reference)
- [Models & Languages](https://elevenlabs.io/docs/models)
- [Voice Lab](https://elevenlabs.io/voice-lab)
- [SDK Reference](reference.md)

## Support

- [Discord Community](https://discord.gg/elevenlabs)
- [GitHub Issues](https://github.com/elevenlabs/elevenlabs-python/issues)
- [Twitter](https://twitter.com/elevenlabsio)

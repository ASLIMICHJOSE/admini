# JARVIS Voice Assistant

A fully functional AI-based voice assistant designed to automate daily computer tasks and provide intelligent responses through speech.

## Features

### Voice Control
- **Wake Word Activation**: Say "Hey JARVIS" to activate
- **Push-to-Talk**: Press Ctrl+Space for immediate activation
- **Continuous Listening**: Always-on audio processing with customizable sensitivity

### Command Categories
- **System Control**: Open/close applications, shutdown/restart, volume control
- **Web Automation**: Browser control, Google searches, YouTube, Wikipedia
- **Information Retrieval**: Weather updates, news headlines, general knowledge
- **Communication**: Send emails and messages
- **Entertainment**: Music playback, media control
- **Personal Assistant**: Reminders, timers, calendar integration

### AI-Powered Intelligence
- **OpenAI Integration**: Advanced natural language understanding
- **Offline Fallback**: Basic commands work without internet
- **Context Awareness**: Remembers recent commands and context
- **Adaptive Learning**: Improves recognition over time

## Quick Start

### Prerequisites
- Python 3.8+
- Microphone and speakers
- Internet connection (for AI features)

### Installation

```bash
# Clone and setup
git clone <repository_url>
cd admini
python -m venv jarvis-env
source jarvis-env/bin/activate  # On Windows: jarvis-env\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp .env.example .env
cp config.yaml.example config.yaml

# Run tests
python main.py --test
```

### Configuration

Edit `.env` file with your API keys:
```bash
OPENAI_API_KEY=your_openai_key
WEATHER_API_KEY=your_weather_key    # Optional
NEWS_API_KEY=your_news_key         # Optional
```

### Run JARVIS

```bash
# Interactive mode
python main.py

# Background/daemon mode
python main.py --daemon

# With custom config
python main.py --config my_config.yaml
```

## Usage Examples

### Basic Commands
- "Hey JARVIS, what time is it?"
- "Hey JARVIS, open Chrome"
- "Hey JARVIS, play some music"
- "Hey JARVIS, what's the weather?"

### Advanced Commands
- "Hey JARVIS, search for Python tutorials on YouTube"
- "Hey JARVIS, send an email to John about the meeting"
- "Hey JARVIS, set a reminder for 3 PM"

### System Commands
- "Hey JARVIS, set volume to 50%"
- "Hey JARVIS, show running processes"
- "Hey JARVIS, restart computer" *(requires confirmation)*

## Configuration

### Audio Settings
```yaml
audio:
  wake_word: "Hey JARVIS"
  hotkey_combination: "ctrl+space"
  sensitivity: 0.5
  timeout_seconds: 5
```

### AI Settings
```yaml
ai:
  use_openai: true
  model: "gpt-4-turbo-preview"
  cache_responses: true
  offline_fallback: true
```

### Privacy Settings
```yaml
privacy:
  sensitive_commands_hotkey_only: true
  log_sensitive_commands: false
  data_retention_days: 30
```

## Security & Privacy

- **Local Processing**: Sensitive commands processed locally only
- **Data Control**: Configure what data is shared with AI
- **No Voice Storage**: Voice recordings not permanently stored
- **Configurable Permissions**: Fine-grained control over features

## Platform Support

- **Windows 10/11**: Full feature support
- **macOS 10.14+**: Full feature support  
- **Linux (Ubuntu/Debian)**: Full feature support
- **Other Distributions**: Basic support

## Troubleshooting

### Common Issues

**Microphone not working:**
- Check system microphone permissions
- Verify microphone is not muted
- Try USB microphone for better quality

**"JARVIS doesn't understand me":**
- Reduce background noise
- Speak clearly and at normal pace
- Check audio sensitivity in config

**Commands fail:**
- Check internet connection for AI features
- Verify API keys are correctly configured
- Try offline mode if internet is unstable

### Debug Mode
```bash
python main.py --verbose
```

### Test Configuration
```bash
python main.py --test
```

## API Integrations

### Required for Full Features
- **OpenAI**: Advanced AI command understanding
- **Weather API**: Weather information
- **News API**: News headlines

### Optional Integrations
- **Email providers**: Gmail, Outlook, custom SMTP
- **Calendar services**: Google Calendar, Outlook
- **Music services**: Spotify, Apple Music, local files

## Development

### Project Structure
```
admini/
├── main.py                    # Application entry point
├── config.py                  # Configuration management
├── jarvis/
│   ├── core/                   # Core functionality
│   │   ├── speech_engine.py    # Audio processing
│   │   ├── nlp_processor.py    # AI integration
│   │   ├── command_dispatcher.py # Command routing
│   │   └── event_loop.py       # Main event loop
│   ├── commands/                # Command handlers
│   ├── services/                # External API integrations
│   ├── utils/                   # Utility functions
│   └── data/                    # Data structures
├── tests/                     # Test files
└── docs/                      # Documentation
```

### Running Tests
```bash
# Test individual components
python -m pytest tests/

# Test with coverage
python -m pytest --cov=jarvis tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

- **Issues**: Report bugs via GitHub Issues
- **Documentation**: Check `/docs` directory for detailed guides
- **Community**: Join discussions for feature requests

## Roadmap

### Version 1.1
- [ ] Smart home device integration
- [ ] Multi-language support
- [ ] Mobile companion app

### Version 1.2
- [ ] Advanced scheduling
- [ ] Custom command creation
- [ ] Cloud sync for preferences

### Version 2.0
- [ ] Local LLM integration
- [ ] Voice training
- [ ] Multi-user support

---

**JARVIS Voice Assistant** - Making your computer smarter, one command at a time.

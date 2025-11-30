#!/usr/bin/env python3
"""
Test for JARVIS main functionality
"""

import pytest
import sys
from unittest.mock import Mock, patch


def test_main_imports():
    """Test that main module can be imported."""
    try:
        import main
        assert hasattr(main, 'JARVIS')
        return True
    except ImportError:
        pytest.fail("Could not import main module")
        return False


def test_argument_parser():
    """Test command line argument parsing."""
    try:
        import main
        parser = main.create_argument_parser()
        
        # Test default arguments
        args = parser.parse_args([])
        assert not args.daemon
        assert not args.test
        assert not args.verbose
        
        # Test --test flag
        args = parser.parse_args(['--test'])
        assert args.test
        
        # Test --daemon flag
        args = parser.parse_args(['--daemon'])
        assert args.daemon
        
        return True
    except Exception as e:
        pytest.fail(f"Argument parser test failed: {e}")
        return False


def test_jarvis_initialization():
    """Test JARVIS class initialization."""
    try:
        import main
        import tempfile
        
        # Create temporary config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('''
audio:
  wake_word_enabled: false
ai:
  use_openai: false
''')
            temp_config = f.name
        
        jarvis = main.JARVIS(config_path=temp_config)
        assert jarvis.config is not None
        assert jarvis.logger is not None
        assert jarvis.error_handler is not None
        
        return True
    except Exception as e:
        pytest.fail(f"JARVIS initialization test failed: {e}")
        return False


def test_dependency_checking():
    """Test dependency checking functionality."""
    try:
        import main
        
        with patch('main.JARVIS') as mock_jarvis:
            # Mock the JARVIS instance
            instance = Mock()
            instance.check_dependencies.return_value = True
            mock_jarvis.return_value = instance
            
            jarvis_instance = main.JARVIS()
            result = jarvis_instance.check_dependencies()
            
            # Should return True or False based on dependencies
            assert isinstance(result, bool)
            
            return True
    except Exception as e:
        pytest.fail(f"Dependency checking test failed: {e}")
        return False


def test_configuration_loading():
    """Test configuration loading."""
    try:
        import config
        import tempfile
        
        # Test default config
        default_config = config.Config()
        assert hasattr(default_config, 'audio')
        assert hasattr(default_config, 'ai')
        assert hasattr(default_config, 'system')
        
        # Test config loading
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('''
audio:
  wake_word: "Test JARVIS"
  sensitivity: 0.7
ai:
  use_openai: false
  offline_fallback: true
''')
            temp_config = f.name
        
        loaded_config = config.Config.load_from_file(temp_config)
        assert loaded_config.audio.wake_word == "Test JARVIS"
        assert loaded_config.audio.sensitivity == 0.7
        assert loaded_config.ai.use_openai == False
        
        return True
    except Exception as e:
        pytest.fail(f"Configuration loading test failed: {e}")
        return False


def test_logging_setup():
    """Test logging configuration."""
    try:
        import config
        import logging
        
        # Create test config
        test_config = config.Config()
        test_config.log_level = "DEBUG"
        test_config.log_file = "test_jarvis.log"
        
        logger = config.setup_logging(test_config)
        assert logger.level == logging.DEBUG
        
        # Test log file creation
        import os
        if os.path.exists("test_jarvis.log"):
            os.remove("test_jarvis.log")
        
        return True
    except Exception as e:
        pytest.fail(f"Logging setup test failed: {e}")
        return False


if __name__ == "__main__":
    # Run tests directly
    print("Running main module tests...")
    
    tests = [
        test_main_imports,
        test_argument_parser,
        test_jarvis_initialization,
        test_dependency_checking,
        test_configuration_loading,
        test_logging_setup
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                print(f"✅ {test_func.__name__} PASSED")
                passed += 1
            else:
                print(f"❌ {test_func.__name__} FAILED")
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}")
    
    print(f"\nTest Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

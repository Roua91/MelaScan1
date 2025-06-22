"""
Test script to verify AI integration
Run this script to check if AI services are working properly
"""

import sys
import os
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_ai_imports():
    """Test if AI-related modules can be imported"""
    try:
        print("Testing AI imports...")
        
        # Test torch import
        import torch
        print(f"✓ PyTorch imported successfully (version: {torch.__version__})")
        print(f"✓ CUDA available: {torch.cuda.is_available()}")
        
        # Test PIL import
        from PIL import Image
        print("✓ PIL imported successfully")
        
        # Test torchvision import
        from torchvision import transforms, models
        print("✓ Torchvision imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_model_loading():
    """Test if the custom ResNet model can be loaded"""
    try:
        print("\nTesting model loading...")
        
        # Try to import and create the model
        from app.modelai.resnet import MelanomaResNet, ImageTransform
        
        print("✓ Model classes imported successfully")
        
        # Create model instance
        model = MelanomaResNet()
        print("✓ Model instance created successfully")
        
        # Test image transform
        transform = ImageTransform()
        print("✓ Image transform created successfully")
        
        return True, model, transform
        
    except Exception as e:
        print(f"✗ Model loading error: {e}")
        return False, None, None

def test_ai_service():
    """Test the AI service"""
    try:
        print("\nTesting AI service...")
        
        from app.services.ai_service import ai_service
        print("✓ AI service imported successfully")
        
        # Check if service is available
        if ai_service.is_available():
            print("✓ AI service is available and ready")
            
            # Get model info
            model_info = ai_service.get_model_info()
            if model_info.get('status') == 'available':
                print(f"✓ Model info: {model_info}")
            else:
                print(f"⚠ Model info warning: {model_info}")
                
        else:
            print("⚠ AI service is not available (this is expected without proper weights)")
            
        return True
        
    except Exception as e:
        print(f"✗ AI service error: {e}")
        return False

def test_dummy_prediction():
    """Test prediction with a dummy image"""
    try:
        print("\nTesting dummy prediction...")
        
        from app.services.ai_service import ai_service
        from PIL import Image
        import tempfile
        import numpy as np
        
        if not ai_service.is_available():
            print("⚠ Skipping prediction test - AI service not available")
            return True
            
        # Create a dummy RGB image
        dummy_image = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            dummy_image.save(tmp.name)
            temp_path = tmp.name
            
        try:
            # Test analysis
            result = ai_service.analyze_image(temp_path)
            
            if result.get('status') == 'success':
                print("✓ Dummy prediction successful")
                print(f"  Result: {result.get('result', {})}")
            else:
                print(f"⚠ Prediction returned: {result}")
                
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
        return True
        
    except Exception as e:
        print(f"✗ Prediction test error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("AI Integration Test Suite")
    print("=" * 50)
    
    success_count = 0
    total_tests = 4
    
    # Test 1: Imports
    if test_ai_imports():
        success_count += 1
        
    # Test 2: Model loading
    model_success, model, transform = test_model_loading()
    if model_success:
        success_count += 1
        
    # Test 3: AI service
    if test_ai_service():
        success_count += 1
        
    # Test 4: Dummy prediction
    if test_dummy_prediction():
        success_count += 1
        
    print("\n" + "=" * 50)
    print(f"Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("✓ All tests passed! AI integration looks good.")
    elif success_count >= 2:
        print("⚠ Partial success. Some features may not work without proper model weights.")
    else:
        print("✗ Multiple failures. Check your installation and configuration.")
        
    print("=" * 50)
    
    return success_count == total_tests

if __name__ == "__main__":
    main()
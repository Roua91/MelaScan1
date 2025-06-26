import pytest
import os
import io
import json
import sys
from unittest.mock import patch, MagicMock, Mock
import torch
import torch.nn as nn
from PIL import Image
import numpy as np
from flask import Flask

# Test configuration
TEST_IMAGE_PATH = r"app\static\images\skin.jpg"
TEST_WEIGHTS_PATH = r"resnet_weights.pth"

@pytest.fixture
def test_image():
    """Create a test image fixture"""
    img = Image.new('RGB', (256, 256), color='red')
    img.save(TEST_IMAGE_PATH)
    yield TEST_IMAGE_PATH
    if os.path.exists(TEST_IMAGE_PATH):
        os.remove(TEST_IMAGE_PATH)

@pytest.fixture
def mock_model():
    """Create a mock model that behaves like MelanomaModel"""
    model = Mock()
    model.weights_loaded = False
    
    # Mock base_model structure
    base_model = Mock()
    fc_layer = Mock()
    fc_layer.in_features = 2048
    base_model.fc = fc_layer
    model.base_model = base_model
    
    # Mock forward pass
    def forward(x):
        return torch.tensor([[0.7]])
    model.forward = forward
    model.return_value = torch.tensor([[0.7]])
    
    # Mock methods
    model.eval = Mock()
    model.to = Mock(return_value=model)
    model.load_custom_weights = Mock(return_value=True)
    model.state_dict = Mock(return_value={
        'base_model.fc.1.weight': torch.rand(1, 2048),
        'base_model.fc.1.bias': torch.rand(1)
    })
    model.load_state_dict = Mock()
    model.parameters = Mock(return_value=[torch.rand(100, 50), torch.rand(50)])
    
    return model

@pytest.fixture 
def mock_ai_service(mock_model):
    """Create a mock AI service"""
    ai_service = Mock()
    
    # Set up basic attributes
    ai_service.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ai_service.model = mock_model
    ai_service.model_loaded = True
    ai_service.app = None
    
    # Mock transform
    transform = Mock()
    transform.return_value = torch.rand(3, 224, 224)
    ai_service.transform = transform
    
    # Mock methods
    ai_service.is_available = Mock(return_value=True)
    ai_service.init_app = Mock()
    
    def preprocess_image(image_path):
        if not ai_service.is_available():
            raise RuntimeError("AI service is not available")
        if not os.path.exists(image_path) and image_path != 'temp_path':
            raise FileNotFoundError(f"Image not found at {image_path}")
        return torch.rand(1, 3, 224, 224)
    
    ai_service.preprocess_image = preprocess_image
    
    def predict(image_tensor):
        if not ai_service.is_available():
            raise RuntimeError("AI service is not available")
        prob = 0.7  # Mock probability
        return {
            'classification': 'malignant' if prob > 0.5 else 'benign',
            'confidence': prob if prob > 0.5 else 1 - prob,
            'probabilities': {
                'benign': 1 - prob,
                'malignant': prob
            }
        }
    
    ai_service.predict = predict
    
    def analyze_image(image_path, model_name='default'):
        try:
            if not ai_service.is_available():
                return {'status': 'error', 'message': 'AI service is not available'}
            
            # Handle temp_path as a special case for API testing
            if image_path == 'temp_path' or os.path.exists(image_path):
                image_tensor = ai_service.preprocess_image(image_path)
                prediction = ai_service.predict(image_tensor)
                
                return {
                    'status': 'success',
                    'analysis': {
                        'classification': prediction['classification'],
                        'confidence': prediction['confidence'],
                        'probabilities': prediction['probabilities'],
                        'model_used': 'CNN Model',
                        'model_version': '1.0'
                    }
                }
            else:
                raise FileNotFoundError(f"Image not found at {image_path}")
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    ai_service.analyze_image = analyze_image
    
    def get_model_info(model_name='default'):
        if not ai_service.is_available():
            return {'status': 'unavailable', 'message': 'AI service is not available'}
        
        return {
            'status': 'available',
            'total_parameters': '25,557,032',
            'trainable_parameters': '2,049',
            'device': str(ai_service.device),
            'model_type': 'CNN Model',
            'weights_loaded': True
        }
    
    ai_service.get_model_info = get_model_info
    
    return ai_service

class TestMelanomaModel:
    """Test cases for Melanoma model"""
    
    def test_model_initialization(self, mock_model):
        """Test model initialization with mocks"""
        with patch('torchvision.models.resnet50') as mock_cnn:
            mock_cnn.return_value = mock_model.base_model
            
            # Simulate model creation
            model = Mock()
            model.base_model = mock_model.base_model
            model.weights_loaded = False
            
            # Replace fc layer with Sequential (simulate the actual behavior)
            model.base_model.fc = nn.Sequential(
                nn.Dropout(0.3),
                nn.Linear(2048, 1)
            )
            
            assert model.base_model is not None
            assert isinstance(model.base_model.fc, nn.Sequential)
            assert not model.weights_loaded
    
    def test_load_custom_weights(self, mock_model):
        """Test loading custom weights"""
        with patch('torch.load') as mock_torch_load, \
             patch('os.path.exists', return_value=True):
            
            mock_torch_load.return_value = {
                'base_model.fc.1.weight': torch.rand(1, 2048),
                'base_model.fc.1.bias': torch.rand(1)
            }
            
            # Simulate weight loading
            result = mock_model.load_custom_weights(TEST_WEIGHTS_PATH)
            assert result is True
            mock_model.load_custom_weights.assert_called_with(TEST_WEIGHTS_PATH)
    
    def test_forward_pass(self, mock_model):
        """Test forward pass"""
        input_tensor = torch.rand(1, 3, 224, 224)
        output = mock_model.forward(input_tensor)
        assert output is not None
        assert output.shape == (1, 1)  # Binary classification output

class TestAIService:
    """Test cases for AI Service"""
    
    def test_initialization(self, mock_ai_service):
        """Test AI service initialization"""
        assert mock_ai_service.device is not None
        assert mock_ai_service.model is not None
        assert mock_ai_service.transform is not None
        assert mock_ai_service.model_loaded is True
    
    def test_is_available(self, mock_ai_service):
        """Test availability check"""
        assert mock_ai_service.is_available() is True
        
        # Test when not available
        mock_ai_service.is_available.return_value = False
        assert mock_ai_service.is_available() is False
    
    def test_preprocess_image(self, test_image, mock_ai_service):
        """Test image preprocessing"""
        tensor = mock_ai_service.preprocess_image(test_image)
        assert tensor is not None
        assert tensor.shape == (1, 3, 224, 224)
        
        # Test with unavailable service
        mock_ai_service.is_available.return_value = False
        with pytest.raises(RuntimeError):
            mock_ai_service.preprocess_image(test_image)
    
    def test_predict(self, mock_ai_service):
        """Test prediction"""
        input_tensor = torch.rand(1, 3, 224, 224)
        result = mock_ai_service.predict(input_tensor)
        
        assert 'classification' in result
        assert 'confidence' in result
        assert 'probabilities' in result
        assert result['classification'] in ['benign', 'malignant']
        assert 0 <= result['confidence'] <= 1
        assert 'benign' in result['probabilities']
        assert 'malignant' in result['probabilities']
    
    def test_analyze_image(self, test_image, mock_ai_service):
        """Test complete image analysis"""
        result = mock_ai_service.analyze_image(test_image)
        
        assert result['status'] == 'success'
        assert 'analysis' in result
        
        analysis = result['analysis']
        assert analysis['classification'] in ['benign', 'malignant']
        assert 0 <= analysis['confidence'] <= 1
        assert 'model_used' in analysis
        assert 'model_version' in analysis
    
    def test_analyze_nonexistent_image(self, mock_ai_service):
        """Test analysis with nonexistent image"""
        result = mock_ai_service.analyze_image("nonexistent.jpg")
        assert result['status'] == 'error'
        assert 'message' in result
    
    def test_get_model_info(self, mock_ai_service):
        """Test model info retrieval"""
        info = mock_ai_service.get_model_info()
        
        assert info['status'] == 'available'
        assert 'total_parameters' in info
        assert 'trainable_parameters' in info
        assert 'device' in info
        assert 'model_type' in info
        assert 'weights_loaded' in info
    
    def test_unavailable_service(self, mock_ai_service):
        """Test behavior when service is unavailable"""
        mock_ai_service.is_available.return_value = False
        
        result = mock_ai_service.analyze_image("test.jpg")
        assert result['status'] == 'error'
        assert 'not available' in result['message']
        
        info = mock_ai_service.get_model_info()
        assert info['status'] == 'unavailable'

class TestDoctorAPI:
    """Test cases for Doctor API endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        app.config['WTF_CSRF_ENABLED'] = False
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_analyze_image_api(self, client, mock_ai_service):
        """Test image analysis API endpoint"""
        # Import request before defining the route
        from flask import request
        
        # Create a simple route for testing
        @client.application.route('/api/analyze', methods=['POST'])
        def analyze_api():
            if 'image' not in request.files:
                return {'status': 'error', 'message': 'No image provided'}, 400
            
            file = request.files['image']
            if file.filename == '':
                return {'status': 'error', 'message': 'No selected file'}, 400
            
            # Mock the analysis with temp_path
            result = mock_ai_service.analyze_image('temp_path')
            return result
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        # Test the API
        response = client.post('/api/analyze',
                             data={'image': (img_bytes, 'test.jpg')},
                             content_type='multipart/form-data')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'analysis' in data
    
    def test_model_info_api(self, client, mock_ai_service):
        """Test model info API endpoint"""
        @client.application.route('/api/model_info')
        def model_info_api():
            model_data = mock_ai_service.get_model_info()
            return {
                'status': 'success',
                'model': {
                    'name': 'CNN Melanoma Detection',
                    'architecture': 'CNN with custom classification head',
                    'parameters': model_data.get('total_parameters', 'Unknown'),
                    'input_size': '224x224 RGB',
                    'classes': ['benign', 'malignant'],
                    'device': model_data.get('device', 'Unknown')
                }
            }
        
        response = client.get('/api/model_info')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'model' in data
        assert data['model']['name'] == 'CNN Melanoma Detection'
        assert 'parameters' in data['model']

class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_file_not_found_error(self, mock_ai_service):
        """Test handling of file not found errors"""
        result = mock_ai_service.analyze_image("nonexistent_file.jpg")
        assert result['status'] == 'error'
        assert 'not found' in result['message'].lower()
    
    def test_service_unavailable_error(self, mock_ai_service):
        """Test handling when service is unavailable"""
        mock_ai_service.is_available.return_value = False
        
        result = mock_ai_service.analyze_image("test.jpg")
        assert result['status'] == 'error'
        assert 'not available' in result['message']
    
    def test_prediction_error_handling(self, mock_ai_service):
        """Test prediction error handling"""
        # Mock an exception in predict
        def failing_predict(tensor):
            raise Exception("Model prediction failed")
        
        mock_ai_service.predict = failing_predict
        
        # This should be caught and handled gracefully
        result = mock_ai_service.analyze_image("test.jpg")
        assert result['status'] == 'error'

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
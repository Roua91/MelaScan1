import torch
from PIL import Image
from torchvision import transforms
import os
import logging
from flask import current_app

class AIService:
    def __init__(self, app=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.transform = None
        self.model_loaded = False
        self.app = app
        
        if app is not None:
            self._initialize()

    def init_app(self, app):
        """Initialize with Flask app context"""
        self.app = app
        self._initialize()

    def _initialize(self):
        """Initialize the AI service components"""
        try:
            self._init_transform()
            self._load_model()
        except Exception as e:
            self._log_error(f"AI Service initialization failed: {str(e)}")
            self.model_loaded = False

    def _log_error(self, message):
        """Log errors with app context if available"""
        try:
            if self.app and hasattr(self.app, 'logger'):
                self.app.logger.error(message)
            else:
                logging.error(message)
        except (RuntimeError, AttributeError):
            logging.error(message)

    def _log_info(self, message):
        """Log info with app context if available"""
        try:
            if self.app and hasattr(self.app, 'logger'):
                self.app.logger.info(message)
            else:
                logging.info(message)
        except (RuntimeError, AttributeError):
            logging.info(message)

    def _init_transform(self):
        """Initialize image transformation pipeline"""
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        self._log_info("Image transform initialized")

    def _load_model(self):
        try:
            # FIXED: Import os module
            import os
            # FIXED: Use direct import path
            from app.modelai.resnet import MelanomaResNet
            
            # Get weights path from config or use default
            weights_path = None
            if self.app and 'RESNET_PATH' in self.app.config:
                weights_path = self.app.config['RESNET_PATH']
                if weights_path and not os.path.exists(weights_path):
                    self._log_info(f"Custom weights not found at {weights_path}, using base ResNet50")
                    weights_path = None
            else:
                self._log_info("No weights path configured, using base ResNet50")
                
            self.model = MelanomaResNet(weights_path=weights_path).to(self.device)
            self.model.eval()
            self.model_loaded = True
            self._log_info(f"ResNet model loaded successfully on {self.device}")
            
        except Exception as e:
            self._log_error(f"Failed to load model: {str(e)}")
            self.model_loaded = False
            

    def is_available(self):
        """Check if AI service is available"""
        return self.model_loaded and self.model is not None and self.transform is not None

    def preprocess_image(self, image_path):
        """Preprocess image for model input"""
        if not self.is_available():
            raise RuntimeError("AI service is not available")
            
        img = Image.open(image_path).convert('RGB')
        return self.transform(img).unsqueeze(0).to(self.device)
            
    def predict(self, image_tensor):
        """Run prediction on preprocessed image tensor"""
        if not self.is_available():
            raise RuntimeError("AI service is not available")
            
        with torch.no_grad():
            output = self.model(image_tensor)
            prob = torch.sigmoid(output).item()
            
            # Simple classification
            if prob > 0.5:
                classification = 'malignant'
                confidence = prob
            else:
                classification = 'benign'
                confidence = 1 - prob
                
            return {
                'classification': classification,
                'confidence': confidence,
                'probabilities': {
                    'benign': 1 - prob,
                    'malignant': prob
                }
            }
            
    def analyze_image(self, image_path, model_name='resnet'):
        """Complete image analysis pipeline"""
        try:
            if not self.is_available():
                return {
                    'status': 'error',
                    'message': 'AI service is not available'
                }
                
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image not found at {image_path}")
                
            image_tensor = self.preprocess_image(image_path)
            prediction = self.predict(image_tensor)
            
            return {
                'status': 'success',
                'analysis': {
                    'classification': prediction['classification'],
                    'confidence': prediction['confidence'],
                    'probabilities': prediction['probabilities'],
                    'model_used': 'ResNet50',
                    'model_version': '1.0'
                }
            }
            
        except Exception as e:
            self._log_error(f"Image analysis failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
            
    def get_model_info(self, model_name='resnet'):
        """Get information about the AI model"""
        if not self.is_available():
            return {
                'status': 'unavailable',
                'message': 'AI service is not available'
            }
            
        try:
            total_params = sum(p.numel() for p in self.model.parameters())
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            
            return {
                'status': 'available',
                'total_parameters': f"{total_params:,}",
                'trainable_parameters': f"{trainable_params:,}",
                'device': str(self.device),
                'model_type': 'ResNet50',
                'weights_loaded': getattr(self.model, 'weights_loaded', False)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

# Create global instance
ai_service = AIService()
import os
import torch
from PIL import Image
from torchvision import transforms
from flask import current_app
from app.modelai.resnet_cbam import ResNetCBAMSelective, load_model_weights

class AIModelService:
    def __init__(self):
        self.models = {}
        self.device = None
        self.app = None
    
    def init_app(self, app):
        """Initialize service with Flask app"""
        self.app = app
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.load_models()
    
    def load_models(self):
        try:
            model_path = os.path.normpath(self.app.config['RESNET_CBAM_PATH'])
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model weights not found at {model_path}")
            
            # Use your updated model class
            model = ResNetCBAMSelective(num_classes=2, pretrained=False)
            
            # Load weights with your helper function
            if not load_model_weights(model, model_path, self.device):
                raise ValueError("Failed to load model weights")
            
            model.eval()
            model.to(self.device)
            
            # Validate model loading
            self._validate_model_loading(model)
            
            self.models['resnet_cbam'] = model
            current_app.logger.info(f"Updated ResNet50-CBAM model loaded successfully on {self.device}")
            
        except Exception as e:
            current_app.logger.error(f"Failed to load model: {str(e)}")
            raise
    
    def _map_state_dict_keys(self, saved_state_dict, model_state_dict):
        """Map saved state dict keys to current model structure"""
        mapped_dict = {}
        model_keys = list(model_state_dict.keys())
        saved_keys = list(saved_state_dict.keys())
        
        # Try to match keys
        for model_key in model_keys:
            # Direct match
            if model_key in saved_state_dict:
                mapped_dict[model_key] = saved_state_dict[model_key]
            # Try with 'model.' prefix
            elif f"model.{model_key}" in saved_state_dict:
                mapped_dict[model_key] = saved_state_dict[f"model.{model_key}"]
            # Try without 'model.' prefix if current key has it
            elif model_key.startswith('model.') and model_key[6:] in saved_state_dict:
                mapped_dict[model_key] = saved_state_dict[model_key[6:]]
        
        return mapped_dict
    
    def _validate_model_loading(self, model):
        """Validate that the model was loaded correctly"""
        try:
            # Test with different types of inputs
            test_inputs = [
                torch.zeros(1, 3, 224, 224),    # Black image
                torch.ones(1, 3, 224, 224),     # White image  
                torch.randn(1, 3, 224, 224),    # Random noise
            ]
            
            results = []
            for i, test_input in enumerate(test_inputs):
                test_input = test_input.to(self.device)
                with torch.no_grad():
                    output = model(test_input)
                    probs = torch.nn.functional.softmax(output, dim=1)
                    results.append(probs.cpu().numpy()[0])
                    current_app.logger.info(f"Test input {i+1} - Raw output: {output.cpu().numpy()[0]}, Probabilities: {probs.cpu().numpy()[0]}")
            
            # Check if model is giving varied outputs (not stuck)
            prob_variations = [abs(r[0] - r[1]) for r in results]
            if all(var < 0.01 for var in prob_variations):  # All outputs very similar
                current_app.logger.warning("Model may not be loaded correctly - all test outputs are very similar")
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Model validation failed: {str(e)}")
            raise
    
    def analyze_image(self, image_path, model_name='resnet_cbam'):
        """Analyze an image using the specified model"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not loaded")
        
        try:
            # Use the exact same preprocessing as training
            preprocess = transforms.Compose([
                transforms.Resize(256),           # Resize to 256x256
                transforms.CenterCrop(224),       # Center crop to 224x224
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                                   std=[0.229, 0.224, 0.225]),
            ])
            
            img = Image.open(image_path).convert('RGB')
            img_tensor = preprocess(img).unsqueeze(0).to(self.device)
            
            # Get prediction
            with torch.no_grad():
                outputs = self.models[model_name](img_tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                confidence, preds = torch.max(probabilities, 1)
                
                # Enhanced logging
                current_app.logger.info(f"Image analysis - Raw outputs: {outputs.cpu().numpy()[0]}")
                current_app.logger.info(f"Probabilities: {probabilities.cpu().numpy()[0]}")
                current_app.logger.info(f"Predicted class: {preds.item()}, Confidence: {confidence.item()}")
            
            # Remove the problematic threshold logic - trust the model's prediction
            predicted_class = preds.item()
            class_names = ['benign', 'malignant']
            
            # Get individual class probabilities
            benign_prob = probabilities[0][0].item()
            malignant_prob = probabilities[0][1].item()
            
            return {
                'classification': class_names[predicted_class],
                'confidence': confidence.item(),
                'model_used': model_name,
                'probabilities': {
                    'benign': benign_prob,
                    'malignant': malignant_prob
                },
                'raw_probabilities': probabilities.tolist()[0],
                'predicted_class_index': predicted_class
            }
            
        except Exception as e:
            current_app.logger.error(f"Error analyzing image: {str(e)}")
            raise

    def get_model_info(self, model_name='resnet_cbam'):
        """Get information about the loaded model"""
        if model_name not in self.models:
            return {"error": "Model not loaded"}
        
        model = self.models[model_name]
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        
        return {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'device': str(self.device),
            'model_loaded': True
        }
        


# Singleton instance
ai_service = AIModelService()
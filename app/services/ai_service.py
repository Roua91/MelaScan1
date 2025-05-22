import os
import torch
from PIL import Image
from torchvision import transforms
from flask import current_app

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
            model_path = os.path.join(self.app.root_path, self.app.config['RESNET_CBAM_PATH'])

            from app.modelai.resnet_cbam import ResNetCBAM
            model = ResNetCBAM(num_classes=2)

            # Load original state_dict
            raw_state_dict = torch.load(model_path, map_location=self.device)

            # Fix key names: change "resnet." to "base_model."
            new_state_dict = {}
            for k, v in raw_state_dict.items():
                if k.startswith("resnet."):
                    new_key = "base_model." + k[len("resnet."):]
                else:
                    new_key = k
                new_state_dict[new_key] = v

            # Get current model's state dict
            model_dict = model.state_dict()

            # 1. Filter out unnecessary keys
            pretrained_dict = {k: v for k, v in new_state_dict.items() 
                            if k in model_dict and v.size() == model_dict[k].size()}
            
            # 2. Print which keys are being loaded/ignored (for debugging)
            ignored_keys = [k for k in new_state_dict.keys() if k not in pretrained_dict]
            if ignored_keys:
                current_app.logger.warning(f"Ignored keys from checkpoint: {ignored_keys}")
            
            missing_keys = [k for k in model_dict.keys() if k not in pretrained_dict and not k.startswith('fc.')]
            if missing_keys:
                current_app.logger.warning(f"Missing keys in checkpoint: {missing_keys}")

            # 3. Update the model's state dict with compatible weights
            model_dict.update(pretrained_dict)
            
            # 4. Load with strict=False to handle missing/unexpected keys
            model.load_state_dict(model_dict, strict=False)
            
            model.eval()
            model.to(self.device)

            self.models['resnet_cbam'] = model
            current_app.logger.info("ResNet CBAM loaded successfully with partial weights")

        except Exception as e:
            current_app.logger.error(f"Model loading failed: {str(e)}")
            raise


    
    def analyze_image(self, image_path, model_name='resnet_cbam'):
        """Analyze an image using the specified model"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not loaded")
        
        try:
            # Preprocess image
            preprocess = transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
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
                
            return {
                'classification': 'malignant' if preds.item() == 1 else 'benign',
                'confidence': confidence.item(),
                'model_used': model_name
            }
            
        except Exception as e:
            current_app.logger.error(f"Error analyzing image: {str(e)}")
            raise

# Singleton instance
ai_service = AIModelService()
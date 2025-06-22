import torch
import torch.nn as nn
from torchvision.models import resnet50, ResNet50_Weights
import os  

class MelanomaResNet(nn.Module):
    def __init__(self, dropout_rate=0.3, weights_path=None):
        super(MelanomaResNet, self).__init__()
        self.weights_loaded = False
        
        # Load ResNet50 with pretrained weights if no custom weights provided
        if weights_path is None:
            self.base_model = resnet50(weights=ResNet50_Weights.DEFAULT)
        else:
            self.base_model = resnet50(weights=None)  # No pretrained weights
            
        # Replace the final fully connected layer for binary classification
        num_features = self.base_model.fc.in_features
        self.base_model.fc = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(num_features, 1)  # Binary classification
        )  
        
        # Load custom weights if provided
        if weights_path is not None:
            self.load_custom_weights(weights_path)
    
    def forward(self, x):
        return self.base_model(x)
    
    def load_custom_weights(self, weights_path):
        """Load custom trained weights"""
        try:
            # Resolve relative paths
            if not os.path.isabs(weights_path):
                weights_path = os.path.abspath(weights_path)
                
            # Check if weights file exists
            if not os.path.exists(weights_path):
                print(f"Weights file not found at: {weights_path}")
                return False
                
            state_dict = torch.load(weights_path, map_location='cpu')
            
            # Handle potential key mismatches
            model_dict = self.state_dict()
            filtered_state_dict = {}
            
            for k, v in state_dict.items():
                if k in model_dict and v.shape == model_dict[k].shape:
                    filtered_state_dict[k] = v
            
            model_dict.update(filtered_state_dict)
            self.load_state_dict(model_dict)
            self.weights_loaded = True
            print(f"Successfully loaded {len(filtered_state_dict)} weight tensors")
            return True
        except Exception as e:
            print(f"Error loading weights: {str(e)}")
            return False
    
    def unfreeze_layers(self, num_layers=2):
        """Unfreeze the last num_layers for fine-tuning"""
        # Freeze all layers first
        for param in self.base_model.parameters():
            param.requires_grad = False
            
        # Unfreeze the last layers
        children = list(self.base_model.children())
        for child in children[-num_layers:]:
            for param in child.parameters():
                param.requires_grad = True
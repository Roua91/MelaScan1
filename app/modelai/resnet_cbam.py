import torch
import torch.nn as nn
from torchvision.models import resnet50
from torchvision.models.resnet import Bottleneck

class CBAM(nn.Module):
    def __init__(self, in_channels, reduction=16, kernel_size=7):
        super(CBAM, self).__init__()
        
        # Channel Attention
        self.channel_attention = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_channels, in_channels // reduction, 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels // reduction, in_channels, 1, bias=False),
            nn.Sigmoid()
        )
        
        # Spatial Attention
        self.spatial_attention = nn.Sequential(
            nn.Conv2d(2, 1, kernel_size, padding=kernel_size//2, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        # Channel Attention
        ca = self.channel_attention(x)
        ca_out = ca * x
        
        # Spatial Attention
        avg_out = torch.mean(ca_out, dim=1, keepdim=True)
        max_out, _ = torch.max(ca_out, dim=1, keepdim=True)
        combined = torch.cat([avg_out, max_out], dim=1)
        sa = self.spatial_attention(combined)
        sa_out = sa * ca_out
        
        return sa_out

class BottleneckWithCBAM(Bottleneck):
    def __init__(self, inplanes, planes, stride=1, downsample=None, **kwargs):
        # Handle different PyTorch versions
        if 'groups' in Bottleneck.__init__.__code__.co_varnames:
            super(BottleneckWithCBAM, self).__init__(
                inplanes, planes, stride, downsample, **kwargs)
        else:
            # For older PyTorch versions
            super(BottleneckWithCBAM, self).__init__(
                inplanes, planes, stride, downsample)
        
        # Add CBAM after the third convolution
        self.cbam = CBAM(planes * self.expansion)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        # Apply CBAM attention
        out = self.cbam(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out

def create_resnet50_cbam_selective(num_classes=2, pretrained=True):
    """
    Creates ResNet50 with CBAM ONLY in the first block of each layer
    (Compatible with multiple PyTorch versions)
    """
    # Load base ResNet50
    if pretrained:
        model = resnet50(weights='IMAGENET1K_V1')
    else:
        model = resnet50(weights=None)
    
    # Replace ONLY the first block of each layer with CBAM version
    
    # Layer 1 - Replace block 0 only
    original_block = model.layer1[0]
    model.layer1[0] = BottleneckWithCBAM(
        inplanes=64,
        planes=64,
        stride=1,
        downsample=original_block.downsample
    )
    
    # Layer 2 - Replace block 0 only  
    original_block = model.layer2[0]
    model.layer2[0] = BottleneckWithCBAM(
        inplanes=256,
        planes=128,
        stride=2,
        downsample=original_block.downsample
    )
    
    # Layer 3 - Replace block 0 only
    original_block = model.layer3[0]
    model.layer3[0] = BottleneckWithCBAM(
        inplanes=512,
        planes=256,
        stride=2,
        downsample=original_block.downsample
    )
    
    # Layer 4 - Replace block 0 only
    original_block = model.layer4[0]
    model.layer4[0] = BottleneckWithCBAM(
        inplanes=1024,
        planes=512,
        stride=2,
        downsample=original_block.downsample
    )
    
    # Replace the final classifier
    model.fc = nn.Linear(2048, num_classes)
    
    return model

class ResNetCBAMSelective(nn.Module):
    """
    ResNet50 with CBAM matching your exact trained architecture
    (CBAM only in first block of each layer)
    """
    def __init__(self, num_classes=2, pretrained=True):
        super(ResNetCBAMSelective, self).__init__()
        self.model = create_resnet50_cbam_selective(
            num_classes=num_classes,
            pretrained=pretrained
        )
    
    def forward(self, x):
        return self.model(x)

def load_model_weights(model, weight_path, device='cpu'):
    """
    Robust weight loading with version compatibility
    """
    try:
        checkpoint = torch.load(weight_path, map_location=device)
        
        # Handle different checkpoint formats
        if isinstance(checkpoint, dict):
            state_dict = checkpoint.get('model_state_dict', checkpoint.get('state_dict', checkpoint))
        else:
            state_dict = checkpoint
        
        # Clean state dict keys
        cleaned_state_dict = {}
        for k, v in state_dict.items():
            name = k.replace('module.', '')  # Remove DataParallel prefix
            cleaned_state_dict[name] = v
        
        # Load with strict=False to handle partial matches
        model.load_state_dict(cleaned_state_dict, strict=False)
        return True
        
    except Exception as e:
        print(f"Error loading weights: {str(e)}")
        return False
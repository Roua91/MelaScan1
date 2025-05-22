import torch
import torch.nn as nn
from torchvision.models.resnet import Bottleneck, resnet50

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
    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None):
        super(BottleneckWithCBAM, self).__init__(
            inplanes, planes, stride, downsample, groups, 
            base_width, dilation, norm_layer)
        
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

class ResNetCBAM(nn.Module):
    def __init__(self, num_classes=2, pretrained=True):
        super(ResNetCBAM, self).__init__()
        
        # Load base ResNet50
        self.base_model = resnet50(pretrained=pretrained)
        
        # Replace only the first bottleneck block in each layer with CBAM version
        self._replace_first_bottleneck_with_cbam()
        
        # Modify final layer
        in_features = self.base_model.fc.in_features
        self.base_model.fc = nn.Linear(in_features, num_classes)

    def _replace_first_bottleneck_with_cbam(self):
        """Replace only the first bottleneck block in each layer with CBAM version"""
        layers = {
            'layer1': (64, self.base_model.layer1[0].stride, self.base_model.layer1[0].downsample),
            'layer2': (128, self.base_model.layer2[0].stride, self.base_model.layer2[0].downsample),
            'layer3': (256, self.base_model.layer3[0].stride, self.base_model.layer3[0].downsample),
            'layer4': (512, self.base_model.layer4[0].stride, self.base_model.layer4[0].downsample)
        }
        
        # Get the original first block from each layer
        original_blocks = {
            'layer1': self.base_model.layer1[0],
            'layer2': self.base_model.layer2[0],
            'layer3': self.base_model.layer3[0],
            'layer4': self.base_model.layer4[0]
        }
        
        # Replace with CBAM versions
        self.base_model.layer1[0] = BottleneckWithCBAM(
            original_blocks['layer1'].conv1.in_channels,
            layers['layer1'][0],
            stride=layers['layer1'][1],
            downsample=layers['layer1'][2]
        )
        
        self.base_model.layer2[0] = BottleneckWithCBAM(
            original_blocks['layer2'].conv1.in_channels,
            layers['layer2'][0],
            stride=layers['layer2'][1],
            downsample=layers['layer2'][2]
        )
        
        self.base_model.layer3[0] = BottleneckWithCBAM(
            original_blocks['layer3'].conv1.in_channels,
            layers['layer3'][0],
            stride=layers['layer3'][1],
            downsample=layers['layer3'][2]
        )
        
        self.base_model.layer4[0] = BottleneckWithCBAM(
            original_blocks['layer4'].conv1.in_channels,
            layers['layer4'][0],
            stride=layers['layer4'][1],
            downsample=layers['layer4'][2]
        )

    def forward(self, x):
        return self.base_model(x)
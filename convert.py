from torch.autograd import Variable

import torch

 

from net import *

 

model = MobileNetV3()

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

model = model.to(device)

model.eval()

 

 

PATH="detection.pth"

 

checkpoint = torch.load(PATH,map_location=device)

model.load_state_dict(checkpoint['model_state_dict'])

input_names = ["input0"]

output_names = ["output0"]

 

dummy_input = Variable(torch.randn(1, 3, 224, 224))

torch.onnx.export(model, dummy_input, "model_classfication.onnx", input_names=input_names, output_names=output_names)

 
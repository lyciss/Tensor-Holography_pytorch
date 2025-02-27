from numpy.fft import fftshift
from torchvision.transforms.transforms import Lambda
import torch, gc
import torch.nn as nn
import torch.optim as optim
import numpy as np
import cv2
import os, glob
import time
from PIL import Image
import torchvision.transforms as transforms
from models import TensorHoloModel
import random
import torch.backends.cudnn as cudnn
import imageio

gc.collect()
torch.cuda.empty_cache()

torch.manual_seed(0)
torch.cuda.manual_seed(0)
torch.cuda.manual_seed_all(0)
np.random.seed(0)
cudnn.benchmark = False
cudnn.deterministic = True
random.seed(0)

nm = 1e-9
um = 1e-6
mm = 1e-3
cm = 1e-2

TRAIN_RGB_DIR="E:/datasets/tensorholography/data/"
TRAIN_DPT_DIR="E:/datasets/tensorholography/data/"
TRAIN_AMP_DIR="E:/datasets/tensorholography/data/train_384/amp/" + "*.exr"
TRAIN_PHS_DIR="E:/datasets/tensorholography/data/train_384/phs/" + "*.exr"
TRAIN_LENGTH=3800

TEST_RGB_DIR="E:/datasets/tensorholography/data/test_384/img/*.exr"
TEST_DPT_DIR="E:/datasets/tensorholography/data/test_384/img/*.exr"
TEST_AMP_DIR="E:/datasets/tensorholography/data/test_384/img/*.exr"
TEST_PHS_DIR="E:/datasets/tensorholography/data/test_384/img/*.exr"
TEST_LENGTH=200

CKPT_DIR="C:/Users/lycis/Desktop/git/Tensor-Holography_pytorch/ckpt/"
RESULTS_DIR="E:/datasets/tensorholography/data/"

EVAL_RGB="C:/python/HOLOGRAM/data/eval/rgb.exr"
EVAL_DPT="C:/python/HOLOGRAM/data/eval/dpt.exr"

BATCH_SIZE=20
EPOCH=1001

TEST_CKPT_NAME='tensorholo.pt'

def rgb_file_list(is_test):
    if is_test==True:
        typ='test'
        num1=TRAIN_LENGTH
        num2=TRAIN_LENGTH+TEST_LENGTH
    else:
        typ='train'
        num1=0
        num2=TRAIN_LENGTH
    rgb_list=list()
    for img_idx in range(num1, num2):
        rgb_path=TRAIN_RGB_DIR+typ+'_384'+'/img/'+str("%04d" % img_idx)+'.exr'
        rgb_list.append(rgb_path)
    return rgb_list

def dpt_file_list(is_test):
    if is_test==True:
        typ='test'
        num1=TRAIN_LENGTH
        num2=TRAIN_LENGTH+TEST_LENGTH
    else:
        typ='train'
        num1=0
        num2=TRAIN_LENGTH
    dpt_list=list()
    for img_idx in range(num1, num2):
        dpt_path=TRAIN_RGB_DIR+typ+'_384'+'/depth/'+str("%04d" % img_idx)+'.exr'
        dpt_list.append(dpt_path)
    return dpt_list

def amp_file_list(is_test):
    if is_test==True:
        typ='test'
        num1=TRAIN_LENGTH
        num2=TRAIN_LENGTH+TEST_LENGTH
    else:
        typ='train'
        num1=0
        num2=TRAIN_LENGTH
    amp_list=list()
    for img_idx in range(num1, num2):
        amp_path=TRAIN_RGB_DIR+typ+'_384'+'/amp/'+str("%04d" % img_idx)+'.exr'
        amp_list.append(amp_path)
    return amp_list

def phs_file_list(is_test):
    if is_test==True:
        typ='test'
        num1=TRAIN_LENGTH
        num2=TRAIN_LENGTH+TEST_LENGTH
    else:
        typ='train'
        num1=0
        num2=TRAIN_LENGTH
    phs_list=list()
    for img_idx in range(num1, num2):
        phs_path=TRAIN_RGB_DIR+typ+'_384'+'/phs/'+str("%04d" % img_idx)+'.exr'
        phs_list.append(phs_path)
    return phs_list    

class ImageTransform():
    def __init__(self, mean, std):
        self.data_transform=transforms.Compose([transforms.ToTensor(), transforms.Normalize(mean, std)])
    
    def __call__(self, img):
        return self.data_transform(img)

class TensorHoloDataset(torch.utils.data.Dataset):
    def __init__(self, rgb_list, dpt_list, amp_list, phs_list, transform):
        self.rgb_list=rgb_list
        self.dpt_list=dpt_list
        self.amp_list=amp_list
        self.phs_list=phs_list
        self.transform=transform
        #self.transform=None

    def __len__(self):
        return len(self.rgb_list)
    
    def __getitem__(self, index):
        rgb_path=self.rgb_list[index]
        #rgb=Image.open(rgb_path)
        rgb=imageio.v3.imread(rgb_path)
        rgb=rgb.squeeze(0)
        #rgb=rgb.convert("RGB")
        #rgb=cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
        #rgb=np.asarray(rgb, dtype=np.uint8)
        #rgb=Image.open(rgb)
        '''
        rr=rgb.copy()
        rr[:,:,1]=0
        rr[:,:,2]=0
        rr=self.transform(rr)
        '''
        rgb=self.transform(rgb)

        dpt_path=self.dpt_list[index]
        #dpt=Image.open(dpt_path)
        dpt=imageio.v3.imread(dpt_path)
        dpt = dpt.squeeze(0)
        dpt = dpt[..., 0]
        #dpt=cv2.cvtColor(dpt, cv2.COLOR_BGR2GRAY)
        dpt=self.transform(dpt)


        amp_path=self.amp_list[index]
        #amp=Image.open(amp_path)
        amp=imageio.v3.imread(amp_path)
        amp = amp.squeeze(0)


        #amp=amp.convert("RGB")
        #amp=cv2.cvtColor(amp, cv2.COLOR_BGR2RGB)
        '''
        ar=amp.copy()
        #ar=np.asarray(ar, dtype=np.uint8)
        ar[:,:,1]=0
        ar[:,:,2]=0
        ar=self.transform(ar)
        '''
        amp=self.transform(amp)

        phs_path=self.phs_list[index]
        #phs=Image.open(phs_path)
        phs=imageio.v3.imread(phs_path)
        phs = phs.squeeze(0)

        #phs=phs.convert("RGB")
        #phs=cv2.cvtColor(phs, cv2.COLOR_BGR2RGB)
        '''
        pr=phs.copy()
        #pr=np.asarray(pr, dtype=np.uint8)
        pr[:,:,1]=0
        pr[:,:,2]=0
        pr=self.transform(pr)
        '''
        phs=self.transform(phs)
        
        #return rr, dpt, ar, pr
        return rgb, dpt, amp, phs

def rescale(cgh):
    min_cgh = np.min(cgh)
    max_cgh = np.max(cgh)

    cgh = (cgh - min_cgh) / (max_cgh - min_cgh)
    return cgh

device='cuda'

net=TensorHoloModel()
net=net.to(device)
net=torch.nn.DataParallel(net)

learning_rate=1e-3
filename='tensorholo.pt'

criterion = nn.MSELoss()
optimizer=optim.Adam(net.parameters(), lr=learning_rate, betas=(0.9, 0.999), eps=1e-08)

rgb_list=rgb_file_list(is_test=False)
dpt_list=dpt_file_list(is_test=False)
amp_list=amp_file_list(is_test=False)
phs_list=phs_file_list(is_test=False)
'''
dataset=TensorHoloDataset(rgb_list=rgb_list, dpt_list=dpt_list, amp_list=amp_list, phs_list=phs_list, transform=transforms.Compose([transforms.ToTensor()]))
loader=torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
meanRGB=[np.mean(x.numpy(), axis=(1,2)) for x, _ in loader]
mean=np.mean([m[0] for m in meanRGB])
print(mean)
mean=dataset.mean(axis=(0,1,2))
std=dataset.std(axis=(0,1,2))

mean=mean/255.0
std=std/255.0

print(mean)
print(std)
'''
def train(epoch):
    train_dataset=TensorHoloDataset(rgb_list=rgb_list, dpt_list=dpt_list, amp_list=amp_list, phs_list=phs_list, transform=transforms.Compose([transforms.ToTensor()]))

    train_loader=torch.utils.data.DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

    print('\n[ Train Epoch: %d ]'%epoch)
    net.train()
    train_loss=0

    for batch_idx, (train_rgb, train_dpt, train_amp, train_phs) in enumerate(train_loader):
        train_rgb=train_rgb.to(device)
        train_dpt=train_dpt.to(device)
        train_amp=train_amp.to(device)
        train_phs=train_phs.to(device)
        optimizer.zero_grad()

        output_amp, output_phs=net(train_rgb, train_dpt)

        #'''
        loss_amp = criterion(output_amp, train_amp)
        loss_phs =criterion(output_phs, train_phs)
        loss=loss_amp+loss_phs

        loss.backward()

        optimizer.step()
        train_loss+=loss.item()

        if batch_idx %10==0:
            print('Current batch:', str(batch_idx))
            print('Current train loss:', loss.item())
    print('Total train loss:', train_loss/TRAIN_LENGTH) # 800 -> len(train data)
    state={
        "epoch": epoch+1,
        "model_state_dict":net.state_dict(), 
        "optimizer_state_dict": optimizer.state_dict(),
        "global_step": global_step,
    }
    if not os.path.isdir('ckpt'):
        os.mkdir('ckpt')
    torch.save(state, './ckpt/'+filename)
    print('Model Saved!')

def test(epoch):
    rgb_list=rgb_file_list(is_test=True)
    dpt_list=dpt_file_list(is_test=True)
    amp_list=amp_file_list(is_test=True)
    phs_list=phs_file_list(is_test=True)
    
    test_dataset=TensorHoloDataset(rgb_list=rgb_list, dpt_list=dpt_list, amp_list=amp_list, phs_list=phs_list, transform=transforms.Compose([transforms.ToTensor()]))
    test_loader=torch.utils.data.DataLoader(test_dataset, batch_size=1, shuffle=False)
    print('\n[ Test Epoch: %d ]'%epoch)
    time0=time.time()
    
    net.eval()
    test_loss=0

    for batch_idx, (test_rgb, test_dpt, test_amp, test_phs) in enumerate(test_loader):

        test_rgb=test_rgb.to(device).float()
        test_dpt=test_dpt.to(device).float()
        test_amp=test_amp.to(device).float()
        test_phs=test_phs.to(device).float()

        output_amp, output_phs=net(test_rgb, test_dpt)
        #'''
        loss_amp2=criterion(output_amp, test_amp)
        loss_phs2=criterion(output_phs, test_phs)
        loss2=loss_amp2+loss_phs2
        test_loss+=loss2.item()
        #'''
        '''
        delta=torch.atan2(torch.sin(output_phs-test_phs), torch.cos(output_phs-test_phs))
        criterion1=output_amp-test_amp*torch.exp(1j*(delta-delta.conj()))
        criterion1=torch.linalg.norm(criterion1, ord=2, dim=2)
        loss=torch.sqrt(torch.sum(criterion1**2))
        test_loss=loss.backward()
        '''
        output_amp = output_amp.detach().cpu().numpy()
        output_phs = output_phs.detach().cpu().numpy()

        output_amp=np.transpose(output_amp[0,:,:,:], [1,2,0])
        output_amp=cv2.cvtColor(output_amp, cv2.COLOR_BGR2RGB)
        output_phs=np.transpose(output_phs[0,:,:,:], [1,2,0])
        output_phs=cv2.cvtColor(output_phs, cv2.COLOR_BGR2RGB)

        cv2.imwrite(os.path.join(RESULTS_DIR, 'amp_%d.bmp'%(TRAIN_LENGTH+batch_idx)), output_amp*255.0)
        cv2.imwrite(os.path.join(RESULTS_DIR, 'phs_%d.bmp'%(TRAIN_LENGTH+batch_idx)), output_phs*255.0)
    dt=time.time()-time0
    print('Test Average Loss: ', test_loss/TEST_LENGTH) # 200 -> len(test data)
    print('iter time {:0.5f}'.format(dt))

    

def adjust_learning_rate(optimizer, epoch):
    lr = learning_rate
    '''
    if epoch >= 100:
        lr /= 10
    if epoch >= 150:
        lr /= 10
    '''
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr

if __name__=='__main__':
    
    # load checkpoint
    if os.path.isfile(CKPT_DIR + TEST_CKPT_NAME):
        print("Loading Checkpoint")
        checkpoint = torch.load(CKPT_DIR + TEST_CKPT_NAME)
        net.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_epoch = checkpoint["epoch"]
        global_step = checkpoint["global_step"]
    else:
        print("No checkpoint, start form the zero")
        start_epoch = 0
        global_step = 0

    if start_epoch==EPOCH:
        test(start_epoch)

    for epoch in range(start_epoch, EPOCH):
        adjust_learning_rate(optimizer, epoch)
        train(epoch)
        if epoch%10==0:
            test(epoch)
    
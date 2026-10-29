"""Serializable 48-hour LSTM adapter. PyTorch loads only when this model is used."""
import numpy as np
class LSTMForecast:
    def __init__(self, epochs=10, batch_size=32, seed=42):
        self.epochs,self.batch_size,self.seed=epochs,batch_size,seed
    def get_params(self):return vars(self) | {'architecture':'LSTM(64), Dropout(0.2), Dense(32), Dense(48)'}
    def network(self):
        import torch
        class Net(torch.nn.Module):
            def __init__(self):
                super().__init__();self.rnn=torch.nn.LSTM(1,64,batch_first=True);self.head=torch.nn.Sequential(torch.nn.Dropout(.2),torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Linear(32,48))
            def forward(self,x):return self.head(self.rnn(x)[0][:,-1])
        return Net()
    def fit(self,X,y):
        import torch
        torch.set_num_threads(2);torch.manual_seed(self.seed)
        histories=X[::48,:48][:,::-1].copy();targets=y.reshape(-1,48)
        self.mean=float(histories.mean());self.scale=float(histories.std()) or 1.
        a=torch.tensor((histories-self.mean)/self.scale,dtype=torch.float32).unsqueeze(-1)
        b=torch.tensor((targets-self.mean)/self.scale,dtype=torch.float32)
        net=self.network();optimizer=torch.optim.Adam(net.parameters());self.loss_history=[]
        for epoch in range(self.epochs):
            net.train();order=torch.randperm(len(a));total=0.
            for ids in order.split(self.batch_size):
                optimizer.zero_grad();loss=torch.nn.functional.mse_loss(net(a[ids]),b[ids]);loss.backward();optimizer.step();total+=loss.item()*len(ids)
            self.loss_history.append(total/len(a))
        self.weights={k:v.detach().numpy() for k,v in net.state_dict().items()};return self
    def predict(self,X):
        import torch
        torch.set_num_threads(2);net=self.network();net.load_state_dict({k:torch.tensor(v) for k,v in self.weights.items()});net.eval()
        histories,ids=np.unique(X[:,:48],axis=0,return_inverse=True)
        with torch.no_grad():
            a=torch.tensor((histories[:,::-1].copy()-self.mean)/self.scale,dtype=torch.float32).unsqueeze(-1)
            p=np.concatenate([net(part).numpy() for part in a.split(256)])*self.scale+self.mean
        return p[ids,X[:,51].astype(int)-1]

import numpy as np
import tensorflow as tf
import matplotlib.image as mping
import matplotlib.pyplot as plt
import pickle
import os
from sklearn.metrics import f1_score
from scipy.io import loadmat
from os.path import isfile, join
from helper_functions import weight_variable, bias_variable, conv2d, max_pool_2x2, get_train_batch, get_valid_test_set
from helper_functions import Compute_F1score, Compute_F1score_au
from AU_Knowledge_part_new import CNN_AUdetection_joint, Loss_KnowledgeModel_joint, Loss_KnowledgeModel_gtExpOnly_joint
from Update_Posterior import posterior_entropy, posterior_summation, Exp_KnowledgeModel_joint
from ThirdModel_part import Loss_3rdModel, Prediction_3rdModel_joint
from ImportGraph import ImportRightAU, ImportRightExp
#from Ipython.display import Image, display
import itertools
import scipy.io as sio

os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID'
os.environ['CUDA_VISIBLE_DEVICES'] = '2'  #(e.g. it will use GPU’s number 0 and 2.)

#training, testing index
pickleFolder = os.path.join( os.getcwd(), 'data_pickle') 
#pickle_in = open( os.path.join( pickleFolder, '3fold-image-serverpath.p'), "rb" )

#fold1_path, fold2_path, fold3_path = pickle.load(pickle_in)
data = sio.loadmat(os.path.join( pickleFolder,'BP4D_Apex_11AU.mat'))
index = data['BP4D_Apex_11AU']
sub_name = index[0,0]['SUB']
task_name = index[0,0]['TASK']
image_name = index[0,0]['IMGIND']
label_exp = index[0,0]['EXP']
label_AU = index[0,0]['AU']
path_all=[]
for i in range(sub_name.shape[0]):
    if sub_name[i] // 1000 == 1:
#        path = ["E:/BP4D_data/color_64/F%03d_"%(sub_name[i]%1000)+"T%d_"%(task_name[i])+"%04d.jpg"%(image_name[i])]
        path = ["/training_data/zijun/color_64/F%03d_"%(sub_name[i]%1000)+"T%d_"%(task_name[i])+"%04d.jpg"%(image_name[i])]
    if sub_name[i] // 1000 == 2:
#        path = ["E:/BP4D_data/color_64/M%03d_"%(sub_name[i]%1000)+"T%d_"%(task_name[i])+"%04d.jpg"%(image_name[i])]
        path = ["/training_data/zijun/color_64/M%03d_"%(sub_name[i]%1000)+"T%d_"%(task_name[i])+"%04d.jpg"%(image_name[i])]
    if i == 0:
        path_all=path
    else:
        path_all=path_all + path

fold1_index=path_all[0:248]
fold2_index=path_all[248:492]
fold3_index=path_all[492:732]
fold1_label=np.concatenate((label_exp[0:248], label_AU[0:248, :] - 1), axis = 1)
fold2_label=np.concatenate((label_exp[248:492], label_AU[248:492, :] -1), axis = 1)
fold3_label=np.concatenate((label_exp[492:732], label_AU[492:732, :] -1), axis = 1)

def main(train1_index, train2_index, test_index, train1_label, train2_label, test_label, title_string_au, title_string):
    trainD_path = list(itertools.chain(train1_index, train2_index))
    testD_path = test_index
    
    trainL = np.concatenate((train1_label, train2_label), axis=0)
    testL = test_label
    
    pickleFolder = os.path.join( os.getcwd(), 'data_pickle') 
    pickle_in = open( os.path.join( pickleFolder, 'list_AU_config.p'), "rb" )
    load_AUconfig = pickle.load(pickle_in)
    #
    pickle_in = open( os.path.join( pickleFolder, 'PGM_p-K2-Bayes.p'), "rb" )
    load_PGM_pExp, load_PGM_pAUconfig = pickle.load(pickle_in)
    
    
    batch_size = 50
    epo = 30
    LR = 0.0001
    
    perf_3rd_training = []
    perf_3rd_testing = []
    
    perf_K_training = []
    perf_K_testing = []
    
    total_samples = len(trainD_path)
    
    define_rightexp_file_name = 'define_right_exp'
    model_folder = os.path.join(os.path.join(os.getcwd()), 'Models')
    define_rightexp_path = os.path.join(model_folder, define_rightexp_file_name)
    
    AU_model_name = title_string_au[:-2]
    AUmodel_path = os.path.join(model_folder, AU_model_name)
    right_AU_model = ImportRightAU(AUmodel_path)
    
    right_Exp_model = ImportRightExp(define_rightexp_path)
    
    for e in range(epo): #each epo go over all samples
        print('--------------epo--------------%d' %e)
        #training iteration
        start_idx = np.arange(0, total_samples, batch_size)
        for i in range(len(start_idx)): 
            
            index = start_idx[i]
            train_image, train_explabel, train_AUlabel, train_AUprob = get_train_batch(batch_size, trainD_path, trainL, load_PGM_pAUconfig, index)
            
            np_p_au, _, _ = right_AU_model.run(train_image, train_AUprob, load_AUconfig) 
            
            right_Exp_model.train(np_p_au, train_explabel, LR, load_PGM_pExp)
            
            
        #training for each epo
        start_idx_train = np.arange(0, len(trainD_path), 300)
        for ti in range(len(start_idx_train)): 
            train_image, train_explabel, train_AUlabel, train_AUprob = get_train_batch(300, trainD_path, trainL, load_PGM_pAUconfig, start_idx_train[ti])
            
            np_p_au, _, _ = right_AU_model.run(train_image, train_AUprob, load_AUconfig)
            
            _, temp_pred_K, _, temp_pred_3rd, temp_loss_3rd = right_Exp_model.run(np_p_au, train_explabel, load_PGM_pExp)
            
            if ti==0:
                train_loss_3rd_b = np.expand_dims(temp_loss_3rd, axis=0)
                train_pred_3rd_b = temp_pred_3rd
                train_pred_K_b = temp_pred_K
            else:
                train_loss_3rd_b = np.concatenate((train_loss_3rd_b, np.expand_dims(temp_loss_3rd, axis=0)), axis=0)
                train_pred_3rd_b = np.concatenate((train_pred_3rd_b, temp_pred_3rd), axis=0)
                train_pred_K_b = np.concatenate((train_pred_K_b, temp_pred_K), axis=0)
    
        np_acc_train_exp_3rd =  (np.ravel(trainL[:,0]-1)== train_pred_3rd_b).sum()/len(trainL)
        np_f1_train_exp_3rd = Compute_F1score(trainL[:,0]-1, train_pred_3rd_b)
        np_acc_train_exp_K = (np.ravel(trainL[:,0]-1)== train_pred_K_b).sum()/len(trainL)
        np_f1_train_exp_K = Compute_F1score(trainL[:,0]-1, train_pred_K_b)
        perf_3rd_training.append([np.mean(train_loss_3rd_b), np_acc_train_exp_3rd, np_f1_train_exp_3rd])
        perf_K_training.append([np_acc_train_exp_K, np_f1_train_exp_K])
        
        print('training')
        print('3rd model loss || acc || f1')
        print(np.mean(train_loss_3rd_b), np_acc_train_exp_3rd, np_f1_train_exp_3rd)
        print(' ')
        print('PGM model acc || f1')
        print(np_acc_train_exp_K, np_f1_train_exp_K)
        print(' ')
        
        #testing for each epo
        start_idx_test = np.arange(0, len(testD_path), 300)
        for ti in range(len(start_idx_test)): 
            test_image, test_explabel, test_AUlabel, test_AUprob = get_train_batch(300, testD_path, testL, load_PGM_pAUconfig, start_idx_test[ti])
            
            np_p_au, _, _ = right_AU_model.run(test_image, test_AUprob, load_AUconfig)
            
            _, temp_pred_K, _, temp_pred_3rd, temp_loss_3rd = right_Exp_model.run(np_p_au, test_explabel, load_PGM_pExp)
            
            if ti==0:
                test_loss_3rd_b = np.expand_dims(temp_loss_3rd, axis=0)
                test_pred_3rd_b = temp_pred_3rd
                test_pred_K_b = temp_pred_K
            else:
                test_loss_3rd_b = np.concatenate((test_loss_3rd_b, np.expand_dims(temp_loss_3rd, axis=0)), axis=0)
                test_pred_3rd_b = np.concatenate((test_pred_3rd_b, temp_pred_3rd), axis=0)
                test_pred_K_b = np.concatenate((test_pred_K_b, temp_pred_K), axis=0)
        
        np_acc_test_exp_3rd =  (np.ravel(testL[:,0]-1)== test_pred_3rd_b).sum()/len(testL)
        np_f1_test_exp_3rd = Compute_F1score(testL[:,0]-1, test_pred_3rd_b)
        np_acc_test_exp_K = (np.ravel(testL[:,0]-1)== test_pred_K_b).sum()/len(testL)
        np_f1_test_exp_K = Compute_F1score(testL[:,0]-1, test_pred_K_b)
        perf_3rd_testing.append([np.mean(test_loss_3rd_b), np_acc_test_exp_3rd, np_f1_test_exp_3rd])
        perf_K_testing.append([np_acc_test_exp_K, np_f1_test_exp_K])
        
        print('testing')
        print('3rd model loss')
        print(np.mean(test_loss_3rd_b), np_acc_test_exp_3rd, np_f1_test_exp_3rd)
        print(' ')
        print('PGM model acc || f1')
        print(np_acc_test_exp_K, np_f1_test_exp_K)
        print(' ')
        
    
    
    pickleFolder = os.path.join(os.getcwd())
    result_folder = os.path.join(pickleFolder, 'Results')
    
    pickle_out = open( os.path.join( result_folder, title_string), "wb" )
    pickle.dump([perf_3rd_training, perf_3rd_testing, perf_K_training, perf_K_testing], pickle_out)
    
    pickle_out.close()
    
    file_name = title_string[:-2]
    write_model_path = os.path.join(model_folder, file_name)
    right_Exp_model.save(define_rightexp_path, write_model_path)
    

name_string_au = 'initialAU-joint'
file1_au = [name_string_au + '-fold1.p'][0]
file2_au = [name_string_au + '-fold2.p'][0]
file3_au = [name_string_au + '-fold3.p'][0]

name_string = 'initialRightExp-joint'
file1 = [name_string + '-fold1.p'][0]
file2 = [name_string + '-fold2.p'][0]
file3 = [name_string + '-fold3.p'][0]
main(fold1_index, fold2_index, fold3_index, fold1_label, fold2_label, fold3_label, file1_au, file1)
main(fold1_index, fold3_index, fold2_index, fold1_label, fold3_label, fold2_label, file2_au, file2)
main(fold2_index, fold3_index, fold1_index, fold2_label, fold3_label, fold1_label, file3_au, file3)

pickleFolder = os.path.join( os.getcwd(), 'Results') 
pickle_in = open( os.path.join( pickleFolder, file1), "rb" )
perf_train_3rd1, perf_test_3rd1, perf_train_K1, perf_test_K1 = pickle.load(pickle_in)

pickle_in = open( os.path.join( pickleFolder, file2), "rb" )
perf_train_3rd2, perf_test_3rd2, perf_train_K2, perf_test_K2 = pickle.load(pickle_in)

pickle_in = open( os.path.join( pickleFolder, file3), "rb" )
perf_train_3rd3, perf_test_3rd3, perf_train_K3, perf_test_K3 = pickle.load(pickle_in)


idx1 = np.argmax(np.asarray(perf_test_3rd1)[:,1])
idx2 = np.argmax(np.asarray(perf_test_3rd2)[:,1])
idx3 = np.argmax(np.asarray(perf_test_3rd3)[:,1])

perf_train_3rd = [perf_train_3rd1[idx1], perf_train_3rd2[idx2], perf_train_3rd3[idx3]]
perf_test_3rd = [perf_test_3rd1[idx1], perf_test_3rd2[idx2], perf_test_3rd3[idx3]]

perf_train_K = [perf_train_K1[-1], perf_train_K2[-1], perf_train_K3[-1]]
perf_test_K = [perf_test_K1[-1], perf_test_K2[-1], perf_test_K3[-1]]

acc_3rd_train = np.mean(np.asarray(perf_train_3rd)[:,1])
f1_3rd_train = np.mean(np.asarray(perf_train_3rd)[:,2])
acc_3rd = np.mean(np.asarray(perf_test_3rd)[:,1])
f1_3rd = np.mean(np.asarray(perf_test_3rd)[:,2])

acc_K_train = np.mean(np.asarray(perf_train_K)[:,0])
f1_K_train = np.mean(np.asarray(perf_train_K)[:,1])
acc_K = np.mean(np.asarray(perf_test_K)[:,0])
f1_K = np.mean(np.asarray(perf_test_K)[:,1])

print("expression 3rd model training ACC:%f,F1:%f"%(acc_3rd_train, f1_3rd_train))
print(' ')
print("expression 3rd model testing ACC:%f,F1:%f"%(acc_3rd, f1_3rd))
print(' ')
print('expression PGM model training ACC:%f,F1:%f'%(acc_K_train, f1_K_train))
print(' ')
print('expression PGM model testing ACC:%f,F1:%f'%(acc_K, f1_K))

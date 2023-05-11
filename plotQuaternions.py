# -*- coding: utf-8 -*-
"""
Created on Tue May  2 15:48:41 2023

@author: limadou
"""

import numpy as np
import matplotlib.pyplot as plt

fileName = input("Inserire il nome del file: ")

suffix = fileName[fileName.find('-'):].replace('.dat','.png')

data = np.genfromtxt(fileName,delimiter=',')

canQuat = data[:,0:4]
comptQuat = data[:,4:8]
delta = data[:,8:12]

for i in range(4):
    plt.plot(canQuat[:,i],'r-',label="can quaternions")
    plt.plot(comptQuat[:,i],'b-',label="local quaternions")
    plt.legend(loc = 'upper right')
    plt.ylabel(f"Q{i}")
    
    plt.savefig(f"Q{i}{suffix}",bbox_inches='tight')
    
    plt.clf()
    
    plt.plot(delta[:,i],'r.')
    plt.ylabel(f"$\Delta$Q{i}")

    plt.savefig(f"deltaQ{i}{suffix}",bbox_inches='tight')
    
    plt.clf()

for i in range(4):
    plt.plot(canQuat[:,i],label=f"can Q{i}")
    plt.plot(comptQuat[:,i],label=f"local Q{i}")
    plt.legend(loc = 'upper right')
    plt.ylabel("Q All")
    
    plt.savefig(f"QAll{suffix}",bbox_inches='tight')
    
plt.clf()

for i in range(4):
    plt.plot(delta[:,i],label=f"$\Delta$Q{i}")
    plt.ylabel("$\Delta$Q All")
    plt.legend(loc = 'upper right')

    plt.savefig(f"sameDeltaQ{suffix}",bbox_inches='tight')

plt.clf()

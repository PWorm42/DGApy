#!/usr/bin/env python
'''
  Helper script to symmetrize the output of the w2dynamics code.
  Adapted from AbinitioDGA: https://github.com/AbinitioDGA/ADGA
'''
import h5py
import numpy as np
import sys
from shutil import copyfile

# not very pythonic utility function to unravel the band-spin compound index
def index2component_general(Nbands, N, ind):
  b=np.zeros((N),dtype=np.int_)
  s=np.zeros((N),dtype=np.int_)
  bs=np.zeros((N),dtype=np.int_)
  # the proposed back conversion assumes the indices are
  # given form 0 to max-1
  ind_tmp = ind - 1
  tmp=np.zeros((N+1),dtype=np.int_)
  for i in range(0,N+1):
    tmp[i] = (2*Nbands)**(N-i)

  for i in range(N):
    bs[i] = ind_tmp//tmp[i+1]
    s[i] = bs[i]%2
    b[i] = (bs[i]-s[i])//2
    ind_tmp = ind_tmp - tmp[i+1]*bs[i]

  return bs,b,s

# compute a compound index from orbital indices only.
def component2index_band(Nbands, N, b):
  ind = 1
  for i in range(N):
     ind = ind + Nbands**(N-i-1)*b[i]
  return ind

# for convenience and checking
def index2component_band(Nbands, N, ind):
  b=[]; ind_tmp = ind - 1
  for i in range(N):
    b.append(ind_tmp//(Nbands**(N-i-1)))
    ind_tmp = ind_tmp - b[i]*(Nbands**(N-i-1))
  return b

def ask_for_input():
  conf={}
  print("Which quantity do you want to symmetrize?")
  targ=int(input("0 -> 1 frequency (f), 1 -> 1 frequency (b), 2 -> 2 frequencies (fb), 3 -> 3 frequencies (ffb): "))
  if targ==0:
    conf['target']='1freq_f'
  if targ==1:
    conf['target']='1freq_b'
  elif targ==2:
    conf['target']='2freq'
  elif targ==3:
    conf['target']='3freq'

  filename_nosym=input('Filename of the not symmetrized data: ')
  conf['infile']=filename_nosym
  nineq=int(input('Number of inequivalent atoms: '))
  conf['nineq']=nineq

  conf['sym'] = []
  Nbands = []
  for ineq in range(nineq):
    print('  Atom {}:'.format(ineq+1))
    conf['sym'].append([])
    Nbands.append(int(input('    Number of correlated bands: ')))
    for i in range(Nbands[ineq]):
      conf['sym'][ineq].append(list(map(int,input('    Band {}: symmetric bands (seperated by spaces): '.format(i+1)).split())))
  conf['Nbands']=Nbands
  filename_sym=input('Outputfile for symmetrized data: ')
  conf['outfile']=filename_sym
  return conf

def get_groups(infile='infile.hdf5',Nbands=[1],target=1,nineq=1,worm_group='worm-last',**kwargs):
  conf = kwargs['conf']
  groups=[]
  bgroups=[]
  for ineq in range(nineq):
    f=h5py.File(infile,'r')
    if target=='1freq_b':
      gr_str=list(f['{}/ineq-{:03}/p2iw-worm'.format(worm_group, ineq+1)].keys())
    elif target=='2freq':
      gr_str=list(f['{}/ineq-{:03}/p3iw-worm'.format(worm_group, ineq+1)].keys())
    elif target=='3freq':
      gr_str=list(f['{}/ineq-{:03}/g4iw-worm'.format(worm_group, ineq+1)].keys())

    if len(gr_str) != 6*(3*Nbands[ineq]**2-2*Nbands[ineq]):
      print('WARNING: ineq-{:03} - Number of groups is not consistent with Kanamori interaction'.format(ineq+1))
      if (input('Continue anyways? (y/n): ') != 'y'):
        print('Exiting ...')
        sys.exit()

    f.close()
    groups.append([])
    bgroups.append([])
    groups[ineq]=[]
    bgroups[ineq]=[]
    bind=[]
    for gr in gr_str:
      bs,b,s=index2component_general(Nbands[ineq],4,int(gr))
      groups[ineq].append({'group':int(gr),'spins':tuple(s),'bands':tuple(b),'band-spin':tuple(bs)})
      bgr=component2index_band(Nbands[ineq],4,b)
      if not bgr in bind:
        bgroups[ineq].append({'bgroup':bgr,'bands':tuple(b)})
      bind.append(bgr)
  conf['groups']=groups
  conf['bgroups']=bgroups

def check_sym(**kwargs):
  nineq = kwargs['nineq']
  Nbands = kwargs['Nbands']
  sym = kwargs['sym']
  for ineq in range(nineq):
    for i in range(Nbands[ineq]):
      for j in sym[ineq][i]:
        if (set(sym[ineq][i]) != set(sym[ineq][j-1])):
          print('orbital symmetry not consistent!')
          sys.exit()

def get_fbox(infile=None,target=None,**kwargs):
  conf = kwargs['conf']
  f=h5py.File(infile,'r')
  if target=='1freq_b':
    n2iwb=f['worm-last/ineq-001/p2iw-worm/00001/value'].shape[0]
    print(n2iwb)
    conf['n2iwb']=n2iwb//2
  elif target=='2freq':
    n3iwf,n3iwb = f['worm-last/ineq-001/p3iw-worm/00001/value'].shape
    conf['n3iwf'],conf['n3iwb'] = n3iwf//2,n3iwb//2
    n3iwf,n3iwb=conf['n3iwf'],conf['n3iwb']
  elif target=='3freq':
    # new worm format -- f f b
    _,n4iwf,n4iwb = f['worm-last/ineq-001/g4iw-worm/00001/value'].shape # always here
    conf['n4iwf']=n4iwf//2
    conf['n4iwb']=n4iwb//2
    n4iwf,n4iwb=conf['n4iwf'],conf['n4iwb']

  f.close()


def initialize_output(f1,h5f,bgroups=None,nineq=None,n2iwb=None,n3iwf=None,n3iwb=None,n4iwf=None,n4iwb=None,target=None,**kwargs):
  for ineq in range(nineq):
    dset_ineq=h5f.create_group('ineq-{:03}'.format(ineq+1))
    dset_dens=dset_ineq.create_group('dens')
    dset_magn=dset_ineq.create_group('magn')

    if target=='1freq_b':
      for bgr in [d['bgroup'] for d in bgroups[ineq]]:
        dset_dens['{:05}'.format(bgr)]=np.zeros((2*n2iwb+1),dtype=np.complex128)
        dset_magn['{:05}'.format(bgr)]=np.zeros((2*n2iwb+1),dtype=np.complex128)
    elif target=='2freq':
      for iwb in range(2*n3iwb+1):
        dset_d1=dset_dens.create_group('{:05}'.format(iwb))
        dset_m1=dset_magn.create_group('{:05}'.format(iwb))
        for bgr in [d['bgroup'] for d in bgroups[ineq]]:
          dset_d1['{:05}'.format(bgr)]=np.zeros((2*n3iwf),dtype=np.complex128)
          dset_m1['{:05}'.format(bgr)]=np.zeros((2*n3iwf),dtype=np.complex128)
    elif target=='3freq':
      if ineq==0:
        f1.copy('.axes',h5f)
      for iwb in range(2*n4iwb+1):
        dset_d1=dset_dens.create_group('{:05}'.format(iwb))
        dset_m1=dset_magn.create_group('{:05}'.format(iwb))
        for bgr in [d['bgroup'] for d in bgroups[ineq]]:
          dset_d1['{:05}/value'.format(bgr)]=np.zeros((2*n4iwf,2*n4iwf),dtype=np.complex128)
          dset_m1['{:05}/value'.format(bgr)]=np.zeros((2*n4iwf,2*n4iwf),dtype=np.complex128)


def get_symgroups(ch,gr,sy,nd,**kwargs):
  if ch == 'dens':
    if gr['spins'] in [(0,0,0,0),(0,0,1,1),(1,1,0,0),(1,1,1,1)]:
      action = '+'
    elif gr['spins'] in [(0,1,1,0),(1,0,0,1)]:
      action = '0'
    else:
      print('unknown spin combination')
      sys.exit()
  elif ch == 'magn':
    if gr['spins'] in [(0,0,0,0),(0,1,1,0),(1,0,0,1),(1,1,1,1)]:
      action = '+'
    elif gr['spins'] in [(0,0,1,1),(1,1,0,0)]:
      action = '-'
    else:
      print('unknown spin combination')
      sys.exit()

  b1,b2,b3,b4=gr['bands']
  symgroups=[]
  if len(sy[b1])==1 and len(sy[b2])==1 and len(sy[b3])==1 and len(sy[b4])==1:
    symgroups.append(component2index_band(nd,4,gr['bands'])) # only su(2)
  else:
    if b1==b2 and b1==b3 and b1==b4:
      for i in sy[b1]:
        i-=1 # because it comes from the user input where we start at 1
        symgroups.append(component2index_band(nd,4,[i,i,i,i]))
    elif b1==b2 and b3==b4 and b2!=b3:
      for i in sy[b1]:
        i-=1
        for j in sy[b3]:
          j-=1
          if i!=j:
            symgroups.append(component2index_band(nd,4,[i,i,j,j]))
    elif b1==b3 and b2==b4 and b1!=b2:
      for i in sy[b1]:
        i-=1
        for j in sy[b2]:
          j-=1
          if i!=j:
            symgroups.append(component2index_band(nd,4,[i,j,i,j]))
    elif b1==b4 and b2==b3 and b1!=b2:
      for i in sy[b1]:
        i-=1
        for j in sy[b2]:
          j-=1
          if i!=j:
            symgroups.append(component2index_band(nd,4,[i,j,j,i]))

  return action,symgroups

def read_and_add(h5in,h5out,ineq,igr,channel,action,symgroups,target=None,n3iwb=None,n4iwb=None,worm_group='worm-last',**kwargs):
  if channel=='dens':
    prefactor = 2.0
  elif channel=='magn':
    prefactor = 4.0
  else:
    print('unkown channel')
    sys.exit()

  if target=='1freq_b':
    x = h5in['{}/ineq-{:03}/p2iw-worm/{:05}/value'.format(worm_group, ineq+1,igr)][()]/float(prefactor*len(symgroups))
    for gr in symgroups:
      if action=='+':
        h5out['ineq-{:03}/{}/{:05}'.format(ineq+1,channel,gr)][...]+=x
      elif action=='-':
        h5out['ineq-{:03}/{}/{:05}'.format(ineq+1,channel,gr)][...]-=x
      elif action=='0':
        pass
  elif target=='2freq':
    x = h5in['{}/ineq-{:03}/p3iw-worm/{:05}/value'.format(worm_group, ineq+1,igr)][()]/float(prefactor*len(symgroups))
    for iwb in range(2*n3iwb+1):
      for gr in symgroups:
        if action=='+':
          h5out['ineq-{:03}/{}/{:05}/{:05}'.format(ineq+1,channel,iwb,gr)][...]+=x[:,iwb]
        elif action=='-':
          h5out['ineq-{:03}/{}/{:05}/{:05}'.format(ineq+1,channel,iwb,gr)][...]-=x[:,iwb]
        elif action=='0':
          pass
  elif target=='3freq':
    x = h5in['{}/ineq-{:03}/g4iw-worm/{:05}/value'.format(worm_group, ineq+1,igr)][()]/float(prefactor*len(symgroups))
    if(np.any(np.isnan(x))):
      print('NaN encountered. Setting x = 0.')
      x[np.isnan(x)] = 0.0 + 1j * 0.0
    for iwb in range(2*n4iwb+1):
      for gr in symgroups:
        if action=='+':
          h5out['ineq-{:03}/{}/{:05}/{:05}/value'.format(ineq+1,channel,iwb,gr)][...]+=x[...,iwb].transpose()
        elif action=='-':
          h5out['ineq-{:03}/{}/{:05}/{:05}/value'.format(ineq+1,channel,iwb,gr)][...]-=x[...,iwb].transpose()
        elif action=='0':
          pass


# we provide the full dictionary and not just the kwargs!
def main(conf):
  print(conf)
  check_sym(**conf)
  f1=h5py.File(conf['infile'],'r')

  if conf['target']=='1freq_f': # we do this completely seperate since we only have to do sume numpy magic
    copyfile(conf['infile'],conf['outfile'])
    f2=h5py.File(conf['outfile'],'r+')
    for ineq in range(conf['nineq']):
      f2['dmft-last/ineq-{:03}/giw_unsymmetrized'.format(ineq+1)] = f2['dmft-last/ineq-{:03}/giwk_obj'.format(ineq+1)]
      del f2['dmft-last/ineq-{:03}/giwk_obj'.format(ineq+1)]
      f2['dmft-last/ineq-{:03}/giwk_obj/value'.format(ineq+1)] = np.zeros_like(f2['dmft-last/ineq-{:03}/giw_unsymmetrized/value'.format(ineq+1)], dtype=np.complex128)
      f2['dmft-last/ineq-{:03}/siw_unsymmetrized'.format(ineq+1)] = f2['dmft-last/ineq-{:03}/siw'.format(ineq+1)]
      del f2['dmft-last/ineq-{:03}/siw'.format(ineq+1)]
      f2['dmft-last/ineq-{:03}/siw/value'.format(ineq+1)] = np.zeros_like(f2['dmft-last/ineq-{:03}/siw_unsymmetrized/value'.format(ineq+1)], dtype=np.complex128)
      for band in range(conf['Nbands'][ineq]):
        for symband in conf['sym'][ineq][band]:
          f2['dmft-last/ineq-{:03}/giwk_obj/value'.format(ineq+1)][band,:,:] += \
            np.mean(f2['dmft-last/ineq-{:03}/giw_unsymmetrized/value'.format(ineq+1)][symband-1,:,:]/float(len(conf['sym'][ineq][band])), axis=0)
          f2['dmft-last/ineq-{:03}/siw/value'.format(ineq+1)][band,:,:] += \
            np.mean(f2['dmft-last/ineq-{:03}/siw_unsymmetrized/value'.format(ineq+1)][symband-1,:,:]/float(len(conf['sym'][ineq][band])), axis=0)
    f2.close()
  else: # 1freq_b, 2freq, 3freq
    get_groups(**conf,conf=conf)
    get_fbox(**conf,conf=conf)

    try:
      f2=h5py.File(conf['outfile'],'w-')
    except IOError:
      print('File already exists.')
      print('Exiting.')
      sys.exit(0)

    initialize_output(f1,f2,**conf)

    for ineq in range(conf['nineq']):
      for ch in ['dens','magn']:
          for gr in conf['groups'][ineq]:
            action,symgroups=get_symgroups(ch,gr,conf['sym'][ineq],conf['Nbands'][ineq],**conf)
            print('group {},'.format(gr['group']),'channel: {},'.format(ch),'action: {},'.format(action),'{} equivaluent band groups:'.format(len(symgroups)),symgroups)
            read_and_add(f1,f2,ineq,gr['group'],ch,action,symgroups,**conf)
            for i in symgroups:
               print(index2component_band(conf['Nbands'][ineq],4, i))
    f2.close()

  f1.close()

if __name__ == '__main__':
  try:
    if len(sys.argv) == 1:
        # Ask for input if no command line arguments are given
        conf = ask_for_input()
    else:
        # Otherwise determine "worm_group", "infile" and "outfile" from command line arguments
        # and set the other conf parameters to default values
        worm = sys.argv[1]
        input_file = "g4iw.hdf5"
        if len(sys.argv) >= 3:
            input_file = sys.argv[2]
        output_file = input_file.split(".")[0] + "_sym.hdf5"
        conf={'nineq': 1, 'target': '3freq', 'sym_type': 'o', 'outfile': output_file, 'Nbands': [1,1], 'infile': input_file, 'sym': [[[1]]], 'worm_group': worm}
    main(conf)
  except KeyboardInterrupt:
    print('\nKilled by user.')
    print('Exiting.')
    sys.exit(0)
  else:
    print('\nDone.')

# ids_06: intento acotado de reproducir el RNG (semillas 0..20000, random.choices/choice, numpy legacy/Generator, 2 alfabetos)
import random, string, numpy as np, time
alphs = {'AZ09': string.ascii_uppercase+string.digits, '09AZ': string.digits+string.ascii_uppercase}
targets = ['8QOW3F1','3DCC91G','7I07NJ7','LT0TPC5']
t0=time.time(); hits=[]
for seed in range(20001):
    for an,A in alphs.items():
        random.seed(seed); s=''.join(random.choices(A,k=300))
        random.seed(seed); s2=''.join([A[random.randrange(36)] for _ in range(300)])
        np.random.seed(seed); s4=''.join(np.random.choice(list(A),300))
        for name,x in [('choices',s),('randrange',s2),('nplegacy',s4)]:
            if any(t in x for t in targets): hits.append((seed,an,name,x[:60]))
    if seed<=2000:
        rng=np.random.default_rng(seed); s3=''.join(rng.choice(list(alphs['AZ09']),300))
        if any(t in s3 for t in targets): hits.append((seed,'AZ09','npgen',s3[:60]))
print('hits', hits[:5], 'secs', round(time.time()-t0))

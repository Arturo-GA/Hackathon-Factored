# utilidades: reconstruye la secuencia Mersenne Twister de random.seed(42) y el carácter que random.choices('0-9A-Z') produciría en cada palabra
import random, numpy as np
ALPH = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
AMAP = {c:i for i,c in enumerate(ALPH)}
def words(n, seed=42):
    r = random.Random(seed)
    b = r.getrandbits(32*n).to_bytes(4*n, 'little')
    return np.frombuffer(b, dtype='<u4').copy()
def chars_per_word(w):
    # random() = ((a>>5)*2^26 + (b>>6)) / 2^53 con a=w[p], b=w[p+1]; choices -> floor(random()*36)
    a = (w[:-1] >> 5).astype(np.float64); b = (w[1:] >> 6).astype(np.float64)
    u = (a*67108864.0 + b) / 9007199254740992.0
    return np.floor(u*36).astype(np.int8)  # char index at word position p
def encode(s):
    return np.array([AMAP[c] for c in s], dtype=np.int8)
def locate(cidx, ident, start=0, maxpos=None):
    """devuelve la primera posición p>=start tal que cidx[p+2j]==ident[j] para todo j"""
    e = encode(ident); k=len(e)
    end = len(cidx)-2*k if maxpos is None else min(maxpos, len(cidx)-2*k)
    cand = np.nonzero(cidx[start:end]==e[0])[0]+start
    for j in range(1,k):
        cand = cand[cidx[cand+2*j]==e[j]]
        if len(cand)==0: return -1
    return int(cand[0])
if __name__=='__main__':
    w = words(2000); c = chars_per_word(w)
    r = random.Random(42); print(''.join(r.choices(ALPH,k=30)))
    print(''.join(ALPH[x] for x in c[0:60:2]))

"""Ray-cast inside test for the cup-pod housing STLs (mechanical/out/v010-cup). Run with the main repo .venv python."""
import numpy as np, struct, sys
D='/Users/henryschwerdtner/dev/ai-insulin-pump-elec/mechanical/out/v010-cup/'
def load(fn):
    b=open(D+fn,'rb').read()
    if b[:5]==b'solid' and b'facet' in b[:300]:
        import re
        v=np.array(re.findall(rb'vertex\s+(\S+)\s+(\S+)\s+(\S+)',b),dtype=float).reshape(-1,3,3)
        return v
    n=struct.unpack('<I',b[80:84])[0]
    a=np.frombuffer(b[84:84+n*50],dtype=np.dtype([('n','<3f4'),('v','<9f4'),('a','<u2')]))
    return a['v'].reshape(-1,3,3).astype(float)
def inside(T,pts):
    # ray along +z; count crossings
    res=[]
    x0=T[:,:,0];y0=T[:,:,1]
    bx0,bx1=x0.min(1),x0.max(1); by0,by1=y0.min(1),y0.max(1)
    for (px,py,pz) in pts:
        m=(bx0<=px)&(px<=bx1)&(by0<=py)&(py<=by1)
        t=T[m]
        if len(t)==0: res.append(False); continue
        a,b,c=t[:,0],t[:,1],t[:,2]
        d=( (b[:,1]-c[:,1])*(a[:,0]-c[:,0]) + (c[:,0]-b[:,0])*(a[:,1]-c[:,1]) )
        ok=np.abs(d)>1e-12
        l1=((b[:,1]-c[:,1])*(px-c[:,0])+(c[:,0]-b[:,0])*(py-c[:,1]))/np.where(ok,d,1)
        l2=((c[:,1]-a[:,1])*(px-c[:,0])+(a[:,0]-c[:,0])*(py-c[:,1]))/np.where(ok,d,1)
        l3=1-l1-l2
        hit=ok&(l1>=0)&(l2>=0)&(l3>=0)
        z=l1*a[:,2]+l2*b[:,2]+l3*c[:,2]
        zs=np.unique(np.round(z[hit&(z>pz)],5))
        res.append(len(zs)%2==1)
    return np.array(res)
def solid_in_box(T,x0,x1,y0,y1,z0,z1,n=6):
    pts=[(x,y,z) for x in np.linspace(x0,x1,n) for y in np.linspace(y0,y1,n) for z in np.linspace(z0,z1,n)]
    r=inside(T,pts); return r.sum(), len(pts), [p for p,q in zip(pts,r) if q][:3]
def zcol(T,x,y,zs):
    return [round(z,2) for z,q in zip(zs,inside(T,[(x,y,z) for z in zs])) if q]
if __name__=='__main__':
    bot=load('OP-100_bottom.stl'); top=load('OP-100_top.stl'); res=load('OP-100_reservoir.stl')
    zs=np.arange(0.05,8.5,0.05)
    print('bottom bbox',bot.reshape(-1,3).min(0),bot.reshape(-1,3).max(0))
    print('top bbox',top.reshape(-1,3).min(0),top.reshape(-1,3).max(0))
    print('res bbox',res.reshape(-1,3).min(0),res.reshape(-1,3).max(0))
    def rng(l):
        if not l: return '[]'
        out=[];s=l[0];p=l[0]
        for z in l[1:]:
            if z-p>0.06: out.append((s,p)); s=z
            p=z
        out.append((s,p)); return out
    for nm,(x,y) in {'pocket roof centre':(39.36,11.75),'pocket roof edge':(36.5,7.0),'corridor 41,16':(41.0,16.3),'side_b 39,20':(39,20),'side_a 39.8,3':(39.8,3.0),
                     'post 45.41,2.55':(45.41,2.55),'post2 45.41,32.05':(45.41,32.05),'cell area 25,28':(25,28),'aux 41,28':(41,28),'ledge 40.57,24.3':(40.57,24.3),
                     'saddle edge 7.6,30.7':(7.6,30.7),'saddle edge 7.5,30.7':(7.5,30.7),'west 8.0,27':(8.0,27),'usb wall 12.3,33.9':(12.3,33.9),'-Y wall 39.8,0.5':(39.8,0.5),'-Y wall 39.8,0.85':(39.8,0.85)}.items():
        print(f'{nm:24s} bottom z {rng(zcol(bot,x,y,zs))}  top z {rng(zcol(top,x,y,zs))}')
    # board volume collision
    print('board slab vs bottom, west strip 7.45-7.8 y29.9-31.5:',solid_in_box(bot,7.45,7.8,29.9,31.5,5.31,6.09,8))
    print('board slab vs bottom whole lane2 7.45-43.4 y22.9-33.5:',solid_in_box(bot,7.46,43.39,22.91,33.49,5.31,6.09,14)[:2])
    print('board slab vs top lane2:',solid_in_box(top,7.46,43.39,22.91,33.49,5.31,6.09,14)[:2])
    print('board slab vs bottom corridor:',solid_in_box(bot,36.01,41.99,6.36,22.89,5.31,6.09,10)[:2], ' foot', solid_in_box(bot,35.41,44.19,1.11,6.34,5.31,6.09,10)[:2])
    print('board slab vs top corridor/foot:',solid_in_box(top,35.41,44.19,1.11,22.89,5.31,6.09,12)[:2])
    print('res vs board slab', solid_in_box(res,7.46,43.39,22.91,33.49,5.31,6.09,10)[:2], solid_in_box(res,35.41,44.19,1.11,22.89,5.31,6.09,10)[:2])
